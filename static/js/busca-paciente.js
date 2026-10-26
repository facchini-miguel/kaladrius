// Patient search-as-you-type (templates/includes/busca_paciente.html), works in pages and modals.
(function () {
  "use strict";
  document.addEventListener("click", (evento) => {
    const opcao = evento.target.closest("[data-paciente-id]");
    if (!opcao) return;
    const caixa = opcao.closest(".busca-paciente");
    if (!caixa) return;
    evento.preventDefault();
    caixa.querySelector("input[type=hidden]").value = opcao.dataset.pacienteId;
    caixa.querySelector(".busca-paciente-texto").value = opcao.dataset.pacienteNome;
    caixa.querySelector(".busca-paciente-sugestoes").innerHTML = "";
  });
  document.addEventListener("input", (evento) => {
    const texto = evento.target;
    if (!texto.classList.contains("busca-paciente-texto") || texto.value) return;
    texto.closest(".busca-paciente").querySelector("input[type=hidden]").value = "";
  });
})();
