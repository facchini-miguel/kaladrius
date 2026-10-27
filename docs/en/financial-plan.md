# Financial module plan

🇺🇸 English | [🇧🇷 Português](../pt-BR/plano-financeiro.md) | [🇪🇸 Español](../es/plan-financiero.md)

> Status: **steps 1 (receivables, 0.15.0) and 2 (payables, cash flow and reports, 0.16.0) done** (2026-10-27). Decisions 048 and 051. Interest and late fees are entered by hand, discounts by administrators only, and the clinic address is printed on receipts.

## Goal
Know **who owes what**, **how each person paid** (cash, Pix, card, installments) and **how much comes in and goes out** of the clinic, with entries made by hand by the staff.

## Out of scope (owner's decision)
- Issuing invoices (NFS-e) and the Receita Saúde receipt.
- Integration with Pix, boleto, payment links or card machines: the payment happens outside the system and is **recorded** in it.
- Dental insurance plans.

All of these can come later; the model below does not prevent them.

## Concepts

| Concept | What it is | Example |
|---|---|---|
| **Receivable** (lançamento a receber) | An amount someone owes the clinic, split into one or more installments | Root canal of R$ 1,200 in 3 installments |
| **Payable** (lançamento a pagar) | An amount the clinic owes | Rent of R$ 3,000, every 10th |
| **Installment** (parcela) | Amount and due date. Computed status: open, partial, paid, overdue, cancelled | 2nd installment, R$ 400, due 12/10 |
| **Payment** (pagamento) | How much of an installment was paid, when, how and into which account. An installment may have several (partial payment) | R$ 400 by Pix on 12/08 |
| **Account** (conta) | Where the money is | Cash drawer, Bank, Card machine |
| **Category** (categoria) | Grouping for reports | Income: Treatment, Consultation. Expenses: Rent, Supplies, Lab, Salaries |

### Payment methods
Cash, Pix, debit card, credit card (single payment or installments on the card machine, with the number of installments), bank transfer, boleto (paid outside the system) and check. For cards only the brand and the transaction code (NSU) are stored, **never** the card number.

### Installments on the card × installments with the clinic
- **On the card:** the patient pays everything at once (the card issuer splits it for them). The installment in the system is **paid**; the patient owes nothing.
- **With the clinic (store credit, payment book, checks):** the receivable is created with several installments and due dates. The patient **owes** each one until paying it. This is what shows in "who owes".

## Screens

| Screen | Contents |
|---|---|
| **Finance > Receivables** | Open installments, filters (overdue, due, period, patient), **Receive** button |
| **New receivable** | Patient (optional; or the payer's name), description, category, practitioner (optional), total, number of installments, first due date and interval (monthly). Installments can be adjusted before saving. "Already received now" option for the common pay-on-the-spot case |
| **Receive** | Amount (the whole installment or part), date, method, account, card details. Produces the receipt |
| **Receipt** | Page ready to print or save as PDF from the browser |
| **Finance > Debtors** | Per patient: overdue total and how long (up to 30, 31–60, 61–90 and over 90 days), linking to the record |
| **Patient record** | "Finance" panel: balance owed, open installments and latest payments |
| **Finance > Payables** | Like receivables, with a supplier instead of a patient and monthly repetition (creates the next installments) |
| **Finance > Cash flow** | Per day or month: **actual** income and expenses (payments) and **expected** ones (open installments), and balance per account |
| **Finance > Daily cash** | The day's income and expenses per account, withdrawals and top-ups, closing with the counted amount and the difference |
| **Finance > Reports** | Received per payment method, per category and per practitioner; expenses per category |
| **Records > Finance** | Accounts and categories (each clinic starts with a default list) |

## Rules
- Nothing is really deleted: a receivable/payable becomes **cancelled** and a payment becomes **reversed**, with a reason. Everything is in the audit log.
- Installments add up to the total; a payment never exceeds what is left of the installment.
- Amounts in reais with cents (`Decimal`, never floating point).
- Per-clinic isolation, like the rest of the system.

## Permissions
Two new modules in the matrix:

| Module | Admin | Front desk | Practitioner |
|---|---|---|---|
| **Receipts** (receivables, receive, receipt, debtors, daily cash) | all | view, create, change | — |
| **Finance** (payables, cash flow, reports, accounts and categories) | all | — | — |

Cancelling entries and reversing payments is for administrators only. So the front desk receives payments and checks who owes, but does not see the clinic's salaries and expenses.

## Steps

| # | Step | Deliverable | Version |
|---|---|---|---|
| 1 ✅ | **Receivables** | Models, default accounts and categories, receivable with installments, receive (all methods, partial), receipt, debtors, panel in the patient record, permissions | 0.15.0 |
| 2 ✅ | **Payables and cash flow** | Payable with monthly repetition, actual and expected cash flow, balance per account, reports | 0.16.0 |
| 3 | **Daily cash** | Opening, withdrawals, top-ups and closing with counting | 0.17.0 |

### Later (no date)
Procedure price list and **treatment estimate** that becomes a receivable; **practitioner commission**; period result (income statement); card machine fees and settlement dates; bank statement import (OFX). And, if decided: invoices, integrated Pix/boleto, insurance plans.

## Assumptions (may be revisited)
1. Finance comes **before** phase 2 (API and app).
2. Estimates and commission come after the 3 steps.
3. A receivable may have no registered patient (payer's name as text).
4. A receivable may name the practitioner, for the future commission.
5. The whole module is born in the three interface languages (versions 0.13 and 0.14 brought the languages and Help before it).
