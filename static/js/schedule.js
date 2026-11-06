// Schedule page: FullCalendar week grid + modal forms loaded with HTMX.
(function () {
  "use strict";

  const settingsElement = document.getElementById("schedule-settings");
  const calendarElement = document.getElementById("calendar");
  if (!settingsElement || !calendarElement) return;

  const config = JSON.parse(settingsElement.textContent);
  const modalEl = document.getElementById("schedule-modal");
  const modal = new bootstrap.Modal(modalEl);
  const notice = document.getElementById("schedule-notice");
  const pad = (n) => String(n).padStart(2, "0");
  // The calendar runs in UTC mode with the clinic's wall clock (decision 117): its dates carry
  // the clinic's times in their UTC fields, whatever the browser's time zone.
  const time = (d) => `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`;
  const isoDate = (d) => `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}`;

  const touch = window.matchMedia("(pointer: coarse)").matches;
  // Below 768px (phones) the calendar opens on the day view; there the week's seven columns are
  // too narrow for "seg. 02/11", which ran into each other: the day's initial and number.
  const narrow = window.innerWidth < 768;

  function openNew(start, end) {
    const params = new URLSearchParams({
      practitioner: config.practitioner,
      date: isoDate(start),
      start: time(start),
      end: time(end),
    });
    openModal(`${config.urls.new}?${params}`);
  }

  function openModal(url) {
    htmx.ajax("GET", url, { target: "#schedule-modal-content", swap: "innerHTML" }).then(() => modal.show());
  }

  function showNotice(text) {
    notice.textContent = text;
    notice.hidden = false;
    clearTimeout(showNotice.timer);
    showNotice.timer = setTimeout(() => { notice.hidden = true; }, 5000);
  }

  // Badges in the day headers (birthdays and pending recalls), each opening a list.
  const BADGES = [
    { cssClass: "birthday-badge", icon: "🎂", title: config.texts.birthdays, summary: config.urls.birthdays, day: config.urls.birthdays_today },
    { cssClass: "recall-badge", icon: "📞", title: config.texts.recalls, summary: config.urls.recalls, day: config.urls.recalls_today },
  ];

  function markDays(info) {
    const params = new URLSearchParams({ start: info.startStr, end: info.endStr });
    BADGES.filter((m) => m.summary).forEach((badge) => {
      fetch(`${badge.summary}?${params}`)
        .then((response) => (response.ok ? response.json() : {}))
        .then((days) => {
          Object.entries(days).forEach(([day, total]) => {
            const cell = calendarElement.querySelector(`.fc-col-header-cell[data-date="${day}"] .fc-scrollgrid-sync-inner`);
            if (!cell || cell.querySelector(`.${badge.cssClass}`)) return;
            const button = document.createElement("button");
            button.type = "button";
            button.className = `btn btn-sm btn-link ${badge.cssClass} p-0 ms-1`;
            button.title = `${total} ${badge.title}`;
            button.textContent = `${badge.icon} ${total}`;
            button.addEventListener("click", () => openModal(`${badge.day}?date=${day}`));
            cell.appendChild(button);
          });
        });
    });
  }

  const calendar = new FullCalendar.Calendar(calendarElement, {
    locale: config.language,
    timeZone: "UTC",
    now: config.now,
    initialView: narrow ? "timeGridDay" : "timeGridWeek",
    views: narrow ? { timeGridWeek: { dayHeaderFormat: { weekday: "narrow", day: "numeric", omitCommas: true } } } : {},
    initialDate: config.date || undefined,
    headerToolbar: { left: "prev,next today", center: "title", right: "timeGridWeek,timeGridDay,listWeek" },
    firstDay: 1,
    allDaySlot: false,
    slotMinTime: config.start,
    slotMaxTime: config.end,
    slotDuration: { minutes: config.interval },
    snapDuration: { minutes: config.interval },
    slotLabelInterval: { minutes: config.interval },
    slotLabelFormat: { hour: "2-digit", minute: "2-digit", hour12: false },
    eventTimeFormat: { hour: "2-digit", minute: "2-digit", hour12: false },
    expandRows: true,
    height: "auto",
    nowIndicator: true,
    selectable: config.can.create,
    selectMirror: true,
    // A cancelled appointment (desmarcado) stays visible but does not hold the slot.
    selectOverlap: (event) => event.extendedProps.status === "desmarcou",
    events: { url: config.urls.events, extraParams: () => ({ practitioner: config.practitioner }) },
    datesSet: markDays,
    select(info) {
      calendar.unselect();
      openNew(info.start, info.end);
    },
    // Touch screens (phones, tablets): the calendar only selects after holding a finger for a
    // second, which nobody finds; a tap on a free slot opens the new appointment for that slot.
    dateClick(info) {
      if (!config.can.create || !touch) return;
      openNew(info.date, new Date(info.date.getTime() + config.interval * 60000));
    },
    eventClick(info) {
      if (config.can.change) openModal(info.event.extendedProps.url);
    },
    eventDidMount(info) {
      const { kind, description, status, status_name } = info.event.extendedProps;
      const marked = status && status !== "agendado" ? status_name : "";
      info.el.title = [kind, marked, description].filter(Boolean).join(" · ");
    },
  });
  calendar.render();

  const goToDate = document.getElementById("go-to-date");
  if (goToDate) goToDate.addEventListener("change", () => goToDate.value && calendar.gotoDate(goToDate.value));

  // The server answers a successful save/delete with a "scheduleUpdated" HTMX event.
  document.body.addEventListener("scheduleUpdated", (event) => {
    modal.hide();
    calendar.refetchEvents();
    if (event.detail && event.detail.message) showNotice(event.detail.message);
  });

})();
