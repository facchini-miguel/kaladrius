// Small behaviours shared by every page. They live here, not in onclick/onchange
// attributes, because the Content-Security-Policy forbids inline scripts.
(function () {
  "use strict";
  // <select data-submit-on-change>: submit its form as soon as the choice changes.
  document.addEventListener("change", (evento) => {
    if (evento.target.matches("[data-submit-on-change]")) evento.target.form.submit();
  });
  // <button data-print>: open the print dialog.
  document.addEventListener("click", (evento) => {
    if (evento.target.closest("[data-print]")) window.print();
  });

  // A document that depends on the person type (decision 121): the field takes the name and
  // example of the chosen type's document ("CPF" or "CNPJ") and hides when that type has none
  // in the clinic's country.
  function documentos(form) {
    const tipo = form.querySelector("input[name=kind]:checked")?.value || "PF";
    const sufixo = tipo === "PJ" ? "Pj" : "Pf";
    form.querySelectorAll("input[data-label-pf]").forEach((campo) => {
      const rotulo = campo.dataset["label" + sufixo];
      const caixa = campo.closest(".mb-3") || campo;
      const pai = caixa.parentElement;
      const alvo = pai && pai.children.length === 1 && /\bcol/.test(pai.className) ? pai : caixa;
      alvo.hidden = !rotulo;
      const nome = form.querySelector(`label[for="${campo.id}"]`);
      if (rotulo && nome) nome.textContent = rotulo;
      campo.placeholder = campo.dataset["example" + sufixo] || "";
    });
  }
  document.querySelectorAll("form").forEach((form) => {
    if (form.querySelector("input[data-label-pf]")) documentos(form);
  });
  document.addEventListener("change", (evento) => {
    if (evento.target.matches("input[name=kind]") && evento.target.form) documentos(evento.target.form);
  });

  // Every password field gets an eye button to show or hide what was typed.
  const OLHO = '<svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true" fill="currentColor"><path d="M8 3C4.5 3 1.7 5.3.5 8c1.2 2.7 4 5 7.5 5s6.3-2.3 7.5-5C14.3 5.3 11.5 3 8 3Zm0 8.3A3.3 3.3 0 1 1 8 4.7a3.3 3.3 0 0 1 0 6.6Zm0-5.1a1.8 1.8 0 1 0 0 3.6 1.8 1.8 0 0 0 0-3.6Z"/></svg>';
  const OLHO_RISCADO = '<svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true" fill="currentColor"><path d="M2.1 1.4 1.4 2.1l2.2 2.2C2.2 5.2 1.1 6.5.5 8c1.2 2.7 4 5 7.5 5 1.4 0 2.7-.4 3.8-1l2.1 2.1.7-.7L2.1 1.4ZM8 11.3A3.3 3.3 0 0 1 4.9 6.8l1.2 1.1a1.8 1.8 0 0 0 2 2l1.2 1.1c-.4.2-.9.3-1.3.3ZM8 3c-1 0-2 .2-2.8.6l1.3 1.3c.5-.2 1-.2 1.5-.2a3.3 3.3 0 0 1 3.3 3.3c0 .5-.1 1-.2 1.5l2 2c1.1-.9 1.9-2.1 2.4-3.5C14.3 5.3 11.5 3 8 3Z"/></svg>';
  const textos = document.body.dataset;
  function olhos(raiz) {
    raiz.querySelectorAll("input[type=password]:not([data-password-toggle])").forEach((campo) => {
      campo.dataset.passwordToggle = "";
      const grupo = document.createElement("div");
      grupo.className = "input-group";
      campo.parentNode.insertBefore(grupo, campo);
      grupo.appendChild(campo);
      const botao = document.createElement("button");
      botao.type = "button";
      botao.className = "btn btn-outline-secondary";
      const mostrar = (visivel) => {
        campo.type = visivel ? "text" : "password";
        botao.innerHTML = visivel ? OLHO_RISCADO : OLHO;
        botao.title = visivel ? textos.hidePassword : textos.showPassword;
        botao.setAttribute("aria-label", botao.title);
        botao.setAttribute("aria-pressed", String(visivel));
      };
      mostrar(false);
      botao.addEventListener("click", () => mostrar(campo.type === "password"));
      grupo.appendChild(botao);
      // Submitted while shown, the field would go as plain text and the browser would not offer
      // to save the password: it always goes back to a password field before sending.
      if (campo.form) campo.form.addEventListener("submit", () => mostrar(false));
    });
  }
  olhos(document);
  document.body.addEventListener("htmx:afterSettle", (evento) => olhos(evento.target));

  // Leave after some idle minutes, so patient data does not stay on an unattended screen
  // (decision 111). Using the page (mouse, keys, touch) tells the server now and then, so a
  // long text being typed does not lose the session; open tabs share the last activity.
  const minutos = Number(textos.idleMinutes || 0);
  if (minutos) {
    const CHAVE = "kaladrius-atividade";
    const limite = minutos * 60000;
    let avisado = null;
    let saindo = false;
    let ultimoAviso = Date.now();
    const carregada = Date.now();
    const ultima = () => {
      try { return Math.max(Number(localStorage.getItem(CHAVE) || 0), carregada); } catch (erro) { return carregada; }
    };
    const atividade = () => {
      const agora = Date.now();
      try { localStorage.setItem(CHAVE, String(agora)); } catch (erro) { /* private window */ }
      if (avisado) { avisado.remove(); avisado = null; }
      if (agora - ultimoAviso > 5 * 60000) {
        ultimoAviso = agora;
        fetch(textos.urlActive, { credentials: "same-origin" }).then((r) => {
          if (r.redirected) window.location.href = textos.urlLoggedOut;
        });
      }
    };
    ["mousemove", "keydown", "pointerdown", "scroll", "touchstart"].forEach((nome) =>
      document.addEventListener(nome, atividade, { passive: true }));
    setInterval(() => {
      const parado = Date.now() - ultima();
      if (saindo) return;
      if (parado >= limite) {
        saindo = true; // once: a slow answer must not be cut by a second submit
        const sair = document.getElementById("logout-form");
        if (sair) {
          const proximo = document.createElement("input");
          proximo.type = "hidden";
          proximo.name = "next";
          proximo.value = textos.urlLoggedOut;
          sair.appendChild(proximo);
          sair.submit();
        } else {
          window.location.href = textos.urlLoggedOut;
        }
      } else if (parado >= limite - 2 * 60000 && !avisado) {
        avisado = document.createElement("div");
        avisado.className = "alert alert-warning shadow position-fixed bottom-0 start-50 translate-middle-x mb-3";
        avisado.setAttribute("role", "alert");
        avisado.style.zIndex = 2000;
        avisado.textContent = textos.idleWarning;
        document.body.appendChild(avisado);
      }
    }, 15000);
  }
})();
