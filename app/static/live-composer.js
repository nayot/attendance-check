// "Ask the class" dialog, used on the attendance list and on the class screen.
// On success it fires a `live-started` event on window with the new activity.
window.LiveComposer = (() => {
  const dlg = document.getElementById("composer");
  const { base, session: sid, csrf } = dlg.dataset;
  const { COLORS, shape, t } = window.LiveKit;
  const $ = (id) => document.getElementById(id);
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

  function open(kind) {
    form.kind.value = kind === "text" ? "text" : "vote";
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
    const res = await fetch(`${base}/sessions/${sid}/live`, {
      method: "POST",
      headers: { "X-CSRF-Token": csrf, Accept: "application/json" },
      body: new URLSearchParams(new FormData(form)),
    });
    if (!res.ok) {
      $("c-error").textContent = await res.text();
      $("c-error").hidden = false;
      return;
    }
    const data = await res.json();
    dlg.close();
    window.dispatchEvent(new CustomEvent("live-started", { detail: data }));
  };

  return { open };
})();
