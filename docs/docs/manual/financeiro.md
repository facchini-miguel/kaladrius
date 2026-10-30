---
sidebar_position: 6
---

# Finance

The **Finance** menu shows who owes the clinic and how each person paid. Payments happen outside the system (cash, Pix, card machine) and are **recorded** here. The front desk and the administrator use it; practitioners do not see the finances.

## Recording an amount to receive
1. In **Finance > New entry** (or in the **Finance** panel of the patient record), choose the **patient**. If the payer is not a registered patient, type the name in **payer**.
2. Enter the **description** (for example, "Root canal"), the **category**, the **practitioner** (optional) and the **total amount**.
3. In **Number of installments**, enter how many times the patient will pay **the clinic**, one per month, from the **due date of the 1st installment**. Installments have the same amount; leftover cents go to the first one.
4. If the patient paid on the spot, check **The 1st installment has just been paid**, choose the method and the account, and save: the receipt opens next.

**Card installments are not installments with the clinic.** If the patient paid by card in 6 installments, the clinic is paid by the card company: record **1 installment** and, when receiving, enter the 6 installments in the **card installments** field. The patient owes nothing.

## Receiving
In **Finance > Receivables**, the list shows the open installments (overdue ones in red). Click **Receive** and enter:
- **amount received** (it may be only part: the rest stays open);
- **interest and late fee**, if charged, already included in the amount received (calculated by hand);
- **payment method** and **account** (Cash, Bank…);
- for cards: brand, number of card installments and transaction code. **Never** write down the card number.

Only the clinic administrator can give a **discount**.

## Receipt
After receiving, the receipt opens ready to **print or save as PDF**. It shows the clinic's details (name, CPF/CNPJ, address and phone, from **Records > Clinic settings**), who paid, the amount, the installment and the payment method. To print it again, open the entry and click **receipt** next to the payment.

## Debtors
In **Finance > Debtors**, each patient with overdue installments, the overdue total split by days late (up to 30, 31 to 60, 61 to 90 and over 90 days), what is not yet due and the oldest due date. Click the name to open the record.

## Fixing a mistake
Nothing is deleted. The **administrator** can:
- **reverse** a payment recorded by mistake (open the entry and click **reverse**, with the reason): the installment is open again and the receipt shows "REVERSED";
- **cancel** an entry (after reversing its payments), with the reason.

Everything is recorded in the audit log.

