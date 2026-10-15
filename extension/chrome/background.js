// Draco Download Manager browser integration (Chrome, Brave, Edge, Firefox).
const HOST = "io.github.draco";
const DEFAULT_EXTS = ("3gp 7z aac ace aif apk arj asf avi bin bz2 deb dmg exe flac flv gz gzip iso jar " +
  "lzh m4a m4v mkv mov mp3 mp4 mpeg mpg msi ogg ogv opus pdf pkg rar rpm sit sitx tar tgz wav webm wma " +
  "wmv xz z zip zst appimage epub").split(" ");
const MEDIA_TYPES = /^(video\/|audio\/)|mpegurl|dash\+xml/i;
const STREAM_EXT = /\.(m3u8|mpd)(\?|$)/i;
const SEGMENT_EXT = /\.(ts|m4s|m4a|aac|vtt|webvtt|key)(\?|$)/i;

const state = { capture: true, exts: DEFAULT_EXTS, minKB: 0, quick: false, subs: false };
const SUB_LANG = (navigator.language || "en").split("-")[0];
// Sites whose videos need yt-dlp (adaptive streams that a plain download can't fetch).
const YTDLP_SITES = /(^|\.)(youtube\.com|youtu\.be|vimeo\.com|dailymotion\.com|tiktok\.com|twitch\.tv|facebook\.com|instagram\.com|x\.com|twitter\.com|reddit\.com|soundcloud\.com|bilibili\.com|bilibili\.tv|streamable\.com|rumble\.com|vk\.com|ok\.ru)$/i;
function isVideoPage(url) {
  try {
    const u = new URL(url);
    if (!YTDLP_SITES.test(u.hostname)) return false;
    if (/(^|\.)youtube\.com$/i.test(u.hostname)) return /^\/(watch|shorts\/|live\/|embed\/)/.test(u.pathname);
    return true;
  } catch (e) {
    return false;
  }
}
const media = {};             // tabId -> [{url, type, size, title}]
const bypass = new Set();     // urls we re-handed to the browser after Draco failed

chrome.storage.local.get({ capture: true, exts: DEFAULT_EXTS.join(" "), minKB: 0, quick: false, subs: false }, (v) => {
  state.capture = v.capture;
  state.quick = v.quick;
  state.subs = v.subs;
  state.exts = v.exts.split(/\s+/).filter(Boolean);
  state.minKB = v.minKB;
});
chrome.storage.onChanged.addListener((ch) => {
  if (ch.capture) state.capture = ch.capture.newValue;
  if (ch.exts) state.exts = ch.exts.newValue.split(/\s+/).filter(Boolean);
  if (ch.minKB) state.minKB = ch.minKB.newValue;
  if (ch.quick) state.quick = ch.quick.newValue;
  if (ch.subs) state.subs = ch.subs.newValue;
});
if (chrome.storage.session) {
  chrome.storage.session.get({ media: {} }, (v) => Object.assign(media, v.media || {}));
}
function saveMedia() {
  if (chrome.storage.session) chrome.storage.session.set({ media });
}

// Two ways to reach Draco: native messaging (normal browsers) and, for snap/flatpak
// browsers that can't start native hosts, a paired loopback bridge on 127.0.0.1.
const BRIDGE_PORTS = [47823, 47824, 47825, 47826, 47827];
const NATIVE_MISSING = /native messaging host|forbidden|not found|has exited|communicating with the native/i;
let nativeWorks = null;
let bridgePort = null;

async function native(msg) {
  if (nativeWorks !== false) {
    const r = await nativeRaw(msg);
    if (r.ok || !NATIVE_MISSING.test(r.error || "")) {
      nativeWorks = true;
      return r;
    }
    nativeWorks = false;
  }
  return bridge(msg);
}

async function findBridge() {
  if (bridgePort) return bridgePort;
  for (const p of BRIDGE_PORTS) {
    try {
      const r = await fetch(`http://127.0.0.1:${p}/ping`, { cache: "no-store" });
      const j = await r.json();
      if (j.app === "draco") { bridgePort = p; return p; }
    } catch (e) { /* try next port */ }
  }
  return null;
}

