---
sidebar_position: 8
---

# Clinic settings

These screens belong to the **clinic administrator**, in the **Records** menu.

## Clinic settings
In **Records > Clinic settings**: the clinic's name, CPF/CNPJ, e-mail and phone, and the **schedule hours** (start, end and length of each slot).

The installation serves **one clinic**, with one patient register, team, schedule and finance. There is no clinic switcher. The internal clinic identifiers remain in place for a possible future extension.

The **primary area** sets the appointment types when the clinic is first created. Under **Specialties**, enable **Dentistry** only, **Medicine** only, or both together (or neither, for another health area). The same options appear in the system administrator's clinic form. Changing the primary area later does not change these switches or replace existing appointment types.

Dentistry enables the dental chart and the teeth and surfaces of estimate items. Disabling it keeps existing dental items visible and printable, but prevents creating, changing or removing them until it is enabled again (the system administrator still can, with a warning). General estimate items remain available. Medicine prepares the configuration for medical extensions; the shared medical record remains available in every area, according to the existing practitioner permissions. Enabling a module does not grant access to clinical records or create new specialty forms automatically.

**Modules** holds the parts shared by the specialties: **Schedule**, **Medical record**, **Estimates**, **Finance**, **Recalls**, **Birthdays**, [**Health plans**](convenios.md) and [**Staff**](pessoal.md). A new clinic starts with all of them on, and so does an updated installation. A module turned off leaves the menu, the home page and the patient record for the whole team, and its address is refused. The **system administrator** still sees it, marked **off** in the menu and with a warning on its pages, to maintain it or to try it before turning it on. Nothing already recorded is erased: turning it back on shows everything again. **Estimates** and **Staff** need **Finance** on, because approving an estimate creates the receivable and the month's pay creates the payables. Patients, practitioners, the team, the base tables, the clinic settings and the audit log are always on.

If a future appointment would fall outside the new hours or slot length, the change is refused and the screen shows which one. Adjust that appointment first.

**Require two-step verification from whoever reaches the medical record or finance** (on by default): practitioners with medical records, administrators and finance staff only use the system after turning on the authenticator app code (see [Getting started](inicio.md)); until then each page takes them to the QR code. The front desk is not required, and the public demo logins never are.

**Country and time zone**: Brazil by default; also the United States, the United Kingdom, Canada, Australia and South Africa. The country sets the time zones offered (the schedule and every time follow the clinic's, wherever each person is), phones in the country's format with the right WhatsApp code, postal codes (ZIP code, postcode…), the order of dates in English (10/31 in the United States, 31/10 in the United Kingdom, Australia and South Africa, 2026-10-31 in Canada) and the suggested currency, which follows a change of country unless another was chosen. Outside Brazil the patient's state and city are typed, and CPF/CNPJ, RG and state registration are not shown: each country's documents come in a next version.

**Currency**: the currency the clinic works in (Brazilian real by default; also US dollar, euro, pound sterling and the Argentine, Mexican, Chilean, Colombian and Uruguayan pesos, the Paraguayan guaraní, the Peruvian sol and the boliviano). Every amount in the system, receipts included, shows in it, for the whole team and whatever language each person uses: the language only sets the separators (1.234,56 or 1,234.56). Changing it does **not convert** amounts already entered; it only changes how they are shown.

## Appointment types
In **Records > Appointment types**: the types (surgery, first visit…) and the color each one paints in the schedule. To stop using a type without losing the history, uncheck **active**. The default types (Surgery, First visit…) show in each person's language; a type the clinic creates or renames shows as typed.

## Audit log
In **Records > Audit log**: who created, changed, deleted or opened each record of the clinic, when, from which address and what changed. Filters search by user, action, record type and period. Entries cannot be changed. Refused login attempts are deleted after 30 days.
