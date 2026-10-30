---
sidebar_position: 6.5
---

# Staff

The **Staff** module keeps the clinic's employees, their salaries and each month's overtime and absences, and turns the month's pay into payables in [finance](financeiro.md). Only the administrator and the Finance role see it. It can be turned off in the [clinic settings](clinica.md) and needs Finance on.

Payroll taxes, vacations and the 13th salary are **not** calculated: the accountant or a payroll system takes care of them.

## Employees
In **Finance > Employees**, click **New employee**: name, CPF, job title, hiring date, phone and the **salary** (from the hiring date, unless you choose another date). For a raise, edit the employee and fill in **New salary** and the date it applies from: the previous salary stays in the **salary history**, and each month uses the salary in force at its end. An employee who left gets a **leaving date** and stops appearing in the months after it.

## The month's pay
In **Finance > Month's pay**, choose the month. There is one line per employee working in it, with their salary. Fill in:
- **Overtime**: hours and the hourly rate. The rate comes suggested as salary ÷ 220 hours × 1.5 (the minimum overtime rate for a 44-hour week) and can be changed.
- **Absences**: days missed; each one deducts salary ÷ 30.

The **total** is salary + overtime − absences. **Save** keeps what was typed. **Save and launch into finance** turns each line into a **payable** in the employee's name, in the chosen category (by default "Salários e encargos") and due date. A launched line no longer changes on this page; to redo it, cancel the payable in finance and the line opens again.