async function bridge(msg) {
  const port = await findBridge();
  if (!port) return { ok: false, error: "Draco is not running. Start Draco and try again." };
  const { token } = await chrome.storage.local.get({ token: "" });
  if (!token) return { ok: false, error: "Not connected to Draco yet", needPair: true };
  try {
    const r = await fetch(`http://127.0.0.1:${port}/msg`, {
      method: "POST", headers: { "Content-Type": "application/json", "X-Draco-Token": token },
      body: JSON.stringify(msg),
    });
    if (r.status === 401) return { ok: false, error: "Not connected to Draco yet", needPair: true };
    return await r.json();
  } catch (e) {
    bridgePort = null;
    return { ok: false, error: String(e) };
  }
}

async function pairWithDraco() {
  bridgePort = null;
  const port = await findBridge();
  if (!port) return { ok: false, error: "Start Draco first, then try again." };
  try {
    const r = await fetch(`http://127.0.0.1:${port}/pair`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: "{}",
    });
    const j = await r.json();
    if (j.ok && j.token) {
      await chrome.storage.local.set({ token: j.token });
      return { ok: true };
    }
    return { ok: false, error: j.error || "Pairing was declined in Draco" };
  } catch (e) {
    return { ok: false, error: String(e) };
  }
}

function nativeRaw(msg) {
  return new Promise((resolve) => {
    try {
      chrome.runtime.sendNativeMessage(HOST, msg, (reply) => {
        if (chrome.runtime.lastError) resolve({ ok: false, error: chrome.runtime.lastError.message });
        else resolve(reply || { ok: false, error: "no reply" });
      });
    } catch (e) {
      resolve({ ok: false, error: String(e) });
    }
  });
}

async function cookiesFor(url) {
  try {
    const list = await chrome.cookies.getAll({ url });
    return list.map((c) => `${c.name}=${c.value}`).join("; ");
  } catch (e) {
    return "";
  }
}

async function sendToDraco(url, extra = {}) {
  const msg = Object.assign({
    cmd: "add", url, cookies: await cookiesFor(url), user_agent: navigator.userAgent,
  }, extra);
  return native(msg);
}

