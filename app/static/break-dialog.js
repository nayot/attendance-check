// "Break" dialog, used on the attendance list and on the class screen.
// On success it fires a `break-started` event on window with the new break.
window.BreakDialog = (() => {
  const dlg = document.getElementById("break-dialog");
  const { base, session: sid, csrf } = dlg.dataset;
  const form = document.getElementById("break-form");
  const error = document.getElementById("break-error");

  async function start(minutes) {
    const res = await fetch(`${base}/sessions/${sid}/break`, {
      method: "POST",
      headers: { "X-CSRF-Token": csrf, Accept: "application/json" },
      body: new URLSearchParams({ minutes }),
    });
    if (!res.ok) {
      error.textContent = await res.text();
      error.hidden = false;
      return;
    }
    const data = await res.json();
    dlg.close();
    window.dispatchEvent(new CustomEvent("break-started", { detail: data }));
  }

  function open() {
    error.hidden = true;
    dlg.showModal();
  }

  dlg.querySelectorAll("[data-minutes]").forEach((b) => (b.onclick = () => start(b.dataset.minutes)));
  document.getElementById("break-cancel").onclick = () => dlg.close();
  form.onsubmit = (e) => {
    e.preventDefault();
    start(form.minutes.value);
  };

  return { open };
})();
