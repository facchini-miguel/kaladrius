// Patient form: show only the fields that apply to the chosen person type (individual or
// company).
(function () {
  "use strict";
  const form = document.getElementById("patient-form");
  if (!form) return;
  function update() {
    const kind = form.querySelector("input[name=kind]:checked")?.value || "PF";
    form.querySelectorAll(".pf-only").forEach((el) => { el.hidden = kind !== "PF"; });
    form.querySelectorAll(".pj-only").forEach((el) => { el.hidden = kind !== "PJ"; });
  }
  form.querySelectorAll("input[name=kind]").forEach((el) => el.addEventListener("change", update));
  update();
})();