## Daily cash
In **Finance > Daily cash**, the front desk controls the money in the drawer:
1. **Open drawer:** count the money and enter the amount. The system shows how much the account should have, only as a reference.
2. During the day, payments registered into the **Caixa** (cash) account come in automatically.
3. **Withdrawal:** money that leaves the drawer, with the reason. If it is deposited in the bank, choose the **Banco** account in **Other account**; empty, the money leaves the system (for example, an owner's withdrawal).
4. **Top-up:** money that enters the drawer, like change.
5. **Close drawer:** count again and enter the amount. The system shows how much there should be and records the **difference**; explain it in the note, if any.

Each account can have only one open drawer. Closed drawers are listed in **Previous drawers**, with the expected and counted amounts and the difference.

## Payables (administrator)
In **Finance > New expense**, choose the registered **supplier** (for a one-off payment, type the name in **Unregistered supplier**), the category, the description and the amount. In **The amount is**, choose:
- **the total, split into the installments**: a R$ 900 purchase in 3 installments becomes 3 installments of R$ 300;
- **per month**: a fixed bill, like rent of R$ 3,000 for 12 months, becomes 12 installments of R$ 3,000.

In **Finance > Payables**, click **Pay** when you pay an installment. Reversing and cancelling work as for receivables.

## Cash flow (administrator)
In **Finance > Cash flow**, choose the period and whether to see it by **day** or by **month**:
- **Money in** and **Money out**: what was actually received and paid, by payment date;
- **Expected in** and **Expected out**: what is left of the open installments, by due date (overdue ones are flagged "overdue");
- **Balance**: starts from the accounts' balance at the start of the period and adds everything, day by day (or month by month).

Below it you see the **current balance of each account**. For it to match the bank and the drawer, enter each account's **initial balance** in **Records > Accounts** (how much it had before the first entry in the system).

## Reports (administrator)
In **Finance > Reports**, for the chosen period: total received, total paid and the result; received by payment method, by category and by practitioner; and expenses paid by category; with cost centers registered, also what was received and paid by **cost center**, with a "No cost center" line. Reversed payments and cancelled entries are left out.

## Bank statement (administrator)
In **Finance > Bank statement**, import the account's statement, downloaded from the bank's website or app in **OFX** format (sometimes called "Money"). Choose the system account (for example, Banco) and the file. Transactions imported before are skipped, so overlapping periods can be imported. If a line of the file has no readable date or amount, the system tells how many were left out: check those on the bank statement.

Each bank transaction is compared with what the system already has in that account: a receipt or payment **with the same amount, up to 10 days before or after**, or a **daily cash** drawer deposit or withdrawal to that account.
- **Reconcile … with a single match** reconciles at once every transaction with only one possible entry.
- When there is more than one, pick it from the list and click **Reconcile**.
- With nothing in the system (a fee, interest, a Pix nobody recorded), click **Create entry**: the system creates the income or expense already paid on that date and account, and reconciles it.
- What should not become an entry (card machine settlement, transfer between the clinic's accounts) can be **ignored** with a reason.
- **undo** takes the transaction back to pending. If a reconciled payment is reversed, the transaction becomes pending again.

At the top, the **bank balance** stated in the file is compared with the **system balance** on the same date; with everything recorded, the difference is zero.

## Commissions (administrator)
In **Finance > Commissions**, each practitioner has a **percentage** of the amount received on the receivables that name them (an approved estimate already carries the practitioner; on a new entry, choose the practitioner). Entries without a practitioner do not generate commission. The base is the money that came in, after discounts and including late fees, if any.

1. Click **Percentage** to set each practitioner's.
2. Choose the date in **Receipts up to** (for example, the last day of the month) and click **View**: the table shows what was received and not yet paid out, and the commission to pay.
3. Click **Pay**, check the receipts and the due date and click **Add to Payables**. The commission becomes an expense in **Payables**, in the practitioner's name, where you record the payment.

Each receipt enters a commission only once. If a receipt already paid out is **reversed**, its commission is deducted from the next payment to the practitioner (at the percentage of the time). If the commission expense is **cancelled**, the commission is undone and the receipts become pending again. If a later commission already deducted the reversal of one of its receipts, cancel the later one first. Each commission's **Statement** lists the receipts and deductions and can be printed for the practitioner.

## Suppliers
In **Records > Suppliers**, register who the clinic buys from or pays: individual or company, name, legal name, CPF/CNPJ, phone, WhatsApp, e-mail and notes. The system checks the CPF or CNPJ and does not let the same document be registered twice. The supplier's page shows how much is **outstanding** and all their payables, and has a **New expense** button with the supplier already chosen. In the lists, the supplier's name leads to that page. To stop using a supplier without losing the history, uncheck **active**: it leaves the new expense form, and the old bills stay linked to it.

## Closing (administrator)
After checking the cash and handing the reports to the accountant, close the period in **Finance > Closing**: choose **Close up to** (yesterday at the latest). From then on, payments and reversals dated in that period or before it are refused, and that period's reports no longer change. What happens today (receiving, paying, the daily cash) goes on as usual. To fix a mistake, **Reopen** moves the closing back to an earlier date (or reopens everything) and asks for the reason, which stays in the page's history and in the audit log. The Finance role also closes and reopens; the public demo logins only look.

## Cost centers
The cost center tells **who** each income or expense is for: a room, a specialty, the office. The category still tells **what** it is (rent, supplies). In **Records > Cost centers**, the administrator registers the centers. As soon as there is an active one, the **Cost center** field shows up on new entries and new expenses (it is optional), and the reports get the cost center tables. Older entries stay without a center. To stop using a center without losing the history, uncheck **active**.

## Chart of accounts
In **Records > Chart of accounts**, the categories are arranged in **groups**, which can have **subgroups** (as in the accountant's chart of accounts). Each group can have a **code** (1, 2, 3…), and subgroups make numbers such as **2.1**. Entries still go to the categories; the reports add what was received and paid **by group**, each one adding up the ones below it, and a "No group" line. New clinics start with a basic chart, whose names are stored in Portuguese like the default categories ("Atendimentos" and "Outras receitas"; "Ocupação", "Pessoal", "Materiais e laboratório", "Impostos" and "Outras despesas"), and can be renamed; in clinics that already existed, the categories with the default names go into it and the others stay without a group until someone picks one. To move a category to another group, edit the category. A group cannot sit inside itself nor mix income with expenses.

## Categories and accounts
In **Records > Categories** and **Records > Accounts**, the administrator creates new categories (income and expenses) and accounts (cash drawer, bank, card machine). To stop using one without losing the history, uncheck **active**.
