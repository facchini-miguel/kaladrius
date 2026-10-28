// Small behaviours shared by every page. They live here, not in onclick/onchange
// attributes, because the Content-Security-Policy forbids inline scripts.
(function () {
  "use strict";
  // <select data-enviar-ao-mudar>: submit its form as soon as the choice changes.
  document.addEventListener("change", (evento) => {
    if (evento.target.matches("[data-enviar-ao-mudar]")) evento.target.form.submit();
  });
  // <button data-imprimir>: open the print dialog.
  document.addEventListener("click", (evento) => {
    if (evento.target.closest("[data-imprimir]")) window.print();
  });
})();
