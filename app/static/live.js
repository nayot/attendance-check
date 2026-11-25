// Student page for live votes and short answers. Polls the server every 2 s.
(() => {
  const root = document.getElementById("live");
  const join = root.dataset.join;
  const csrf = root.dataset.csrf;
  const { COLORS, INKS, shape, t } = window.LiveKit;
  const $ = (id) => document.getElementById(id);
  let current = null;   // activity shown
  let last = "";        // last poll payload, to skip re-rendering
  let busy = false;
  let timer = null;

  function show(view) {
    for (const v of ["v-wait", "v-ended", "v-question"]) $(v).hidden = v !== view;
  }

  function error(msg) {
    $("live-error").hidden = !msg;
    $("live-error").textContent = msg || "";
  }

  async function poll() {
    try {
      const res = await fetch(`${join}/poll`, { headers: { Accept: "application/json" } });
      if (res.status === 401) { location.reload(); return; }
      if (!res.ok) return;
      const text = await res.text();
      if (text !== last) { last = text; render(JSON.parse(text)); }
    } catch (e) { /* offline for a moment; try again next tick */ }
  }

  async function send(path, body) {
    if (busy) return;
    busy = true;
    error("");
    try {
      const res = await fetch(`${join}/${path}`, {
        method: "POST",
        headers: { "X-CSRF-Token": csrf, Accept: "application/json" },
        body: new URLSearchParams(body),
      });
      if (!res.ok) { error(await res.text()); return false; }
      const text = await res.text();
      last = text;
      render(JSON.parse(text));
      if (navigator.vibrate) navigator.vibrate(30);
      return true;
    } catch (e) {
      error(t("No connection. Try again."));
      return false;
    } finally {
      busy = false;
    }
  }

  function render(data) {
    if (data.ended) { show("v-ended"); clearInterval(timer); return; }
    const a = data.activity;
    if (!a) { current = null; show("v-wait"); return; }
    const fresh = !current || current.id !== a.id;
    current = a;
    show("v-question");
    if (fresh) {
      error("");
      $("q-input").value = "";
      $("v-question").classList.remove("pop");
      void $("v-question").offsetWidth;
      $("v-question").classList.add("pop");
    }
    $("q-kind").textContent = a.kind === "vote" ? t("Vote") : t("Short answer");
    $("q-text").textContent = a.question;
    a.kind === "vote" ? renderVote(a) : renderText(a);
  }

  function status(text, cls = "") {
    $("q-status").className = `live-status ${cls}`;
    $("q-status").textContent = text;
  }

  function renderVote(a) {
    $("q-form").hidden = true;
    $("q-mine").replaceChildren();
    const voted = a.mine !== null && a.mine !== undefined;
    if (!a.open) status(t("Voting is closed."), "closed");
    else if (voted) status("✓ " + t("Vote sent. You can change it until voting closes."), "ok");
    else status(t("Tap your answer"));
    const box = $("q-options");
    box.classList.toggle("many", a.options.length > 4);
    box.replaceChildren(...a.options.map((label, i) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "vote-tile" + (a.mine === i ? " chosen" : "") + (voted && a.mine !== i ? " faded" : "");
      b.style.setProperty("--tile", COLORS[i % COLORS.length]);
      b.style.setProperty("--ink", INKS[i % INKS.length]);
      b.disabled = !a.open;
      b.innerHTML = `${shape(i)}<span></span>${a.mine === i ? '<b class="tick">✓</b>' : ""}`;
      b.querySelector("span").textContent = label;
      b.onclick = () => send("vote", { activity: a.id, option: i });
      return b;
    }));
  }

  function renderText(a) {
    $("q-options").replaceChildren();
    const left = a.max_answers - a.mine.length;
    const form = $("q-form");
    form.hidden = !a.open || left <= 0;
    $("q-input").maxLength = a.max_len;
    $("q-left").textContent = t("You can send {n} more", { n: left });
    if (!a.open) status(t("Answers are closed."), "closed");
    else if (left <= 0) status("✓ " + t("Thanks! All your answers are in."), "ok");
    else if (a.mine.length) status("✓ " + t("Sent! Add another if you like."), "ok");
    else status("");
    $("q-mine").replaceChildren(...a.mine.map((text) => {
      const li = document.createElement("li");
      li.textContent = text;
      return li;
    }));
  }

  $("q-form").onsubmit = async (e) => {
    e.preventDefault();
    const text = $("q-input").value.trim();
    if (!text || !current) return;
    if (await send("answer", { activity: current.id, text })) $("q-input").value = "";
    $("q-input").focus();
  };

  if (root.dataset.ended === "1") { show("v-ended"); return; }
  show("v-wait");
  poll();
  timer = setInterval(poll, 2000);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) poll(); });
})();
