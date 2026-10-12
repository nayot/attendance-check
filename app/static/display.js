// Live QR display: rotating code, running check-in list and phase controls.
(() => {
  const app = document.getElementById("app");
  const base = app.dataset.base;
  const sid = app.dataset.session;
  const csrf = app.dataset.csrf;
  const $ = (id) => document.getElementById(id);
  const t = (key, params = {}) =>
    (window.I18N[key] ?? key).replace(/\{(\w+)\}/g, (m, name) => params[name] ?? m);

  let state = null;      // session state from /state
  let viewPhase = null;  // phase whose list is shown
  let qrDeadline = 0;
  let qrInterval = 15;

  async function post(path, body) {
    const res = await fetch(base + path, {
      method: "POST",
      headers: { "X-CSRF-Token": csrf },
      body: body ? new URLSearchParams(body) : undefined,
    });
    if (!res.ok) alert(await res.text());
    await refresh();
  }

  async function refresh() {
    const res = await fetch(`${base}/sessions/${sid}/state`, { headers: { Accept: "application/json" } });
    if (res.redirected || !res.ok) { location.reload(); return; }
    state = await res.json();
    if (state.closed) { location.href = `${base}/sessions/${sid}/report`; return; }
    if (!state.phases.some((p) => p.id === viewPhase)) viewPhase = null;
    viewPhase = state.active_phase ?? viewPhase ?? state.phases[0].id;
    render();
  }

  function phase(id) { return state.phases.find((p) => p.id === id); }

  function render() {
    const active = state.active_phase ? phase(state.active_phase) : null;

    // Phase tabs
    const nav = $("phases");
    nav.replaceChildren(...state.phases.map((p) => {
      const b = document.createElement("button");
      b.className = `phase ${p.state}${p.id === viewPhase ? " viewing" : ""}`;
      b.innerHTML = `<span></span><b></b><em></em>`;
      b.children[0].textContent = p.label;
      b.children[1].textContent = p.count;
      b.children[2].textContent = t({ pending: "not started", open: "open", paused: "paused", closed: "closed" }[p.state]);
      b.title = t(p.state === "open" || p.state === "paused" ? "Showing this check" : "Click to open this check");
      b.onclick = () => {
        if (p.state === "pending" || p.state === "closed") {
          const ask = t(p.state === "closed" ? 'Reopen "{label}"?' : 'Start "{label}"?', { label: p.label });
          const note = active ? " " + t('This closes "{label}".', { label: active.label }) : "";
          if (!confirm(ask + note)) return;
          post(`/sessions/${sid}/phases/${p.id}/open`);
        } else {
          viewPhase = p.id;
          render();
        }
      };
      return b;
    }));

    // Pause / resume
    const pause = $("btn-pause");
    pause.disabled = !active;
    pause.textContent = active && active.state === "paused" ? "▶ " + t("Resume") : "❚❚ " + t("Pause");
    pause.classList.toggle("warn", !!active && active.state === "paused");

    $("btn-checkout").hidden = state.phases.some((p) => p.kind === "checkout");

    // QR area
    const overlay = $("qr-overlay");
    $("qr-label").textContent = active ? active.label : t("No check open");
    if (!active) {
      overlay.hidden = false;
      overlay.textContent = t("Choose a check above to open it");
    } else if (active.state === "paused") {
      overlay.hidden = false;
      overlay.textContent = t("Paused");
    } else {
      overlay.hidden = true;
    }
    $("qr-box").classList.toggle("off", !active || active.state !== "open");
    $("qr-timer").style.visibility = active && active.state === "open" ? "" : "hidden";

    // Running list
    const p = phase(viewPhase);
    $("list-title").textContent = p ? p.label : t("Checked in");
    $("count").textContent = p ? p.count : 0;
    $("list").replaceChildren(...(p ? p.checkins.map(row) : []));
  }

  function row(c, fresh) {
    const li = document.createElement("li");
    if (fresh) li.className = "fresh";
    li.innerHTML = `<span class="name"></span> <span class="email"></span><time></time>`;
    li.children[0].textContent = c.name || c.email;
    li.children[1].textContent = c.name ? `<${c.email}>` : "";
    li.children[2].textContent = c.time;
    return li;
  }

  function onCheckin(c) {
    const p = state && phase(c.phase_id);
    if (!p || p.checkins.some((x) => x.id === c.id)) return;
    p.checkins.unshift(c);
    p.count += 1;
    if (c.phase_id === viewPhase) {
      $("count").textContent = p.count;
      $("list").prepend(row(c, true));
      const tab = [...$("phases").children][state.phases.indexOf(p)];
      if (tab) tab.children[1].textContent = p.count;
    } else {
      render();
    }
  }

  function onQr(d) {
    if (!d.phase_id) { $("qr").replaceChildren(); return; }
    $("qr").innerHTML = d.svg;
    $("qr").dataset.url = d.url;
    qrInterval = d.interval;
    qrDeadline = Date.now() + d.expires_in * 1000;
  }

  // Live updates
  function connect() {
    const es = new EventSource(`${base}/sessions/${sid}/events`);
    es.onopen = () => { $("conn").className = "conn on"; refresh(); };
    es.onerror = () => { $("conn").className = "conn off"; };
    es.addEventListener("qr", (e) => onQr(JSON.parse(e.data)));
    es.addEventListener("checkin", (e) => onCheckin(JSON.parse(e.data)));
    es.addEventListener("state", () => refresh());
  }

  // Buttons
  $("btn-pause").onclick = () => {
    const active = state && state.active_phase && phase(state.active_phase);
    if (!active) return;
    post(`/sessions/${sid}/phases/${active.id}/${active.state === "paused" ? "resume" : "pause"}`);
  };
  $("btn-mid").onclick = () => {
    if (confirm(t("Add a mid-class check and open it now?")))
      post(`/sessions/${sid}/phases`, { kind: "mid", open_now: "true" });
  };
  $("btn-checkout").onclick = () => {
    if (confirm(t("Add a check-out and open it now?")))
      post(`/sessions/${sid}/phases`, { kind: "checkout", open_now: "true" });
  };
  $("btn-full").onclick = () => {
    if (document.fullscreenElement) document.exitFullscreen();
    else document.documentElement.requestFullscreen();
  };
  $("close-form").onsubmit = (e) => {
    if (!confirm(t("Close this session? Students can no longer check in."))) e.preventDefault();
  };
  document.addEventListener("keydown", (e) => {
    if (e.target.tagName === "INPUT") return;
    if (e.key === " ") { e.preventDefault(); $("btn-pause").click(); }
    if (e.key === "f") $("btn-full").click();
  });

  // Clock and QR countdown bar
  const fmt = new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23", timeZone: window.TZ });
  setInterval(() => {
    $("clock").textContent = fmt.format(new Date());
    const left = Math.max(0, qrDeadline - Date.now()) / (qrInterval * 1000);
    $("qr-timer-bar").style.width = `${Math.min(1, left) * 100}%`;
  }, 200);

  refresh().then(connect);
})();
