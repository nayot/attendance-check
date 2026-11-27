// Class screen: break countdown, with a chime when the break is over.
(() => {
  const app = document.getElementById("app");
  const base = app.dataset.base;
  const sid = app.dataset.session;
  const csrf = app.dataset.csrf;
  const { t } = window.LiveKit;
  const $ = (id) => document.getElementById(id);

  let brk = null;       // {started_at, ends_at} in server seconds
  let skew = 0;         // server clock minus this computer's clock, in ms
  let wasOver = null;   // null until the first tick of a break, so a reload doesn't chime
  const backFmt = new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit", hourCycle: "h23", timeZone: window.TZ });

  async function post(path) {
    const res = await fetch(`${base}/sessions/${sid}/break${path}`, {
      method: "POST",
      headers: { "X-CSRF-Token": csrf, Accept: "application/json" },
    });
    if (!res.ok) { alert(await res.text()); return; }
    update((await res.json()).break);
  }

  async function load() {
    const res = await fetch(`${base}/sessions/${sid}/break`, { headers: { Accept: "application/json" } });
    if (res.ok) update((await res.json()).break);
  }

  function update(b) {
    if (b) skew = b.now * 1000 - Date.now();
    if (!b || !brk || b.started_at !== brk.started_at) wasOver = null;
    brk = b;
    app.classList.toggle("break-mode", !!b);
    $("break-stage").hidden = !b;
    $("break-controls").hidden = !b;
    $("btn-break").hidden = !!b;
    if (b) tick();
  }

  function clock(ms) {
    const s = Math.ceil(ms / 1000);
    const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
    const mm = h ? String(m).padStart(2, "0") : m;
    return `${h ? h + ":" : ""}${mm}:${String(sec).padStart(2, "0")}`;
  }

  function tick() {
    if (!brk) return;
    const now = Date.now() + skew;
    const end = brk.ends_at * 1000;
    const total = Math.max(1, end - brk.started_at * 1000);
    const left = Math.max(0, end - now);
    const over = left <= 0;

    $("break-time").textContent = clock(left);
    $("break-bar").style.width = `${Math.min(1, left / total) * 100}%`;
    $("break-label").textContent = over ? t("Break is over") : "☕ " + t("Break");
    $("break-back").textContent = over ? t("Please take your seats") : t("Back at {time}", { time: backFmt.format(new Date(end)) });
    $("break-stage").classList.toggle("over", over);
    $("break-stage").classList.toggle("soon", !over && left <= 60_000);
    $("btn-break-less").disabled = over;
    $("break-sound").hidden = !!audio && audio.state === "running";

    if (wasOver === false && over) chime();
    wasOver = over;
  }

  // ---- Chime -------------------------------------------------------------
  // Browsers only allow sound after someone has clicked on the page, so the
  // audio is unlocked on the first click or key press.
  let audio = null;
  function unlock() {
    try {
      audio = audio || new (window.AudioContext || window.webkitAudioContext)();
      if (audio.state === "suspended") audio.resume();
    } catch (e) { audio = null; }
  }
  ["pointerdown", "keydown"].forEach((ev) => document.addEventListener(ev, unlock));

  function chime() {
    if (!audio) return;
    const at = audio.currentTime + 0.05;
    [[659.25, 0], [523.25, 0.45], [392.0, 0.9], [523.25, 1.6], [659.25, 2.05]].forEach(([freq, dt]) => {
      const osc = audio.createOscillator();
      const gain = audio.createGain();
      osc.type = "sine";
      osc.frequency.value = freq;
      gain.gain.setValueAtTime(0.0001, at + dt);
      gain.gain.exponentialRampToValueAtTime(0.35, at + dt + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, at + dt + 1.2);
      osc.connect(gain).connect(audio.destination);
      osc.start(at + dt);
      osc.stop(at + dt + 1.3);
    });
  }

  // ---- Toolbar -----------------------------------------------------------
  $("break-sound").onclick = unlock;
  $("btn-break").onclick = () => window.BreakDialog.open();
  $("btn-break-more").onclick = () => post("/more");
  $("btn-break-less").onclick = () => post("/less");
  $("btn-break-end").onclick = () => post("/end");

  window.addEventListener("break-update", (e) => update(e.detail.break));
  window.addEventListener("break-started", (e) => update(e.detail.break));
  window.addEventListener("live-refresh", load);
  setInterval(tick, 250);
  load();
})();
