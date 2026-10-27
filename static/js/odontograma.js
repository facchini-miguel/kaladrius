// Clickable dental chart (templates/orcamentos/_odontograma.html): toggles teeth and keeps
// the form's hidden "dentes" field and the quantity in sync.
(function () {
  "use strict";
  document.querySelectorAll(".odontograma-interativo").forEach((grafico) => {
    const form = grafico.closest("form");
    const campo = form.querySelector("input[name=dentes]");
    const quantidade = form.querySelector("input[name=quantidade]");
    grafico.addEventListener("click", (evento) => {
      const dente = evento.target.closest("[data-dente]");
      if (!dente) return;
      const ligado = dente.classList.toggle("selecionado");
      dente.setAttribute("aria-pressed", ligado ? "true" : "false");
      const escolhidos = [...grafico.querySelectorAll(".dente.selecionado")].map((b) => b.dataset.dente);
      campo.value = escolhidos.join(",");
      if (quantidade && escolhidos.length) quantidade.value = escolhidos.length;
    });
  });
})();
