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

  // Every password field gets an eye button to show or hide what was typed.
  const OLHO = '<svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true" fill="currentColor"><path d="M8 3C4.5 3 1.7 5.3.5 8c1.2 2.7 4 5 7.5 5s6.3-2.3 7.5-5C14.3 5.3 11.5 3 8 3Zm0 8.3A3.3 3.3 0 1 1 8 4.7a3.3 3.3 0 0 1 0 6.6Zm0-5.1a1.8 1.8 0 1 0 0 3.6 1.8 1.8 0 0 0 0-3.6Z"/></svg>';
  const OLHO_RISCADO = '<svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true" fill="currentColor"><path d="M2.1 1.4 1.4 2.1l2.2 2.2C2.2 5.2 1.1 6.5.5 8c1.2 2.7 4 5 7.5 5 1.4 0 2.7-.4 3.8-1l2.1 2.1.7-.7L2.1 1.4ZM8 11.3A3.3 3.3 0 0 1 4.9 6.8l1.2 1.1a1.8 1.8 0 0 0 2 2l1.2 1.1c-.4.2-.9.3-1.3.3ZM8 3c-1 0-2 .2-2.8.6l1.3 1.3c.5-.2 1-.2 1.5-.2a3.3 3.3 0 0 1 3.3 3.3c0 .5-.1 1-.2 1.5l2 2c1.1-.9 1.9-2.1 2.4-3.5C14.3 5.3 11.5 3 8 3Z"/></svg>';
  const textos = document.body.dataset;
  function olhos(raiz) {
    raiz.querySelectorAll("input[type=password]:not([data-com-olho])").forEach((campo) => {
      campo.dataset.comOlho = "";
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
        botao.title = visivel ? textos.ocultarSenha : textos.mostrarSenha;
        botao.setAttribute("aria-label", botao.title);
        botao.setAttribute("aria-pressed", String(visivel));
      };
      mostrar(false);
      botao.addEventListener("click", () => mostrar(campo.type === "password"));
      grupo.appendChild(botao);
    });
  }
  olhos(document);
  document.body.addEventListener("htmx:afterSettle", (evento) => olhos(evento.target));

  // Leave after some idle minutes, so patient data does not stay on an unattended screen
  // (decision 111). Using the page (mouse, keys, touch) tells the server now and then, so a
  // long text being typed does not lose the session; open tabs share the last activity.
  const minutos = Number(textos.inatividade || 0);
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
        fetch(textos.urlAtivo, { credentials: "same-origin" }).then((r) => {
          if (r.redirected) window.location.href = textos.urlSaiu;
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
        const sair = document.getElementById("form-sair");
        if (sair) {
          const proximo = document.createElement("input");
          proximo.type = "hidden";
          proximo.name = "next";
          proximo.value = textos.urlSaiu;
          sair.appendChild(proximo);
          sair.submit();
        } else {
          window.location.href = textos.urlSaiu;
        }
      } else if (parado >= limite - 2 * 60000 && !avisado) {
        avisado = document.createElement("div");
        avisado.className = "alert alert-warning shadow position-fixed bottom-0 start-50 translate-middle-x mb-3";
        avisado.setAttribute("role", "alert");
        avisado.style.zIndex = 2000;
        avisado.textContent = textos.avisoInatividade;
        document.body.appendChild(avisado);
      }
    }, 15000);
  }
})();
