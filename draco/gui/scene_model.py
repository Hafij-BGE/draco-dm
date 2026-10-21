"""State behind the live planet in the details pane (no GTK here, so it can be unit tested).

The planet never invents progress: `scene_state()` reads the engine's own item fields and
`SceneMotion` only eases the picture toward them (the progress ring never runs ahead of the
real fraction). Stages follow the design: Initializing 0-5 %, Downloading 5-70 %, High speed
70-95 %, Finalizing 95-100 % (or while the engine joins the parts), Completed 100 %."""

from dataclasses import dataclass

# Engine status -> scene state
_STATES = {"connecting": "connecting", "downloading": "downloading", "merging": "merging",
           "complete": "completed", "error": "error", "queued": "queued",
           "paused": "paused", "stopped": "paused"}

STAGES = ("idle", "initializing", "downloading", "highspeed", "finalizing", "completed", "paused", "error")

LABELS = {"idle": "Select a download", "initializing": "Initializing…", "downloading": "Downloading…",
          "highspeed": "Downloading…", "finalizing": "Finalizing…", "completed": "Completed!",
          "paused": "Paused", "queued": "Queued", "error": "Error"}

# Colours per stage: (ring, glow, sky tint) as 0..1 RGB
PALETTE = {
    "idle":         ((0.55, 0.60, 0.95), (0.45, 0.50, 0.95), (0.30, 0.22, 0.70)),
    "initializing": ((0.60, 0.62, 1.00), (0.50, 0.55, 1.00), (0.42, 0.25, 0.85)),
    "downloading":  ((0.40, 0.75, 1.00), (0.35, 0.65, 1.00), (0.20, 0.35, 0.95)),
    "highspeed":    ((1.00, 0.50, 0.92), (0.55, 0.80, 1.00), (0.55, 0.25, 0.95)),
    "finalizing":   ((1.00, 0.68, 0.22), (1.00, 0.55, 0.18), (0.95, 0.38, 0.12)),
    "completed":    ((0.88, 0.88, 1.00), (0.70, 0.72, 1.00), (0.55, 0.50, 0.95)),
    "paused":       ((0.98, 0.78, 0.30), (0.55, 0.55, 0.80), (0.30, 0.25, 0.60)),
    "error":        ((0.98, 0.45, 0.45), (0.90, 0.35, 0.40), (0.55, 0.15, 0.25)),
}


@dataclass(frozen=True)
class SceneState:
    state: str = "idle"        # engine side: idle, connecting, downloading, merging, completed, error, queued, paused
    fraction: float = 0.0      # 0..1 from the engine; -1 when the size is unknown
    speed: float = 0.0         # bytes/s, only while downloading
    item_id: str = ""

    @property
    def stage(self):
        """Look of the planet: one of STAGES."""
        s = self.state
        if s in ("idle", "completed", "error", "paused"):
            return s
        if s == "queued":
            return "paused"
        if s == "merging":
            return "finalizing"
        if s == "connecting" or self.fraction < 0.05:
            return "initializing"
        if self.fraction >= 0.95:
            return "finalizing"
        return "highspeed" if self.fraction >= 0.70 else "downloading"

    @property
    def flowing(self):
        """Data particles stream in only while bytes really arrive."""
        return self.state in ("downloading", "merging") and (self.speed > 0 or self.state == "merging")

    @property
    def label(self):
        if self.state == "queued":
            return LABELS["queued"]
        return LABELS[self.stage]


def scene_state(item):
    """SceneState for one engine item (None = nothing selected)."""
    if not item:
        return SceneState()
    st = _STATES.get(item.get("status", "stopped"), "paused")
    if st == "completed":
        frac = 1.0
    elif item.get("fraction"):
        frac = float(item["fraction"])
    elif item.get("seg_total"):
        frac = item.get("seg_done", 0) / item["seg_total"]
    elif (item.get("size") or -1) > 0:
        frac = item.get("downloaded", 0) / item["size"]
    else:
        frac = -1.0
    frac = -1.0 if frac < 0 else max(0.0, min(1.0, frac))
    speed = float(item.get("speed") or 0) if st == "downloading" else 0.0
    return SceneState(st, frac, speed, str(item.get("id", "")))


def _approach(value, target, dt, rate):
    return value + (target - value) * min(1.0, dt * rate)


class SceneMotion:
    """Eased values the planet is drawn with. Call `update(dt)` once per frame."""

    def __init__(self):
        self.state = SceneState()
        self.arc = 0.0        # shown progress, never above the real fraction
        self.flow = 0.0       # 0..1 how many data particles stream in (follows the average speed)
        self.active = 0.0     # 0..1 a download is moving: steady motion and brightness, not the raw speed
        self.avg = 0.0        # speed averaged over a few seconds (a jumpy speed must not shake the scene)
        self.speedy = 0.0     # 0..1 high-speed look (bright rings, speed lines)
        self.tight = 0.0      # 0..1 rings pulled in (finalizing)
        self.calm = 0.0       # 1 = completed (stable success glow)
        self.alarm = 0.0      # 1 = error
        self.hold = 0.0       # 1 = paused / queued
        self.wake = 0.0       # 0 = dark planet (initializing), 1 = lit
        self.colors = PALETTE["idle"]
        self.peak = 1.0

    def set_state(self, state):
        if state.item_id != self.state.item_id:     # another download: jump, don't animate from the old one
            self.state = state
            self.peak = 1.0
            self.avg = state.speed
            self.settle()
            self.flow = 0.0
            return
        self.state = state

    def targets(self):
        s = self.state
        stage = s.stage
        flow = 0.0
        if s.flowing:
            flow = 0.5 + 0.5 * min(1.0, self.avg / self.peak) if s.speed else 0.8
        return {"flow": flow, "active": 1.0 if s.flowing else 0.0,
                "speedy": 1.0 if stage == "highspeed" else 0.0,
                "tight": 1.0 if stage == "finalizing" else 0.0,
                "calm": 1.0 if stage == "completed" else 0.0,
                "alarm": 1.0 if stage == "error" else 0.0,
                "hold": 1.0 if stage == "paused" else 0.0,
                "wake": 0.25 if stage in ("idle", "initializing") else 1.0}

    def update(self, dt):
        self.avg = _approach(self.avg, self.state.speed, dt, 0.25)
        self.peak = max(self.peak * (1 - 0.01 * dt), self.avg, 1.0)
        for k, v in self.targets().items():
            slow = k == "flow" and self.state.flowing        # calm while running, quick to stop on pause
            setattr(self, k, _approach(getattr(self, k), v, dt, 0.8 if slow else 2.0))
        target = PALETTE[self.state.stage]
        self.colors = tuple(tuple(_approach(a, b, dt, 1.8) for a, b in zip(cur, tgt))
                            for cur, tgt in zip(self.colors, target))
        real = max(0.0, self.state.fraction)
        if self.arc > real:            # progress went back (restart): follow at once
            self.arc = real
        else:
            self.arc = min(real, _approach(self.arc, real, dt, 4.0) + 1e-4)

    def settle(self):
        """Jump straight to the targets (another download, or Reduce motion)."""
        for k, v in self.targets().items():
            setattr(self, k, v)
        self.colors = PALETTE[self.state.stage]
        self.arc = max(0.0, self.state.fraction)