function extOf(name) {
  const clean = (name || "").split(/[?#]/)[0];
  const last = clean.split("/").pop();
  const i = last.lastIndexOf(".");
  return i > 0 ? last.slice(i + 1).toLowerCase() : "";
}

// ---------------------------------------------------------------- downloads
function shouldCapture(item) {
  if (!state.capture) return false;
  const url = item.finalUrl || item.url;
  if (!/^(https?|ftp):/i.test(url) || bypass.has(url)) return false;
  if (item.fileSize > 0 && item.fileSize < state.minKB * 1024) return false;
  const ext = extOf(item.filename) || extOf(url);
  if (state.exts.includes(ext)) return true;
  return /^(application\/(octet-stream|zip|x-|vnd\.android)|video\/|audio\/)/i.test(item.mime || "") &&
    !/^(application\/(json|xml|javascript)|text\/)/i.test(item.mime || "");
}

chrome.downloads.onCreated.addListener(async (item) => {
  if (!shouldCapture(item)) return;
  const url = item.finalUrl || item.url;
  try { await chrome.downloads.cancel(item.id); } catch (e) { /* already done */ }
  try { await chrome.downloads.erase({ id: item.id }); } catch (e) { /* ignore */ }
  const reply = await sendToDraco(url, {
    referer: item.referrer || "", filename: (item.filename || "").split(/[\\/]/).pop(),
    size: item.totalBytes > 0 ? item.totalBytes : undefined, silent: state.quick,
  });
  if (!reply.ok) {
    // Draco not reachable: give the download back to the browser.
    bypass.add(url);
    chrome.downloads.download({ url });
    setTimeout(() => bypass.delete(url), 60000);
    console.warn("Draco unavailable:", reply.error);
  }
});

// ---------------------------------------------------------------- media sniffing
function header(details, name) {
  const h = (details.responseHeaders || []).find((x) => x.name.toLowerCase() === name);
  return h ? h.value : "";
}

chrome.webRequest.onHeadersReceived.addListener((d) => {
  if (d.tabId < 0) return;
  if (/(^|\.)(googlevideo\.com|ytimg\.com)$/i.test(new URL(d.url).hostname)) return;  // YouTube: use yt-dlp
  const type = header(d, "content-type");
  const isStream = STREAM_EXT.test(d.url) || /mpegurl|dash\+xml/i.test(type);
  if (!isStream && !MEDIA_TYPES.test(type)) return;
  if (!isStream && SEGMENT_EXT.test(d.url)) return;
  let size = 0;
  const cr = header(d, "content-range");
  if (cr && /\/(\d+)/.test(cr)) size = parseInt(cr.match(/\/(\d+)/)[1], 10);
  else size = parseInt(header(d, "content-length") || "0", 10);
  if (!isStream && size && size < 512 * 1024) return;   // skip tiny clips/sounds
  // Strip byte-range query params some players add, so Draco fetches the whole file.
  let url = d.url;
  try {
    const u = new URL(url);
    ["range", "rn", "rbuf", "bytestart", "byteend"].forEach((p) => u.searchParams.delete(p));
    url = u.toString();
  } catch (e) { /* keep */ }
  const list = media[d.tabId] || (media[d.tabId] = []);
  if (list.some((m) => m.url === url) || (hlsChildren[d.tabId] || new Set()).has(url)) return;
  const entry = { url, type: isStream ? (/mpd/i.test(url + type) ? "DASH" : "HLS") : type, size };
  list.push(entry);
  if (list.length > 30) list.shift();
  publishMedia(d.tabId);
  if (entry.type === "HLS") analyzeHls(d.tabId, entry);
}, { urls: ["<all_urls>"], types: ["media", "xmlhttprequest", "other", "object"] }, ["responseHeaders"]);

function publishMedia(tabId) {
  const list = media[tabId] || [];
  saveMedia();
  chrome.action.setBadgeText({ tabId, text: list.length ? String(list.length) : "" });
  chrome.action.setBadgeBackgroundColor({ tabId, color: "#3584e4" });
  chrome.tabs.sendMessage(tabId, { type: "draco-media", list }).catch(() => {});
}

// ---------------------------------------------------------------- HLS details (quality, size, length)
const hlsChildren = {};   // tabId -> Set of variant playlist URLs already shown under their master

function m3u8Attrs(line) {
  const out = {};
  const body = line.slice(line.indexOf(":") + 1);
  for (const m of body.matchAll(/([A-Z0-9-]+)=("[^"]*"|[^,]*)/g)) out[m[1]] = m[2].replace(/^"|"$/g, "");
  return out;
}

function parseM3u8(text, base) {
  const out = { variants: [], duration: 0, segments: 0, firstSeg: null, encrypted: false, separateAudio: false };
  let pending = null;
  for (const raw of text.split(/\r?\n/)) {
    const l = raw.trim();
    if (!l) continue;
    if (l.startsWith("#EXT-X-STREAM-INF")) {
      const a = m3u8Attrs(l);
      const [w, h] = (a.RESOLUTION || "x").split("x").map((n) => parseInt(n, 10) || 0);
      pending = { bw: parseInt(a["AVERAGE-BANDWIDTH"] || a.BANDWIDTH || "0", 10), width: w, height: h };
      if (a.AUDIO) out.separateAudio = true;
    } else if (l.startsWith("#EXTINF")) {
      out.duration += parseFloat(l.slice(8)) || 0;
      out.segments++;
    } else if (l.startsWith("#EXT-X-KEY") && !/METHOD=NONE/.test(l)) {
      out.encrypted = true;
    } else if (!l.startsWith("#")) {
      const u = new URL(l, base).href;
      if (pending) { pending.url = u; out.variants.push(pending); pending = null; }
      else if (!out.firstSeg) out.firstSeg = u;
    }
  }
  return out;
}

async function fetchText(url) {
  const r = await fetch(url, { credentials: "include", cache: "no-store" });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return { text: await r.text(), base: r.url || url };
}

async function segmentSize(url) {
  try {
    const r = await fetch(url, { method: "HEAD", credentials: "include" });
    const n = parseInt(r.headers.get("content-length") || "0", 10);
    if (n) return n;
  } catch (e) { /* fall through */ }
  try {
    const r = await fetch(url, { headers: { Range: "bytes=0-0" }, credentials: "include" });
    const m = /\/(\d+)/.exec(r.headers.get("content-range") || "");
    return m ? parseInt(m[1], 10) : 0;
  } catch (e) {
    return 0;
  }
}

async function analyzeHls(tabId, entry) {
  try {
    const { text, base } = await fetchText(entry.url);
    const pl = parseM3u8(text, base);
    if (pl.variants.length) {
      // Master playlist: one row per quality. Read one variant for the length.
      const kids = hlsChildren[tabId] || (hlsChildren[tabId] = new Set());
      pl.variants.forEach((v) => kids.add(v.url));
      let duration = 0;
      try {
        const sample = await fetchText(pl.variants[0].url);
        duration = parseM3u8(sample.text, sample.base).duration;
      } catch (e) { /* unknown length */ }
      entry.duration = duration;
      entry.separateAudio = pl.separateAudio;
      entry.variants = pl.variants
        .sort((a, b) => b.height - a.height || b.bw - a.bw)
        .map((v) => ({ url: v.url, height: v.height, width: v.width,
                       size: duration && v.bw ? Math.round(v.bw * duration / 8) : 0 }));
      // Drop variant playlists that were listed on their own before we knew the master.
      media[tabId] = (media[tabId] || []).filter((m) => m === entry || !kids.has(m.url));
    } else {
      entry.duration = pl.duration;
      entry.encrypted = pl.encrypted;
      if (pl.firstSeg && pl.segments) {
        const first = await segmentSize(pl.firstSeg);
        if (first) entry.size = Math.round(first * pl.segments);
      }
    }
    entry.analyzed = true;
  } catch (e) {
    entry.analyzed = false;
  }
  publishMedia(tabId);
}

chrome.tabs.onRemoved.addListener((tabId) => { delete media[tabId]; delete hlsChildren[tabId]; saveMedia(); });
chrome.tabs.onUpdated.addListener((tabId, info) => {
  // Fires on real page loads and on in-page navigation (YouTube switching videos).
  if (info.url) {
    delete media[tabId];
    delete hlsChildren[tabId];
    saveMedia();
    chrome.action.setBadgeText({ tabId, text: "" });
  }
});

// ---------------------------------------------------------------- context menus
chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.local.get(["exts"], (v) => {
    if (!v.exts) chrome.storage.local.set({ exts: DEFAULT_EXTS.join(" "), capture: true, minKB: 0 });
  });
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({ id: "draco-link", title: "Download with Draco", contexts: ["link", "video", "audio", "image"] });
    chrome.contextMenus.create({ id: "draco-quick", title: "Quick download with Draco (no dialog)", contexts: ["link", "video", "audio", "image"] });
    chrome.contextMenus.create({ id: "draco-all", title: "Download all links with Draco", contexts: ["page", "selection"] });
    chrome.contextMenus.create({ id: "draco-video", title: "Download video from this page (yt-dlp)", contexts: ["page", "video"] });
    chrome.contextMenus.create({ id: "draco-grab", title: "Grab this site with Draco", contexts: ["page"] });
  });
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  const referer = (tab && tab.url) || "";
  if (info.menuItemId === "draco-link" || info.menuItemId === "draco-quick") {
    const url = info.linkUrl || info.srcUrl;
    const quick = info.menuItemId === "draco-quick";
    if (url && isVideoPage(url)) sendToDraco(url, { referer, kind: "ytdlp", silent: quick || state.quick });
    else if (url) sendToDraco(url, { referer, silent: quick || state.quick });
  } else if (info.menuItemId === "draco-all") {
    chrome.tabs.sendMessage(tab.id, { type: "draco-collect", selection: !!info.selectionText }, async (res) => {
      if (chrome.runtime.lastError || !res) return;
      native({ cmd: "links", urls: res.links, referer, title: `Links from ${tab.title || referer}`,
               cookies: await cookiesFor(referer), user_agent: navigator.userAgent });
    });
  } else if (info.menuItemId === "draco-video") {
    sendToDraco(info.pageUrl || referer, { kind: "ytdlp", referer });
  } else if (info.menuItemId === "draco-grab") {
    native({ cmd: "grab", url: info.pageUrl || referer });
  }
});

