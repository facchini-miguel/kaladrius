// Patient search-as-you-type (templates/includes/patient_search.html), works in pages and modals.
(function () {
  "use strict";
  document.addEventListener("click", (evento) => {
    const opcao = evento.target.closest("[data-patient-id]");
    if (!opcao) return;
    const caixa = opcao.closest(".patient-search");
    if (!caixa) return;
    evento.preventDefault();
    caixa.querySelector("input[type=hidden]").value = opcao.dataset.patientId;
    caixa.querySelector(".patient-search-text").value = opcao.dataset.patientName;
    caixa.querySelector(".patient-search-suggestions").innerHTML = "";
  });
  document.addEventListener("input", (evento) => {
    const texto = evento.target;
    if (!texto.classList.contains("patient-search-text") || texto.value) return;
    texto.closest(".patient-search").querySelector("input[type=hidden]").value = "";
  });
})();
