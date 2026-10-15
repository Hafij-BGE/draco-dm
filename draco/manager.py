"""Download list, queues and scheduler. GUI-independent."""

import json
import os
import shlex
import shutil
import subprocess
import threading
import time
import urllib.parse
import uuid
from datetime import datetime
from pathlib import Path

from .config import DOWNLOADS_FILE, Settings
from .engine import HttpTask, RateLimiter, sanitize_filename, unique_path
from .media import FfmpegTask, HlsTask, YtdlpTask, is_hls

TASKS = {"http": HttpTask, "hls": HlsTask, "ffmpeg": FfmpegTask, "ytdlp": YtdlpTask}
TRANSIENT = {"speed", "_dirty"}
ACTIVE = ("connecting", "downloading", "merging")


def guess_kind(url, content_type=""):
    if is_hls(url, content_type):
        return "hls"
    if urllib.parse.urlparse(url).path.lower().endswith(".mpd") or "dash+xml" in (content_type or ""):
        return "ffmpeg"
    return "http"


class Manager:
    def __init__(self, settings: Settings, store=DOWNLOADS_FILE):
        self.settings = settings
        self.store = Path(store)
        self.lock = threading.RLock()
        self.items = {}            # id -> record (dict); insertion order = list order
        self.tasks = {}            # id -> running task
        self.listeners = []        # callables(event, item_or_payload)
        self.queue_running = {}
        self._queue_skip = set()
        self._last_sched_minute = None
        self.dirty = False
        self.global_limiter = RateLimiter(settings["speed_limit_kbps"] * 1024)
        self._load()

    # -- events ---------------------------------------------------------------
    def emit(self, event, payload=None):
        if event in ("added", "changed", "removed", "finished"):
            self.dirty = True
        for fn in list(self.listeners):
            try:
                fn(event, payload)
            except Exception as e:  # never let a UI bug kill a download thread
                print("listener error:", e)

    # -- persistence --------------------------------------------------------
    def _load(self):
        if not self.store.exists():
            return
        try:
            data = json.loads(self.store.read_text())
        except (OSError, ValueError):
            return
        for it in data.get("items", []):
            if it.get("status") in ACTIVE:
                it["status"] = "paused"  # was running when the app quit/crashed
            it["speed"] = 0
            self.items[it["id"]] = it

    def save(self):
        with self.lock:
            data = {"version": 1, "items": [{k: v for k, v in it.items() if k not in TRANSIENT}
                                            for it in self.items.values()]}
        self.store.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.store.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)  # holds cookies
        with os.fdopen(fd, "w") as fh:
            json.dump(data, fh)
        os.replace(tmp, self.store)
        self.dirty = False

    def save_if_dirty(self):
        if self.dirty or any(it.pop("_dirty", False) for it in list(self.items.values())):
            self.save()

    # -- items --------------------------------------------------------------
    def new_item(self, url, filename="", size=-1, referer="", cookies="", headers=None,
                 description="", kind=None, content_type="", resumable=False, probed=False,
                 final_url="", user_agent=""):
        filename = sanitize_filename(filename) if filename else ""
        kind = kind or guess_kind(url, content_type)
        category = ("Video" if kind in ("hls", "ffmpeg", "ytdlp")
                    else self.settings.category_for(filename or urllib.parse.urlparse(url).path))
        return {
            "id": uuid.uuid4().hex[:12],
            "url": url, "final_url": final_url, "referer": referer, "cookies": cookies,
            "headers": headers or {}, "user_agent": user_agent,
            "filename": filename, "size": size, "resumable": resumable, "probed": probed,
            "content_type": content_type,
            "kind": kind,
            "category": category,
            "save_dir": str(self.settings.folder_for(category)),
            "description": description,
            "status": "stopped", "downloaded": 0, "speed": 0, "error": "",
            "segments": [], "queue": "", "queue_pos": 0,
            "connections": self.settings["connections"],
            "speed_limit_kbps": 0,
            "added": time.time(), "last_try": None, "finished": None,
        }

    def add(self, item, start=False, queue=""):
        with self.lock:
            if self.settings["duplicate_action"] == "rename" and item.get("filename"):
                reserved = {str(Path(i["save_dir"]) / i["filename"])
                            for i in self.items.values() if i["status"] != "complete"}
                p = unique_path(Path(item["save_dir"]) / item["filename"], reserved)
                item["filename"] = p.name
            item["queue"] = queue or ""
            if queue:
                item["queue_pos"] = 1 + max([i.get("queue_pos", 0) for i in self.items.values()
                                             if i.get("queue") == queue] or [0])
            self.items[item["id"]] = item
        self.emit("added", item)
        if start:
            self.start(item["id"])
        elif queue and self.queue_running.get(queue):
            self.pump_queues()
        return item["id"]

    def get(self, item_id):
        return self.items.get(item_id)

    def start(self, item_id):
        with self.lock:
            it = self.items.get(item_id)
            if not it or item_id in self.tasks or it["status"] == "complete":
                return False
            self._queue_skip.discard(item_id)
            cls = TASKS.get(it.get("kind", "http"), HttpTask)
            task = cls(it, self.settings, self.global_limiter,
                       on_update=lambda i: self.emit("changed", i),
                       on_finish=self._on_finish)
            task.reserve_name = self._reserve_name
            self.tasks[item_id] = task
            it["status"] = "connecting"
        task.start()
        self.emit("changed", it)
        return True

    def _reserve_name(self, item, name):
        """Pick the final file name once the server told us its name (called from task threads)."""
        with self.lock:
            if item.get("auto_category"):
                item["category"] = self.settings.category_for(name)
                item["save_dir"] = str(self.settings.folder_for(item["category"]))
            if self.settings["duplicate_action"] != "rename":
                return name
            reserved = {str(Path(i["save_dir"]) / i["filename"]) for i in self.items.values()
                        if i is not item and i["status"] != "complete" and i.get("filename")}
            name = unique_path(Path(item["save_dir"]) / name, reserved).name
            item["filename"] = name
            return name

    def pause(self, item_id):
        self._queue_skip.add(item_id)  # a running queue must not restart it
        task = self.tasks.get(item_id)
        if task:
            task.stop()
        elif item_id in self.items and self.items[item_id]["status"] == "queued":
            self.items[item_id]["status"] = "stopped"
            self.emit("changed", self.items[item_id])

    def stop_all(self):
        for q in list(self.queue_running):
            self.queue_running[q] = False
        for task in list(self.tasks.values()):
            task.stop()

    def task(self, item_id):
        return self.tasks.get(item_id)

    def _on_finish(self, item, ok):
        with self.lock:
            self.tasks.pop(item["id"], None)
            if not ok and item.get("queue") and item["status"] == "error":
                self._queue_skip.add(item["id"])
        self.emit("finished", item)
        if ok and self.settings["antivirus_cmd"]:
            threading.Thread(target=self._scan, args=(item,), daemon=True).start()
        self.pump_queues()

    def _scan(self, item):
        path = str(Path(item["save_dir"]) / item["filename"])
        cmd = self.settings["antivirus_cmd"].replace("{file}", shlex.quote(path))
        try:
            from .osdeps import popen_kwargs
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=600, **popen_kwargs())
            item["scan"] = "clean" if r.returncode == 0 else f"flagged ({r.returncode}): {r.stdout.strip()[:200]}"
        except Exception as e:
            item["scan"] = f"scan failed: {e}"
        self.emit("scanned", item)

    def remove(self, ids, delete_files=False):
        for item_id in ids:
            task = self.tasks.get(item_id)
            if task:
                task.stop()
                task.join(5)
            with self.lock:
                it = self.items.pop(item_id, None)
            if not it:
                continue
            base = Path(it["save_dir"])
            for p in (base / (it["filename"] + self.settings["temp_suffix"]),):
                if it["filename"] and p.exists():
                    p.unlink()
            hls_dir = base / f".{it['filename']}.dracohls"
            if it["filename"] and hls_dir.is_dir():
                shutil.rmtree(hls_dir, ignore_errors=True)
            if delete_files and it["status"] == "complete" and it["filename"]:
                f = base / it["filename"]
                if f.is_file():
                    f.unlink()
            self.emit("removed", it)

    def reset(self, item_id):
        """Re-download from scratch."""
        it = self.items.get(item_id)
        if not it or item_id in self.tasks:
            return
        tmp = Path(it["save_dir"]) / (it["filename"] + self.settings["temp_suffix"])
        if tmp.exists():
            tmp.unlink()
        it.update(segments=[], downloaded=0, status="stopped", probed=False, size=-1, error="",
                  finished=None)
        self.emit("changed", it)

    def refresh_address(self, item_id, url, referer=None, cookies=None):
        """Point a broken/expired download at a fresh link and keep the downloaded data."""
        it = self.items.get(item_id)
        if not it:
            return
        was_running = item_id in self.tasks
        if was_running:
            self.tasks[item_id].stop()
            self.tasks[item_id].join(10)
        it["url"], it["final_url"] = url, ""
        if referer is not None:
            it["referer"] = referer
        if cookies is not None:
            it["cookies"] = cookies
        self.emit("changed", it)
        if was_running or it["status"] == "error":
            self.start(item_id)

    # -- queues -------------------------------------------------------------
    def queue_names(self):
        return [q["name"] for q in self.settings["queues"]]

    def queue_conf(self, name):
        return next((q for q in self.settings["queues"] if q["name"] == name), None)

    def queue_items(self, name):
        return sorted((i for i in self.items.values() if i.get("queue") == name),
                      key=lambda i: i.get("queue_pos", 0))

    def set_queue(self, ids, name):
        for item_id in ids:
            it = self.items.get(item_id)
            if it:
                it["queue"] = name or ""
                it["queue_pos"] = time.time()
                self.emit("changed", it)
        self.pump_queues()

    def move_in_queue(self, item_id, delta):
        it = self.items.get(item_id)
        if not it or not it.get("queue"):
            return
        items = self.queue_items(it["queue"])
        idx = items.index(it)
        j = max(0, min(len(items) - 1, idx + delta))
        items.insert(j, items.pop(idx))
        for pos, i in enumerate(items):
            i["queue_pos"] = pos
        self.emit("reordered", it["queue"])

    def start_queue(self, name):
        self.queue_running[name] = True
        self._queue_skip = {i for i in self._queue_skip if self.items.get(i, {}).get("queue") != name}
        self.emit("queue", {"name": name, "running": True})
        self.pump_queues()

    def stop_queue(self, name):
        self.queue_running[name] = False
        for it in self.queue_items(name):
            if it["id"] in self.tasks:
                self.tasks[it["id"]].stop()
            elif it["status"] == "queued":
                it["status"] = "stopped"
                self.emit("changed", it)
        self.emit("queue", {"name": name, "running": False})

    def pump_queues(self):
        finished_queues = []
        with self.lock:
            for name, running in list(self.queue_running.items()):
                if not running:
                    continue
                conf = self.queue_conf(name) or {}
                retry = conf.get("schedule", {}).get("retry_failed", True)
                items = self.queue_items(name)
                active = [i for i in items if i["id"] in self.tasks]
                waiting = [i for i in items if i["id"] not in self.tasks and i["status"] != "complete"
                           and (i["status"] != "error" or (retry and i["id"] not in self._queue_skip))]
                slots = max(1, int(conf.get("max_active", 1))) - len(active)
                for i in waiting[:max(0, slots)]:
                    self.start(i["id"])
                for i in waiting[max(0, slots):]:
                    if i["status"] != "queued":
                        i["status"] = "queued"
                        self.emit("changed", i)
                if not active and not waiting:
                    self.queue_running[name] = False
                    finished_queues.append(conf)
        for conf in finished_queues:
            self.emit("queue", {"name": conf.get("name"), "running": False})
            self.emit("queue_done", conf)

    def scheduler_tick(self, now=None):
        now = now or datetime.now()
        minute = now.strftime("%Y-%m-%d %H:%M")
        if minute == self._last_sched_minute:
            return
        self._last_sched_minute = minute
        hm, wd = now.strftime("%H:%M"), now.weekday()
        changed = False
        for q in self.settings["queues"]:
            s = q.get("schedule", {})
            if not s.get("enabled") or wd not in s.get("days", []):
                continue
            if s.get("start") == hm and not self.queue_running.get(q["name"]):
                self.start_queue(q["name"])
                if s.get("once"):
                    s["enabled"] = False
                    changed = True
            if s.get("stop") == hm and self.queue_running.get(q["name"]):
                self.stop_queue(q["name"])
        if changed:
            self.settings.save()

    def shutdown(self):
        tasks = list(self.tasks.values())
        for t in tasks:
            t.stop()
        for t in tasks:
            t.join(10)
        self.save()
