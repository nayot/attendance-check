// Class screen: live votes (bar or pie chart) and short answers (grouped answer cloud).
(() => {
  const app = document.getElementById("app");
  const base = app.dataset.base;
  const sid = app.dataset.session;
  const csrf = app.dataset.csrf;
  const { COLORS, shape, t } = window.LiveKit;
  const $ = (id) => document.getElementById(id);
  // Darker steps of the same hues, for words in the answer cloud on white.
  const INK_COLORS = ["#1b64be", "#c4531a", "#00876c", "#a86f00", "#c2457a", "#006c10", "#5236c4", "#c62f30"];
  const SVGNS = "http://www.w3.org/2000/svg";

  let act = null;        // current activity results
  let built = "";        // key of the chart structure in the DOM
  let qrLoaded = false;

  async function post(path, body) {
    const res = await fetch(`${base}/sessions/${sid}/live${path}`, {
      method: "POST",
      headers: { "X-CSRF-Token": csrf, Accept: "application/json" },
      body: body,
    });
    if (!res.ok) throw new Error(await res.text());
    update((await res.json()).activity);
  }

  async function load() {
    const res = await fetch(`${base}/sessions/${sid}/live`, { headers: { Accept: "application/json" } });
    if (!res.ok) return;
    const data = await res.json();
    $("live-qr").innerHTML = data.join_qr;
    $("live-qr").title = data.join_url;
    qrLoaded = true;
    update(data.activity);
  }

  // ---- Rendering --------------------------------------------------------

  function update(a) {
    // Snapshots can arrive out of order; keep the newest of the same question.
    if (a && act && a.id === act.id && a.rev < act.rev) return;
    const prev = act;
    act = a;
    app.classList.toggle("live-mode", !!a);
    $("live-stage").hidden = !a;
    $("live-controls").hidden = !a;
    $("btn-live").textContent = "✦ " + t(a ? "New question" : "Ask the class");
    if (!a) { built = ""; return; }
    if (!qrLoaded) load();
    if (!prev || prev.id !== a.id) built = "";

    $("live-kind").innerHTML = a.kind === "vote" ? `📊 ${t("Vote")}` : `💬 ${t("Short answer")}`;
    $("live-question").textContent = a.question;
    $("live-people").textContent = a.people;
    $("live-state").textContent = a.open ? t("Answers open") : t("Answers closed");
    $("live-state").className = `live-state ${a.open ? "open" : "closed"}`;
    $("btn-live-open").textContent = a.open ? "❚❚ " + t("Stop answers") : "▶ " + t("Reopen answers");
    $("chart-toggle").hidden = a.kind !== "vote";
    $("btn-bar").classList.toggle("on", a.chart === "bar");
    $("btn-pie").classList.toggle("on", a.chart === "pie");

    if (a.kind === "vote") a.chart === "pie" ? pie(a) : bars(a);
    else cloud(a);
  }

  const pct = (n, total) => (total ? Math.round((n / total) * 100) : 0);

  function bars(a) {
    const box = $("live-results");
    const key = `bar:${a.id}`;
    if (built !== key) {
      built = key;
      box.className = "live-results bars";
      box.replaceChildren(...a.options.map((o, i) => {
        const row = document.createElement("div");
        row.className = "bar-row";
        row.style.setProperty("--c", COLORS[i % COLORS.length]);
        row.innerHTML = `<div class="bar-label">${shape(i)}<span></span></div>
          <div class="bar-track"><div class="bar-fill"></div></div>
          <div class="bar-val"><b>0</b><small>0%</small></div>`;
        row.querySelector(".bar-label span").textContent = o.label;
        return row;
      }));
    }
    const lead = Math.max(...a.options.map((o) => o.count));
    [...box.children].forEach((row, i) => {
      const o = a.options[i];
      // The full track is 100% of the votes.
      row.querySelector(".bar-fill").style.width = `${a.total ? (o.count / a.total) * 100 : 0}%`;
      row.querySelector(".bar-val b").textContent = o.count;
      row.querySelector(".bar-val small").textContent = `${pct(o.count, a.total)}%`;
      row.classList.toggle("lead", o.count > 0 && o.count === lead);
      row.title = `${o.label}: ${o.count} (${pct(o.count, a.total)}%)`;
    });
  }

  function pie(a) {
    const box = $("live-results");
    const key = `pie:${a.id}`;
    const R = 80, C = 2 * Math.PI * R;
    if (built !== key) {
      built = key;
      box.className = "live-results pie";
      box.innerHTML = `<div class="pie-wrap"><svg viewBox="0 0 220 220" class="pie-svg" role="img">
          <circle class="pie-track" cx="110" cy="110" r="${R}"/></svg>
          <div class="pie-center"><b>0</b><span>${t("votes")}</span></div></div>
        <ul class="pie-legend"></ul>`;
      const svg = box.querySelector("svg");
      const legend = box.querySelector(".pie-legend");
      a.options.forEach((o, i) => {
        const c = document.createElementNS(SVGNS, "circle");
        c.setAttribute("class", "pie-seg");
        c.setAttribute("cx", 110); c.setAttribute("cy", 110); c.setAttribute("r", R);
        c.setAttribute("stroke", COLORS[i % COLORS.length]);
        c.setAttribute("stroke-dasharray", `0 ${C}`);
        c.appendChild(document.createElementNS(SVGNS, "title"));
        svg.appendChild(c);
        const li = document.createElement("li");
        li.style.setProperty("--c", COLORS[i % COLORS.length]);
        li.innerHTML = `${shape(i)}<span class="pl"></span><b>0</b><small>0%</small>`;
        li.querySelector(".pl").textContent = o.label;
        legend.appendChild(li);
      });
    }
    box.querySelector(".pie-center b").textContent = a.total;
    const segs = box.querySelectorAll(".pie-seg");
    const items = box.querySelectorAll(".pie-legend li");
    const nonzero = a.options.filter((o) => o.count > 0).length;
    const gap = nonzero > 1 ? 3 : 0;   // white gap between slices
    let start = 0;
    a.options.forEach((o, i) => {
      const len = a.total ? (o.count / a.total) * C : 0;
      const seg = segs[i];
      const drawn = Math.max(0, len - gap);
      seg.setAttribute("stroke-dasharray", `${drawn} ${C - drawn}`);
      seg.setAttribute("stroke-dashoffset", `${-start}`);
      seg.querySelector("title").textContent = `${o.label}: ${o.count} (${pct(o.count, a.total)}%)`;
      start += len;
      items[i].querySelector("b").textContent = o.count;
      items[i].querySelector("small").textContent = `${pct(o.count, a.total)}%`;
      items[i].classList.toggle("zero", o.count === 0);
    });
    box.classList.toggle("empty", !a.total);
  }

  function hash(text) {
    let h = 0;
    for (const ch of text) h = (h * 31 + ch.codePointAt(0)) >>> 0;
    return h;
  }

  function cloud(a) {
    const box = $("live-results");
    const key = `cloud:${a.id}`;
    if (built !== key) {
      built = key;
      box.className = "live-results cloud";
      box.replaceChildren();
    }
    const groups = a.groups.slice(0, 60);
    if (!groups.length) {
      box.classList.add("empty");
      box.innerHTML = `<p class="cloud-empty">${t("Answers will appear here")}</p>`;
      return;
    }
    box.classList.remove("empty");
    box.querySelector(".cloud-empty")?.remove();
    const maxc = groups[0].count;
    // Biggest answers in the middle, smaller ones alternating outwards.
    const ordered = [];
    groups.forEach((g, i) => (i % 2 ? ordered.push(g) : ordered.unshift(g)));
    const old = new Map([...box.children].map((el) => [el.dataset.text, el]));
    const els = ordered.map((g) => {
      let el = old.get(g.text);
      if (!el) {
        el = document.createElement("span");
        el.className = "word pop";
        el.dataset.text = g.text;
        el.innerHTML = "<span></span><sup></sup>";
        el.firstChild.textContent = g.text;
        el.style.color = INK_COLORS[hash(g.text) % INK_COLORS.length];
        el.style.setProperty("--tilt", `${(hash(g.text) % 5) - 2}deg`);
      } else if (el.dataset.count !== String(g.count)) {
        el.classList.remove("pop", "grow");
        void el.offsetWidth;
        el.classList.add("grow");
      }
      el.dataset.count = g.count;
      const size = maxc > 1 ? 1.2 + 3.6 * Math.sqrt((g.count - 1) / (maxc - 1)) : 2;
      el.style.fontSize = `${size}rem`;
      el.style.fontWeight = g.count === maxc && maxc > 1 ? 800 : 600;
      el.querySelector("sup").textContent = g.count > 1 ? `×${g.count}` : "";
      el.title = `${g.text} (${g.count})`;
      return el;
    });
    box.replaceChildren(...els);
  }

  // ---- Composer ---------------------------------------------------------

  const dlg = $("composer");
  const form = $("composer-form");
  const FILLS = {
    yesno: [t("Yes"), t("No")],
    tf: [t("True"), t("False")],
    abcd: ["A", "B", "C", "D"],
    scale: ["1", "2", "3", "4", "5"],
  };

  function optionRow(value = "") {
    const li = document.createElement("li");
    const i = $("c-options").children.length;
    li.style.setProperty("--c", COLORS[i % COLORS.length]);
    li.innerHTML = `${shape(i)}<input name="option" maxlength="80" autocomplete="off"><button type="button" class="link x" aria-label="${t("Remove")}">×</button>`;
    const input = li.querySelector("input");
    input.value = value;
    input.placeholder = t("Choice {n}", { n: i + 1 });
    li.querySelector(".x").onclick = () => {
      if ($("c-options").children.length > 2) { li.remove(); renumber(); }
    };
    return li;
  }

  function renumber() {
    [...$("c-options").children].forEach((li, i) => {
      li.style.setProperty("--c", COLORS[i % COLORS.length]);
      li.querySelector("svg").outerHTML = shape(i);
      li.querySelector("input").placeholder = t("Choice {n}", { n: i + 1 });
    });
    $("c-add").hidden = $("c-options").children.length >= 8;
  }

  function setOptions(values) {
    $("c-options").replaceChildren();
    values.forEach((v) => $("c-options").appendChild(optionRow(v)));
    renumber();
  }

  function syncKind() {
    const vote = form.kind.value === "vote";
    $("c-vote").hidden = !vote;
    $("c-text-note").hidden = vote;
    $("c-options").querySelectorAll("input").forEach((i) => (i.disabled = !vote));
  }

  function openComposer() {
    if (act && act.kind === "text") form.kind.value = "text";
    form.question.value = "";
    setOptions(["", "", "", ""]);
    $("c-error").hidden = true;
    syncKind();
    dlg.showModal();
    form.question.focus();
  }

  form.querySelectorAll('input[name="kind"]').forEach((r) => (r.onchange = syncKind));
  form.querySelectorAll(".chip").forEach((c) => (c.onclick = () => setOptions(FILLS[c.dataset.fill])));
  $("c-add").onclick = () => {
    if ($("c-options").children.length < 8) {
      $("c-options").appendChild(optionRow());
      renumber();
      $("c-options").lastElementChild.querySelector("input").focus();
    }
  };
  $("c-cancel").onclick = () => dlg.close();
  form.question.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); }
  });
  form.onsubmit = async (e) => {
    e.preventDefault();
    const body = new URLSearchParams(new FormData(form));
    try {
      await post("", body);
      dlg.close();
    } catch (err) {
      $("c-error").textContent = err.message;
      $("c-error").hidden = false;
    }
  };

  // ---- Toolbar ----------------------------------------------------------

  const act_ = (path) => post(path).catch((err) => alert(err.message));
  $("btn-live").onclick = openComposer;
  $("btn-bar").onclick = () => act_("/bar");
  $("btn-pie").onclick = () => act_("/pie");
  $("btn-live-open").onclick = () => act_(act && act.open ? "/close" : "/open");
  $("btn-live-stop").onclick = () => act_("/stop");

  window.addEventListener("live-update", (e) => update(e.detail.activity));
  window.addEventListener("live-refresh", load);
  load();
})();
