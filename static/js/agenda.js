// Schedule page: FullCalendar week grid + modal forms loaded with HTMX.
(function () {
  "use strict";

  const elementoConfig = document.getElementById("configuracao-agenda");
  const elementoCalendario = document.getElementById("calendario");
  if (!elementoConfig || !elementoCalendario) return;

  const config = JSON.parse(elementoConfig.textContent);
  const modalEl = document.getElementById("modal-agenda");
  const modal = new bootstrap.Modal(modalEl);
  const aviso = document.getElementById("aviso-agenda");
  const pad = (n) => String(n).padStart(2, "0");
  const hora = (d) => `${pad(d.getHours())}:${pad(d.getMinutes())}`;
  const dataISO = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

  function abrirModal(url) {
    htmx.ajax("GET", url, { target: "#modal-conteudo", swap: "innerHTML" }).then(() => modal.show());
  }

  function mostrarAviso(texto) {
    aviso.textContent = texto;
    aviso.hidden = false;
    clearTimeout(mostrarAviso.timer);
    mostrarAviso.timer = setTimeout(() => { aviso.hidden = true; }, 5000);
  }

  // Birthday badges in the day headers.
  function marcarAniversariantes(info) {
    const params = new URLSearchParams({ start: info.startStr, end: info.endStr });
    fetch(`${config.urls.aniversariantes}?${params}`)
      .then((resposta) => (resposta.ok ? resposta.json() : {}))
      .then((dias) => {
        Object.entries(dias).forEach(([dia, total]) => {
          const cabecalho = elementoCalendario.querySelector(`.fc-col-header-cell[data-date="${dia}"] .fc-col-header-cell-cushion`);
          if (!cabecalho || cabecalho.parentElement.querySelector(".aniversariantes")) return;
          const botao = document.createElement("button");
          botao.type = "button";
          botao.className = "btn btn-sm btn-link aniversariantes p-0 ms-1";
          botao.title = `${total} aniversariante(s)`;
          botao.textContent = `🎂 ${total}`;
          botao.addEventListener("click", () => abrirModal(`${config.urls.aniversariantes_dia}?data=${dia}`));
          cabecalho.after(botao);
        });
      });
  }

  const calendario = new FullCalendar.Calendar(elementoCalendario, {
    locale: "pt-br",
    initialView: window.innerWidth < 768 ? "timeGridDay" : "timeGridWeek",
    initialDate: config.data || undefined,
    headerToolbar: { left: "prev,next today", center: "title", right: "timeGridWeek,timeGridDay,listWeek" },
    firstDay: 1,
    allDaySlot: false,
    slotMinTime: config.inicio,
    slotMaxTime: config.fim,
    slotDuration: { minutes: config.intervalo },
    snapDuration: { minutes: config.intervalo },
    slotLabelInterval: { minutes: config.intervalo },
    slotLabelFormat: { hour: "2-digit", minute: "2-digit", hour12: false },
    eventTimeFormat: { hour: "2-digit", minute: "2-digit", hour12: false },
    expandRows: true,
    height: "auto",
    nowIndicator: true,
    selectable: config.pode.criar,
    selectMirror: true,
    selectOverlap: false,
    events: { url: config.urls.eventos, extraParams: () => ({ profissional: config.profissional }) },
    datesSet: marcarAniversariantes,
    select(info) {
      calendario.unselect();
      const params = new URLSearchParams({
        profissional: config.profissional,
        data: dataISO(info.start),
        inicio: hora(info.start),
        fim: hora(info.end),
      });
      abrirModal(`${config.urls.novo}?${params}`);
    },
    eventClick(info) {
      if (config.pode.alterar) abrirModal(info.event.extendedProps.url);
    },
    eventDidMount(info) {
      const { tipo, descricao } = info.event.extendedProps;
      info.el.title = [tipo, descricao].filter(Boolean).join(" · ");
    },
  });
  calendario.render();

  const irParaData = document.getElementById("ir-para-data");
  if (irParaData) irParaData.addEventListener("change", () => irParaData.value && calendario.gotoDate(irParaData.value));

  // The server answers a successful save/delete with an "agendaAtualizada" HTMX event.
  document.body.addEventListener("agendaAtualizada", (evento) => {
    modal.hide();
    calendario.refetchEvents();
    if (evento.detail && evento.detail.mensagem) mostrarAviso(evento.detail.mensagem);
  });

  // Patient search-as-you-type inside the modal form.
  modalEl.addEventListener("click", (evento) => {
    const opcao = evento.target.closest("[data-paciente-id]");
    if (!opcao) return;
    evento.preventDefault();
    modalEl.querySelector("#id_paciente").value = opcao.dataset.pacienteId;
    modalEl.querySelector("#busca-paciente").value = opcao.dataset.pacienteNome;
    modalEl.querySelector("#sugestoes-paciente").innerHTML = "";
  });
  modalEl.addEventListener("input", (evento) => {
    if (evento.target.id === "busca-paciente" && !evento.target.value) {
      modalEl.querySelector("#id_paciente").value = "";
    }
  });
})();
