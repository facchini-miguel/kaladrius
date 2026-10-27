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
In **Finance > New expense**, enter the **supplier**, the category, the description and the amount. In **The amount is**, choose:
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
In **Finance > Reports**, for the chosen period: total received, total paid and the result; received by payment method, by category and by practitioner; and expenses paid by category. Reversed payments and cancelled entries are left out.

## Categories and accounts
In **Records > Categories** and **Records > Accounts**, the administrator creates new categories (income and expenses) and accounts (cash drawer, bank, card machine). To stop using one without losing the history, uncheck **active**.
