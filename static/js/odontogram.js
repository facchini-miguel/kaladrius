// Clickable dental chart (templates/dentistry/_odontogram.html): toggles teeth and keeps
// the form's hidden "teeth" field and the quantity in sync.
(function () {
  "use strict";
  document.querySelectorAll(".odontogram-interactive").forEach((chart) => {
    const form = chart.closest("form");
    const field = form.querySelector("input[name=teeth]");
    const quantity = form.querySelector("input[name=quantity]");
    chart.addEventListener("click", (event) => {
      const tooth = event.target.closest("[data-tooth]");
      if (!tooth) return;
      const pressed = tooth.classList.toggle("selected");
      tooth.setAttribute("aria-pressed", pressed ? "true" : "false");
      const chosen = [...chart.querySelectorAll(".tooth.selected")].map((b) => b.dataset.tooth);
      field.value = chosen.join(",");
      if (quantity && chosen.length) quantity.value = chosen.length;
    });
  });
})();
