// Patient search-as-you-type (templates/includes/patient_search.html), works in pages and modals.
(function () {
  "use strict";
  document.addEventListener("click", (event) => {
    const option = event.target.closest("[data-patient-id]");
    if (!option) return;
    const box = option.closest(".patient-search");
    if (!box) return;
    event.preventDefault();
    box.querySelector("input[type=hidden]").value = option.dataset.patientId;
    box.querySelector(".patient-search-text").value = option.dataset.patientName;
    box.querySelector(".patient-search-suggestions").innerHTML = "";
  });
  document.addEventListener("input", (event) => {
    const input = event.target;
    if (!input.classList.contains("patient-search-text") || input.value) return;
    input.closest(".patient-search").querySelector("input[type=hidden]").value = "";
  });
})();
