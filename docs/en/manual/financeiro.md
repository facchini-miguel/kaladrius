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

## Categories and accounts
In **Records > Categories** and **Records > Accounts**, the administrator creates new categories (income and expenses) and accounts (cash drawer, bank, card machine). To stop using one without losing the history, uncheck **active**.
