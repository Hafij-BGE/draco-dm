// Shared by popup.js and content.js: turn detected media into readable rows.
// eslint-disable-next-line no-unused-vars
const DracoMediaUI = (() => {
  function fmtSize(n) {
    if (!n) return "";
    const u = ["B", "KB", "MB", "GB"];
    let i = 0;
    while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
    return `${n.toFixed(i >= 2 ? 1 : 0)} ${u[i]}`;
  }

  function fmtDur(s) {
    if (!s) return "";
    s = Math.round(s);
    const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
    return h ? `${h}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}` : `${m}:${String(sec).padStart(2, "0")}`;
  }

  function fileName(url) {
    try {
      return decodeURIComponent(new URL(url).pathname.split("/").pop() || "video");
    } catch (e) {
      return "video";
    }
  }

  function quality(h) {
    if (!h) return "Auto";
    if (h >= 2160) return `${h}p 4K`;
    if (h >= 1440) return `${h}p 2K`;
    if (h >= 720) return `${h}p HD`;
    return `${h}p`;
  }

  /** -> [{tag, title, detail, msg}] where msg is what to send to Draco. */
  function rows(list) {
    const out = [];
    for (const m of (list || []).slice().reverse()) {
      const parts = (...xs) => xs.filter(Boolean).join(" · ");
      if (m.variants && m.variants.length) {
        for (const v of m.variants) {
          out.push({
            tag: "HLS", title: quality(v.height),
            detail: parts(v.size ? `~${fmtSize(v.size)}` : "size unknown", fmtDur(m.duration),
                          v.width && v.height ? `${v.width}×${v.height}` : ""),
            // yt-dlp picks this quality from the master playlist and merges separate audio.
            msg: { url: m.url, kind: "ytdlp", quality: v.height ? String(v.height) : "best" },
          });
        }
      } else if (m.type === "HLS") {
        out.push({
          tag: "HLS", title: fileName(m.url),
          detail: parts(m.size ? `~${fmtSize(m.size)}` : (m.analyzed === undefined ? "checking…" : "size unknown"),
                        fmtDur(m.duration), m.encrypted ? "encrypted" : ""),
          msg: { url: m.url, kind: "ytdlp" },
        });
      } else if (m.type === "DASH") {
        out.push({ tag: "DASH", title: fileName(m.url), detail: "stream", msg: { url: m.url, kind: "ffmpeg" } });
      } else {
        const t = (m.type || "").split(";")[0];
        out.push({
          tag: (t.split("/")[1] || "media").toUpperCase(), title: fileName(m.url),
          detail: parts(m.size ? fmtSize(m.size) : "size unknown", t.startsWith("audio") ? "audio" : ""),
          msg: { url: m.url },
        });
      }
    }
    return out;
  }

  return { rows, fmtSize, fmtDur };
})();
