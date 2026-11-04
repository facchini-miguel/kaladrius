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
  // The calendar runs in UTC mode with the clinic's wall clock (decision 117): its dates carry
  // the clinic's times in their UTC fields, whatever the browser's time zone.
  const hora = (d) => `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`;
  const dataISO = (d) => `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}`;

  const toque = window.matchMedia("(pointer: coarse)").matches;

  function abrirNovo(inicio, fim) {
    const params = new URLSearchParams({
      practitioner: config.practitioner,
      data: dataISO(inicio),
      inicio: hora(inicio),
      fim: hora(fim),
    });
    abrirModal(`${config.urls.novo}?${params}`);
  }

  function abrirModal(url) {
    htmx.ajax("GET", url, { target: "#modal-conteudo", swap: "innerHTML" }).then(() => modal.show());
  }

  function mostrarAviso(texto) {
    aviso.textContent = texto;
    aviso.hidden = false;
    clearTimeout(mostrarAviso.timer);
    mostrarAviso.timer = setTimeout(() => { aviso.hidden = true; }, 5000);
  }

  // Badges in the day headers (birthdays and pending recalls), each opening a list.
  const MARCADORES = [
    { classe: "aniversariantes", icone: "🎂", titulo: config.textos.aniversariantes, resumo: config.urls.aniversariantes, dia: config.urls.aniversariantes_dia },
    { classe: "rechamadas", icone: "📞", titulo: config.textos.rechamadas, resumo: config.urls.rechamadas, dia: config.urls.rechamadas_dia },
  ];

  function marcarDias(info) {
    const params = new URLSearchParams({ start: info.startStr, end: info.endStr });
    MARCADORES.filter((m) => m.resumo).forEach((marcador) => {
      fetch(`${marcador.resumo}?${params}`)
        .then((resposta) => (resposta.ok ? resposta.json() : {}))
        .then((dias) => {
          Object.entries(dias).forEach(([dia, total]) => {
            const celula = elementoCalendario.querySelector(`.fc-col-header-cell[data-date="${dia}"] .fc-scrollgrid-sync-inner`);
            if (!celula || celula.querySelector(`.${marcador.classe}`)) return;
            const botao = document.createElement("button");
            botao.type = "button";
            botao.className = `btn btn-sm btn-link ${marcador.classe} p-0 ms-1`;
            botao.title = `${total} ${marcador.titulo}`;
            botao.textContent = `${marcador.icone} ${total}`;
            botao.addEventListener("click", () => abrirModal(`${marcador.dia}?data=${dia}`));
            celula.appendChild(botao);
          });
        });
    });
  }

  const calendario = new FullCalendar.Calendar(elementoCalendario, {
    locale: config.idioma,
    timeZone: "UTC",
    now: config.agora,
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
    // A cancelled appointment (desmarcado) stays visible but does not hold the slot.
    selectOverlap: (evento) => evento.extendedProps.status === "desmarcou",
    events: { url: config.urls.eventos, extraParams: () => ({ practitioner: config.practitioner }) },
    datesSet: marcarDias,
    select(info) {
      calendario.unselect();
      abrirNovo(info.start, info.end);
    },
    // Touch screens (phones, tablets): the calendar only selects after holding a finger for a
    // second, which nobody finds; a tap on a free slot opens the new appointment for that slot.
    dateClick(info) {
      if (!config.pode.criar || !toque) return;
      abrirNovo(info.date, new Date(info.date.getTime() + config.intervalo * 60000));
    },
    eventClick(info) {
      if (config.pode.alterar) abrirModal(info.event.extendedProps.url);
    },
    eventDidMount(info) {
      const { kind, description, status, status_name } = info.event.extendedProps;
      const marcada = status && status !== "agendado" ? status_name : "";
      info.el.title = [kind, marcada, description].filter(Boolean).join(" · ");
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

})();
