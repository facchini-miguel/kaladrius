---
sidebar_position: 3.7
---

# Health plans

The **Health plans** module keeps the plans the clinic accepts and each patient's card. It can be turned off in the [clinic settings](clinica.md) by clinics that only see private patients.

## Registering a health plan
In **Records > Health plans**, click **New health plan** and fill in the name and, if there is one, the **insurer registration** of the clinic's country (in Brazil the ANS, 6 digits; in the United States the Payer ID; in Argentina the RNOS; in South Africa the CMS number), the phone and notes. Countries without an insurer registry do not show the field. The same name cannot be registered twice. To stop accepting a plan without losing the history, edit it and uncheck **active**: it leaves the list of new cards, and the existing cards stay.

## The patient's card
On the patient's record, the **Health plans** card lists their cards. Click **New card** and choose the plan, the **plan type** (e.g. "Basic"), the **card number**, the **valid until** date and, for a dependent, the plan **holder**. The same card number cannot belong to two patients of the same plan.

The card number carries its local name (Member ID in the United States, membership number in the United Kingdom, Australia and South Africa, número de afiliado in Argentina…). North American cards also have the **group number**, and South African and Australian family cards the **beneficiary code** (dependant code, patient number on the card).

An expired card shows **Expired**. A patient without a card shows **Private**. A card that is no longer used can be marked as inactive without being deleted.

## Who does what
The front desk and the administrator register plans and cards; practitioners and the Finance role see them. When a patient's data is deleted at their request (LGPD), their cards are deleted too.

Authorizations, claims and billing the plans are not part of the system yet.
