---
sidebar_position: 8
---

# Clinic settings

These screens belong to the **clinic administrator**, in the **Records** menu.

## Clinic settings
In **Records > Clinic settings**: the clinic's name, CPF/CNPJ, e-mail and phone, and the **schedule hours** (start, end and length of each slot).

The installation serves **one clinic**, with one patient register, team, schedule and finance. There is no clinic switcher. The internal clinic identifiers remain in place for a possible future extension.

The **primary area** sets the appointment types when the clinic is first created. Under **Specialties**, enable **Dentistry** only, **Medicine** only, or both together (or neither, for another health area). The same options appear in the system administrator's clinic form. Changing the primary area later does not change these switches or replace existing appointment types.

Dentistry enables the dental chart and the teeth and surfaces of estimate items. Disabling it keeps existing dental items visible and printable, but prevents creating, changing or removing them until it is enabled again. General estimate items remain available. Medicine prepares the configuration for medical extensions; the shared medical record remains available in every area, according to the existing practitioner permissions. Enabling a module does not grant access to clinical records or create new specialty forms automatically.

**Modules** holds the parts shared by the specialties: **Schedule**, **Medical record**, **Estimates**, **Finance**, **Recalls**, **Birthdays**, [**Health plans**](convenios.md) and [**Staff**](pessoal.md). A new clinic starts with all of them on, and so does an updated installation. A module turned off leaves the menu, the home page and the patient record for the whole team, the system administrator included, and its address is refused. Nothing already recorded is erased: turning it back on shows everything again. **Estimates** and **Staff** need **Finance** on, because approving an estimate creates the receivable and the month's pay creates the payables. Patients, practitioners, the team, the base tables, the clinic settings and the audit log are always on.

If a future appointment would fall outside the new hours or slot length, the change is refused and the screen shows which one. Adjust that appointment first.

## Appointment types
In **Records > Appointment types**: the types (surgery, first visit…) and the color each one paints in the schedule. To stop using a type without losing the history, uncheck **active**.

## Audit log
In **Records > Audit log**: who created, changed, deleted or opened each record of the clinic, when, from which address and what changed. Filters search by user, action, record type and period. Entries cannot be changed. Refused login attempts are deleted after 30 days.
