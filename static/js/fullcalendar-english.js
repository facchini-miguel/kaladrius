// English variants of the clinic's country (decision 117) for FullCalendar: the texts are the
// built-in English; the code sets the date order (31/10 in the UK, Australia and South Africa,
// 2026-10-31 in Canada) and the first day of the week.
(function () {
  [
    { code: "en-gb", week: { dow: 1, doy: 4 } },
    { code: "en-au", week: { dow: 1, doy: 4 } },
    { code: "en-za", week: { dow: 1, doy: 4 } },
    { code: "en-ca", week: { dow: 0, doy: 6 } },
  ].forEach(function (locale) {
    FullCalendar.globalLocales.push(locale);
  });
})();
