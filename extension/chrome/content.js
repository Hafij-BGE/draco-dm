// Draco content script: link collection and the "Download this video" panel.
(() => {
  if (window.__dracoLoaded) return;
  window.__dracoLoaded = true;

  chrome.runtime.onMessage.addListener((msg, sender, reply) => {
    if (msg.type === "draco-collect") {
      reply({ links: collectLinks(msg.selection) });
    } else if (msg.type === "draco-media") {
      mediaList = msg.list || [];
      attachToVideos();
    }
  });

  function collectLinks(selectionOnly) {
    let root = document;
    const sel = window.getSelection();
    const urls = new Set();
    const add = (u) => {
      try {
        const abs = new URL(u, location.href);
        if (/^(https?|ftp):$/.test(abs.protocol)) urls.add(abs.href.split("#")[0]);
      } catch (e) { /* ignore */ }
    };
    if (selectionOnly && sel && sel.rangeCount) {
      const frag = sel.getRangeAt(0).cloneContents();
      frag.querySelectorAll("a[href]").forEach((a) => add(a.getAttribute("href")));
      return [...urls];
    }
    root.querySelectorAll("a[href]").forEach((a) => add(a.href));
    root.querySelectorAll("video[src], audio[src], source[src], img[src]").forEach((e) => add(e.src));
    return [...urls];
  }

  // ------------------------------------------------------------ video panel
  const YTDLP_SITES = /(^|\.)(youtube\.com|youtu\.be|vimeo\.com|dailymotion\.com|tiktok\.com|twitch\.tv|facebook\.com|instagram\.com|x\.com|twitter\.com|reddit\.com|soundcloud\.com|bilibili\.com|bilibili\.tv|streamable\.com|rumble\.com|vk\.com|ok\.ru)$/i;
  const onVideoSite = YTDLP_SITES.test(location.hostname);
  function isVideoPage() {
    if (!onVideoSite) return false;
    if (/(^|\.)youtube\.com$/i.test(location.hostname)) return /^\/(watch|shorts\/|live\/|embed\/)/.test(location.pathname);
    return true;
  }
  const QUALITIES = [["best", "Best quality"], ["1080", "1080p"], ["720", "720p"], ["480", "480p"],
                     ["360", "360p"], ["audio", "Audio only (MP3)"], ["subs", "Subtitles only (.srt)"]];
  let wantSubs = false;
  chrome.storage.local.get({ subs: false }, (v) => { wantSubs = v.subs; });
  let mediaList = [];
  let panel = null;
  let btnLabel = null;
  let current = null;


  function buildPanel() {
    const host = document.createElement("div");
    host.style.cssText = "position:absolute;z-index:2147483647;display:none;";
    const shadow = host.attachShadow({ mode: "closed" });
    shadow.innerHTML = `
      <style>
        .btn{font:600 12px system-ui,sans-serif;background:#3584e4;color:#fff;border:0;border-radius:6px;
             padding:6px 10px;cursor:pointer;box-shadow:0 2px 8px rgba(0,0,0,.35);display:flex;gap:6px;align-items:center}
        .btn:hover{background:#1c71d8}
        .x{background:rgba(0,0,0,.25);border-radius:4px;padding:0 5px;margin-left:4px}
        .menu{display:none;margin-top:4px;background:#fff;color:#222;border-radius:6px;min-width:260px;max-width:420px;
              box-shadow:0 4px 16px rgba(0,0,0,.35);font:12px system-ui,sans-serif;overflow:hidden}
        .menu div{padding:7px 10px;cursor:pointer;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
        .menu div:hover{background:#e8f0fc}
        @media (prefers-color-scheme: dark){.menu{background:#2a2a2e;color:#eee}.menu div:hover{background:#3a4a63}}
      </style>
      <button class="btn" part="btn"><span class="lbl">⬇ Download this video</span><span class="x" title="Hide">✕</span></button>
      <div class="menu"></div>`;
    const btn = shadow.querySelector(".btn");
    host.__menu = shadow.querySelector(".menu");
    btnLabel = shadow.querySelector(".lbl");
    const menu = shadow.querySelector(".menu");
    shadow.querySelector(".x").addEventListener("click", (e) => {
      e.stopPropagation();
      host.style.display = "none";
      host.dataset.dismissed = "1";
    });
    btn.addEventListener("click", (e) => {
      if (!e.isTrusted) return;
      e.stopPropagation();
      menu.innerHTML = "";
      if (isVideoPage()) {
        // Video sites: one click = start downloading in Draco at that quality (quick capture).
        QUALITIES.forEach(([q, label]) => {
          const row = document.createElement("div");
          row.textContent = label;
          row.addEventListener("click", (ev) => {
            if (!ev.isTrusted) return;
            ev.stopPropagation();
            // Opens Draco's confirmation dialog with this quality chosen (instant if Quick capture is on).
            chrome.runtime.sendMessage({ type: "draco-download", url: location.href, kind: "ytdlp", quality: q,
                                         subs: wantSubs, title: document.title }, (r) => sent(r));
            menu.style.display = "none";
          });
          menu.appendChild(row);
        });
        const subsRow = document.createElement("div");
        const paintSubs = () => { subsRow.textContent = `${wantSubs ? "☑" : "☐"} Include subtitles`; };
        paintSubs();
        subsRow.style.borderTop = "1px solid rgba(128,128,128,.3)";
        subsRow.addEventListener("click", (ev) => {
          if (!ev.isTrusted) return;
          ev.stopPropagation();
          wantSubs = !wantSubs;
          chrome.storage.local.set({ subs: wantSubs });
          paintSubs();
        });
        menu.appendChild(subsRow);
        const more = document.createElement("div");
        more.textContent = "More options…";
        more.style.opacity = "0.75";
        more.addEventListener("click", (ev) => {
          if (!ev.isTrusted) return;
          ev.stopPropagation();
          chrome.runtime.sendMessage({ type: "draco-download", url: location.href, kind: "ytdlp", silent: false,
                                       subs: wantSubs, title: document.title }, (r) => sent(r));
          menu.style.display = "none";
        });
        menu.appendChild(more);
        menu.style.display = menu.style.display === "block" ? "none" : "block";
        return;
      }
      DracoMediaUI.rows(mediaList).forEach((r) => {
        const row = document.createElement("div");
        row.textContent = `${r.tag}  ${r.title}  —  ${r.detail}`;
        row.title = r.msg.url;
        row.addEventListener("click", (ev) => {
          if (!ev.isTrusted) return;
          chrome.runtime.sendMessage(Object.assign({ type: "draco-download", title: document.title }, r.msg),
                                     (rep) => sent(rep));
          menu.style.display = "none";
        });
        menu.appendChild(row);
      });
      const yt = document.createElement("div");
      yt.textContent = "Whole page with yt-dlp (YouTube, Vimeo, …)";
      yt.addEventListener("click", (ev) => { if (ev.isTrusted) { send(location.href, "ytdlp"); menu.style.display = "none"; } });
      menu.appendChild(yt);
      menu.style.display = menu.style.display === "block" ? "none" : "block";
    });
    document.documentElement.appendChild(host);
    return host;
  }

  function send(url, kind) {
    chrome.runtime.sendMessage({ type: "draco-download", url, kind, title: document.title }, (r) => sent(r));
  }

  function sent(r) {
    if (!btnLabel) return;
    const old = btnLabel.textContent;
    btnLabel.textContent = r && r.ok ? "✓ Sent to Draco" : "✕ Draco not reachable";
    setTimeout(() => { btnLabel.textContent = old; }, 2500);
  }

  function place(video) {
    if (!panel) panel = buildPanel();
    if (panel.dataset.dismissed) return;
    if (!isVideoPage() && !mediaList.length) {
      panel.style.display = "none";
      return;
    }
    const r = video.getBoundingClientRect();
    if (r.width < 200 || r.height < 120) return;
    panel.style.top = `${window.scrollY + r.top + 8}px`;
    panel.style.left = `${window.scrollX + r.right - 220}px`;
    panel.style.display = "block";
    current = video;
  }

  function attachToVideos() {
    if (!mediaList.length && !isVideoPage()) return;
    document.querySelectorAll("video").forEach((v) => {
      if (v.__draco) return;
      v.__draco = true;
      v.addEventListener("mouseenter", () => place(v));
      v.addEventListener("play", () => place(v));
    });
    const big = [...document.querySelectorAll("video")].sort((a, b) =>
      b.clientWidth * b.clientHeight - a.clientWidth * a.clientHeight)[0];
    if (big) place(big);
  }

  window.addEventListener("scroll", () => { if (current && panel && panel.style.display === "block") place(current); },
    { passive: true });

  // YouTube & co. switch videos without reloading the page: reset the button for every new video.
  let lastUrl = location.href;
  function onNavigate() {
    if (location.href === lastUrl) return;
    lastUrl = location.href;
    mediaList = [];
    current = null;
    if (panel) {
      delete panel.dataset.dismissed;
      panel.style.display = "none";
      const menu = panel.__menu;
      if (menu) menu.style.display = "none";
    }
    if (btnLabel) btnLabel.textContent = "⬇ Download this video";
    // give the site a moment to swap in the new player, then attach to it
    setTimeout(() => {
      chrome.runtime.sendMessage({ type: "draco-media-list" }, (res) => {
        if (chrome.runtime.lastError) return;
        if (res && res.list) mediaList = res.list;
        attachToVideos();
      });
    }, 800);
  }
  window.addEventListener("yt-navigate-finish", onNavigate);   // YouTube's own event
  window.addEventListener("popstate", onNavigate);
  setInterval(onNavigate, 1000);                               // any other single-page site
  let pending = false;   // pages like YouTube mutate constantly: re-check at most twice a second
  new MutationObserver(() => {
    if (pending || !(mediaList.length || isVideoPage())) return;
    pending = true;
    setTimeout(() => { pending = false; attachToVideos(); }, 500);
  })
    .observe(document.documentElement, { childList: true, subtree: true });

  chrome.runtime.sendMessage({ type: "draco-media-list" }, (res) => {
    if (chrome.runtime.lastError) return;
    if (res && res.list && res.list.length) { mediaList = res.list; attachToVideos(); }
  });
  if (isVideoPage()) setTimeout(attachToVideos, 1000);
})();
