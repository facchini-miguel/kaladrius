// Clickable dental chart (templates/dentistry/_odontogram.html): toggles teeth and keeps
// the form's hidden "teeth" field and the quantity in sync.
(function () {
  "use strict";
  document.querySelectorAll(".odontogram-interactive").forEach((grafico) => {
    const form = grafico.closest("form");
    const campo = form.querySelector("input[name=teeth]");
    const quantidade = form.querySelector("input[name=quantity]");
    grafico.addEventListener("click", (evento) => {
      const tooth = evento.target.closest("[data-tooth]");
      if (!tooth) return;
      const ligado = tooth.classList.toggle("selected");
      tooth.setAttribute("aria-pressed", ligado ? "true" : "false");
      const escolhidos = [...grafico.querySelectorAll(".tooth.selected")].map((b) => b.dataset.tooth);
      campo.value = escolhidos.join(",");
      if (quantidade && escolhidos.length) quantidade.value = escolhidos.length;
    });
  });
})();
