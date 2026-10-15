const $ = (id) => document.getElementById(id);

function fmtSize(n) {
  if (!n) return "";
  const u = ["B", "KB", "MB", "GB"];
  let i = 0;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return `${n.toFixed(i ? 1 : 0)} ${u[i]}`;
}

function refreshStatus() {
  chrome.runtime.sendMessage({ type: "draco-ping" }, (r) => {
    const s = $("status");
    $("pairbox").hidden = !(r && r.needPair);
    if (r && r.ok) { s.textContent = `connected · v${r.version || "?"}`; s.className = "status ok"; }
    else if (r && r.needPair) { s.textContent = "not connected"; s.className = "status bad"; }
    else { s.textContent = "Draco not reachable"; s.className = "status bad"; s.title = (r && r.error) || ""; }
  });
}
refreshStatus();
$("pair").addEventListener("click", () => {
  $("pair").disabled = true;
  $("pairmsg").textContent = "Switch to Draco and click Allow…";
  chrome.runtime.sendMessage({ type: "draco-pair" }, (r) => {
    $("pair").disabled = false;
    $("pairmsg").textContent = r && r.ok ? "Connected." : `Not connected: ${(r && r.error) || "unknown error"}`;
    refreshStatus();
  });
});

chrome.storage.local.get({ capture: true, exts: "", minKB: 0, quick: false, subs: false }, (v) => {
  $("subs").checked = v.subs;
  $("capture").checked = v.capture;
  $("quick").checked = v.quick;
  $("exts").value = v.exts;
  $("minkb").value = v.minKB;
});
$("capture").addEventListener("change", (e) => chrome.storage.local.set({ capture: e.target.checked }));
$("quick").addEventListener("change", (e) => chrome.storage.local.set({ quick: e.target.checked }));
$("subs").addEventListener("change", (e) => chrome.storage.local.set({ subs: e.target.checked }));
$("quicknow").addEventListener("click", () => {
  $("quicknow").disabled = true;
  chrome.runtime.sendMessage({ type: "draco-quick-capture" }, () => window.close());
});
$("exts").addEventListener("change", (e) => chrome.storage.local.set({ exts: e.target.value.trim() }));
$("minkb").addEventListener("change", (e) => chrome.storage.local.set({ minKB: parseInt(e.target.value || "0", 10) }));
$("show").addEventListener("click", () => chrome.runtime.sendMessage({ type: "draco-show" }));

chrome.tabs.query({ active: true, currentWindow: true }, ([tab]) => {
  if (!tab) return;
  $("ytdlp").addEventListener("click", () => {
    chrome.runtime.sendMessage({ type: "draco-download", url: tab.url, kind: "ytdlp", referer: tab.url, title: tab.title });
    window.close();
  });
  let lastKey = "";
  const sent = new Set();
  function render() {
    chrome.runtime.sendMessage({ type: "draco-media-list", tabId: tab.id }, (res) => {
      const rows = DracoMediaUI.rows((res && res.list) || []);
      const key = JSON.stringify(rows.map((r) => [r.title, r.detail]));
      if (!rows.length || key === lastKey) return;
      lastKey = key;
      const box = $("media");
      box.innerHTML = "";
      rows.forEach((r) => {
        const row = document.createElement("div");
        row.className = "item";
        const tag = document.createElement("b");
        tag.className = "tag";
        tag.textContent = r.tag;
        const span = document.createElement("span");
        const t = document.createElement("strong");
        t.textContent = r.title;
        const d = document.createElement("small");
        d.textContent = r.detail;
        span.append(t, document.createElement("br"), d);
        span.title = r.msg.url;
        const b = document.createElement("button");
        const id = r.msg.url + "|" + (r.msg.quality || "");
        b.textContent = sent.has(id) ? "Sent ✓" : "Download";
        b.disabled = sent.has(id);
        b.addEventListener("click", () => {
          chrome.runtime.sendMessage(Object.assign({ type: "draco-download", referer: tab.url, title: tab.title }, r.msg),
                                     (rep) => { b.textContent = rep && rep.ok ? "Sent ✓" : "Failed"; });
          sent.add(id);
          b.disabled = true;
        });
        row.append(tag, span, b);
        box.appendChild(row);
      });
    });
  }
  render();
  setInterval(render, 1000);   // HLS details arrive a moment later
});