// ---------------------------------------------------------------- messages from popup/content
chrome.runtime.onMessage.addListener((msg, sender, reply) => {
  (async () => {
    if (msg.type === "draco-download") {
      const tabUrl = (sender.tab && sender.tab.url) || msg.referer || "";
      reply(await sendToDraco(msg.url, {
        referer: tabUrl, kind: msg.kind, filename: msg.filename, description: msg.title,
        quality: msg.quality, silent: msg.silent !== undefined ? msg.silent : state.quick,
        subs: msg.kind === "ytdlp" ? (msg.subs !== undefined ? msg.subs : state.subs) : undefined,
        sub_lang: SUB_LANG,
      }));
    } else if (msg.type === "draco-media-list") {
      const tabId = msg.tabId ?? (sender.tab && sender.tab.id);
      reply({ list: media[tabId] || [] });
    } else if (msg.type === "draco-ping") {
      reply(await native({ cmd: "ping" }));
    } else if (msg.type === "draco-quick-capture") {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      await quickCapture(tab);
      reply({ ok: true });
    } else if (msg.type === "draco-pair") {
      reply(await pairWithDraco());
    } else if (msg.type === "draco-show") {
      reply(await native({ cmd: "show" }));
    } else {
      reply({ ok: false });
    }
  })();
  return true;
});

