// Patient form: show only the fields that apply to the chosen person type (individual or
// company).
(function () {
  "use strict";
  const form = document.getElementById("form-paciente");
  if (!form) return;
  function atualizar() {
    const tipo = form.querySelector("input[name=tipo]:checked")?.value || "PF";
    form.querySelectorAll(".so-pf").forEach((el) => { el.hidden = tipo !== "PF"; });
    form.querySelectorAll(".so-pj").forEach((el) => { el.hidden = tipo !== "PJ"; });
  }
  form.querySelectorAll("input[name=tipo]").forEach((el) => el.addEventListener("change", atualizar));
  atualizar();
})();
