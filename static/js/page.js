// Small behaviours shared by every page. They live here, not in onclick/onchange
// attributes, because the Content-Security-Policy forbids inline scripts.
(function () {
  "use strict";
  // <select data-submit-on-change>: submit its form as soon as the choice changes.
  document.addEventListener("change", (event) => {
    if (event.target.matches("[data-submit-on-change]")) event.target.form.submit();
  });
  // <button data-print>: open the print dialog.
  document.addEventListener("click", (event) => {
    if (event.target.closest("[data-print]")) window.print();
  });

  // A document that depends on the person type (decision 121): the field takes the name and
  // example of the chosen type's document ("CPF" or "CNPJ") and hides when that type has none
  // in the clinic's country.
  function documents(form) {
    const kind = form.querySelector("input[name=kind]:checked")?.value || "individual";
    const suffix = kind === "company" ? "Pj" : "Pf";
    form.querySelectorAll("input[data-label-pf]").forEach((field) => {
      const label = field.dataset["label" + suffix];
      const box = field.closest(".mb-3") || field;
      const parent = box.parentElement;
      const target = parent && parent.children.length === 1 && /\bcol/.test(parent.className) ? parent : box;
      target.hidden = !label;
      const caption = form.querySelector(`label[for="${field.id}"]`);
      if (label && caption) caption.textContent = label;
      field.placeholder = field.dataset["example" + suffix] || "";
    });
  }
  document.querySelectorAll("form").forEach((form) => {
    if (form.querySelector("input[data-label-pf]")) documents(form);
  });
  document.addEventListener("change", (event) => {
    if (event.target.matches("input[name=kind]") && event.target.form) documents(event.target.form);
  });

  // Every password field gets an eye button to show or hide what was typed.
  const EYE = '<svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true" fill="currentColor"><path d="M8 3C4.5 3 1.7 5.3.5 8c1.2 2.7 4 5 7.5 5s6.3-2.3 7.5-5C14.3 5.3 11.5 3 8 3Zm0 8.3A3.3 3.3 0 1 1 8 4.7a3.3 3.3 0 0 1 0 6.6Zm0-5.1a1.8 1.8 0 1 0 0 3.6 1.8 1.8 0 0 0 0-3.6Z"/></svg>';
  const EYE_CROSSED = '<svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true" fill="currentColor"><path d="M2.1 1.4 1.4 2.1l2.2 2.2C2.2 5.2 1.1 6.5.5 8c1.2 2.7 4 5 7.5 5 1.4 0 2.7-.4 3.8-1l2.1 2.1.7-.7L2.1 1.4ZM8 11.3A3.3 3.3 0 0 1 4.9 6.8l1.2 1.1a1.8 1.8 0 0 0 2 2l1.2 1.1c-.4.2-.9.3-1.3.3ZM8 3c-1 0-2 .2-2.8.6l1.3 1.3c.5-.2 1-.2 1.5-.2a3.3 3.3 0 0 1 3.3 3.3c0 .5-.1 1-.2 1.5l2 2c1.1-.9 1.9-2.1 2.4-3.5C14.3 5.3 11.5 3 8 3Z"/></svg>';
  const texts = document.body.dataset;
  function addEyes(root) {
    root.querySelectorAll("input[type=password]:not([data-password-toggle])").forEach((field) => {
      field.dataset.passwordToggle = "";
      const group = document.createElement("div");
      group.className = "input-group";
      field.parentNode.insertBefore(group, field);
      group.appendChild(field);
      const button = document.createElement("button");
      button.type = "button";
      button.className = "btn btn-outline-secondary";
      const show = (visible) => {
        field.type = visible ? "text" : "password";
        button.innerHTML = visible ? EYE_CROSSED : EYE;
        button.title = visible ? texts.hidePassword : texts.showPassword;
        button.setAttribute("aria-label", button.title);
        button.setAttribute("aria-pressed", String(visible));
      };
      show(false);
      button.addEventListener("click", () => show(field.type === "password"));
      group.appendChild(button);
      // Submitted while shown, the field would go as plain text and the browser would not offer
      // to save the password: it always goes back to a password field before sending.
      if (field.form) field.form.addEventListener("submit", () => show(false));
    });
  }
  addEyes(document);
  document.body.addEventListener("htmx:afterSettle", (event) => addEyes(event.target));

  // Leave after some idle minutes, so patient data does not stay on an unattended screen
  // (decision 111). Using the page (mouse, keys, touch) tells the server now and then, so a
  // long text being typed does not lose the session; open tabs share the last activity.
  const minutes = Number(texts.idleMinutes || 0);
  if (minutes) {
    const KEY = "kaladrius-activity";
    const limit = minutes * 60000;
    let warning = null;
    let leaving = false;
    let lastPing = Date.now();
    const loadedAt = Date.now();
    const lastActivity = () => {
      try { return Math.max(Number(localStorage.getItem(KEY) || 0), loadedAt); } catch (error) { return loadedAt; }
    };
    const activity = () => {
      const now = Date.now();
      try { localStorage.setItem(KEY, String(now)); } catch (error) { /* private window */ }
      if (warning) { warning.remove(); warning = null; }
      if (now - lastPing > 5 * 60000) {
        lastPing = now;
        fetch(texts.urlActive, { credentials: "same-origin" }).then((r) => {
          if (r.redirected) window.location.href = texts.urlLoggedOut;
        });
      }
    };
    ["mousemove", "keydown", "pointerdown", "scroll", "touchstart"].forEach((name) =>
      document.addEventListener(name, activity, { passive: true }));
    setInterval(() => {
      const idle = Date.now() - lastActivity();
      if (leaving) return;
      if (idle >= limit) {
        leaving = true; // once: a slow answer must not be cut by a second submit
        const logoutForm = document.getElementById("logout-form");
        if (logoutForm) {
          const nextField = document.createElement("input");
          nextField.type = "hidden";
          nextField.name = "next";
          nextField.value = texts.urlLoggedOut;
          logoutForm.appendChild(nextField);
          logoutForm.submit();
        } else {
          window.location.href = texts.urlLoggedOut;
        }
      } else if (idle >= limit - 2 * 60000 && !warning) {
        warning = document.createElement("div");
        warning.className = "alert alert-warning shadow position-fixed bottom-0 start-50 translate-middle-x mb-3";
        warning.setAttribute("role", "alert");
        warning.style.zIndex = 2000;
        warning.textContent = texts.idleWarning;
        document.body.appendChild(warning);
      }
    }, 15000);
  }
})();