// ---------------------------------------------------------------- quick capture shortcut
function flash(tabId, ok) {
  chrome.action.setBadgeText({ tabId, text: ok ? "✓" : "!" });
  chrome.action.setBadgeBackgroundColor({ tabId, color: ok ? "#26a269" : "#c01c28" });
  setTimeout(() => {
    const n = (media[tabId] || []).length;
    chrome.action.setBadgeText({ tabId, text: n ? String(n) : "" });
    chrome.action.setBadgeBackgroundColor({ tabId, color: "#3584e4" });
  }, 2500);
}

async function quickCapture(tab) {
  if (!tab || !tab.url) return;
  let reply;
  if (isVideoPage(tab.url)) {
    reply = await sendToDraco(tab.url, { kind: "ytdlp", quality: "best", silent: true, referer: tab.url,
                                         description: tab.title, subs: state.subs, sub_lang: SUB_LANG });
  } else {
    const list = (media[tab.id] || []).slice().sort((a, b) =>
      (b.type === "HLS" || b.type === "DASH") - (a.type === "HLS" || a.type === "DASH") || (b.size || 0) - (a.size || 0));
    if (!list.length) { flash(tab.id, false); return; }
    const m = list[0];
    reply = await sendToDraco(m.url, { referer: tab.url, silent: true, description: tab.title,
                                       kind: m.type === "DASH" ? "ffmpeg" : undefined });
  }
  flash(tab.id, reply && reply.ok);
}

chrome.commands.onCommand.addListener(async (command, tab) => {
  if (command !== "quick-capture") return;
  if (!tab) [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  quickCapture(tab);
});
