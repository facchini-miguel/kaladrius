// Patient form: show only the fields that apply to the chosen person type (individual or
// company).
(function () {
  "use strict";
  const form = document.getElementById("patient-form");
  if (!form) return;
  function atualizar() {
    const tipo = form.querySelector("input[name=kind]:checked")?.value || "PF";
    form.querySelectorAll(".pf-only").forEach((el) => { el.hidden = tipo !== "PF"; });
    form.querySelectorAll(".pj-only").forEach((el) => { el.hidden = tipo !== "PJ"; });
  }
  form.querySelectorAll("input[name=kind]").forEach((el) => el.addEventListener("change", atualizar));
  atualizar();
})();
