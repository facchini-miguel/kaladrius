---
sidebar_position: 9
title: FAQ and troubleshooting
---

# FAQ and troubleshooting

## Is it only for dentists?

No. Schedule, patients, recalls, estimates and finance serve any clinic. In Clinic settings, the clinic turns on **Dentistry**, **Medicine** or both (or neither, for another health area): the dental parts, such as the dental chart in estimates, only appear with Dentistry on. The shared modules (schedule, medical record, estimates, finance, recalls, birthdays, health plans) can also be turned off one by one.

## How much does it cost?

The software is free and open source (Apache 2.0). You pay only for where it runs; on the Google Cloud free tier, that can be zero.

## Can one installation serve several clinics?

No: one installation serves one clinic, and nobody chooses a clinic when logging in. To serve another clinic, install the system again (another server, or another Compose project on the same one).

## The page does not open or the certificate fails

- Check that the domain points to the server: `dig +short AAAA clinic.example.com` (or `A`).
- Check that ports 80 and 443 are open in the server firewall and in the cloud provider.
- See `kaladrius logs caddy`: Let's Encrypt explains why it refused.
- On an IPv6-only server, test from a network with IPv6 (for example, the phone's mobile data).

## "Bad Request (400)"

The domain is missing from `DJANGO_ALLOWED_HOSTS`. Add it and run `kaladrius up -d`.

## "CSRF verification failed" when logging in

The domain, with `https://`, is missing from `DJANGO_CSRF_TRUSTED_ORIGINS`.

## Someone is locked out after wrong passwords

The lockout ends by itself after 1 hour. To release it now:

```bash
kaladrius exec app python manage.py axes_reset_username <user name>
```

If a whole address was blocked (20 wrong logins from it, whatever the user), release it with `axes_reset_ip <address>` the same way.

## Someone forgot their password

With e-mail configured (`DJANGO_EMAIL_HOST`), the person uses **Forgot my password** on the login page. Otherwise, the clinic administrator sets a new one in **Records > Team > Set new password**. For the superuser:

```bash
kaladrius exec app python manage.py changepassword <user name>
```

## The server is slow or ran out of memory

On 1 GB of RAM, keep the swap on. Everyone sees the memory, swap and disk in **Help > System health** (Google Cloud installation). With more users, use 2 GB.

## Where are the files of the system?

There are none: everything is in the database, so the database backup is the backup of the system.
