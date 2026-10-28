---
sidebar_position: 3
title: Google Cloud free tier
---

# Google Cloud free tier

The reference installation of Kaladrius runs on the Google Cloud **free tier**, at no monthly cost:

| Resource | Choice | Cost |
|---|---|---|
| VM | `e2-micro` in `us-east1`, `us-west1` or `us-central1`, **standard** disk of 30 GB, Debian | Free tier |
| Address | External **IPv6** only (an IPv4 costs about US$ 3.65/month) | Free |
| Domain | DuckDNS subdomain with an `AAAA` record | Free |
| Images | Artifact Registry (up to 0.5 GB) | Free tier |
| Backups | Cloud Storage bucket in the same region (up to 5 GB), deleted after 30 days | Free tier |

On top of the [own server](docker-compose.md) setup, this installation adds:

- **Automatic updates:** every 5 minutes the VM checks for a new image; when there is one, it installs it and restarts (`deploy/servidor/atualizar.sh`).
- **Daily backup** at 06:00 UTC to Cloud Storage, recorded in the system, with retries (`deploy/servidor/backup.sh`).
- **Server health** every 5 minutes (CPU, memory, swap, disk, network, containers), shown to everyone in **Help > System health** (`deploy/servidor/saude.sh`).
- **1 GB of swap**, needed with 1 GB of RAM.
- No passwords or keys stored for Google: the VM and the CI use short-lived tokens.

## How it works

```
git push (main) ─> GitHub Actions: tests ─> build ─> Artifact Registry
                                                        │ the VM checks every 5 min
                                                        ▼
Browser ──IPv6/HTTPS──> e2-micro VM (no public IPv4)
                         ├─ caddy  (automatic HTTPS)
                         ├─ app    (Django + Gunicorn, 127.0.0.1:8000)
                         ├─ db     (PostgreSQL 16)
                         └─ daily backup ─> Cloud Storage bucket
Maintenance: SSH only through Google's IAP tunnel
```

## Steps

The project's [deploy guide](https://github.com/facchini-miguel/kaladrius/blob/main/docs/en/deploy.md) records every resource of the reference installation. In short:

1. **Project and budget.** Create a Google Cloud project and a budget alert (for example, R$ 5) so any unexpected charge is noticed.
2. **Network.** A VPC with a subnet in the free-tier region with **external IPv6**; reserve the IPv6 address as static (free). Firewall: TCP 80/443 and UDP 443 from `::/0`, ICMPv6, and SSH (22) only from the IAP range `35.235.240.0/20`.
3. **Registry and bucket.** An Artifact Registry repository for the image and a private Cloud Storage bucket with a 30-day deletion rule.
4. **Service accounts.** One for the VM (reads images, writes backups) and one for GitHub Actions through Workload Identity Federation (publishes images), limited to your repository and the `main` branch.
5. **VM.** `e2-micro`, standard disk, no external IPv4, with `deploy/servidor/instalar.sh` as the **startup script**. It installs Docker, creates the swap, installs the systemd timers and starts the system.
6. **Configuration.** Create `/opt/kaladrius/.env` (root only) with the values of [Configuration](../configuration.md), including `SITE_HOSTNAME` and `DUCKDNS_TOKEN`.
7. **Domain.** Create the DuckDNS subdomain and point it to the IPv6:
   ```bash
   curl "https://www.duckdns.org/update?domains=<name>&token=<token>&ipv6=<IPv6 of the VM>"
   ```
8. **First administrator.** Through the IAP tunnel:
   ```bash
   gcloud compute ssh <vm> --zone=<zone> --tunnel-through-iap --command \
     'cd /opt/kaladrius/release && sudo docker compose -f docker-compose.prod.yml exec app python manage.py criar_admin'
   ```

## Day to day

```bash
# Enter the server
gcloud compute ssh <vm> --zone=<zone> --tunnel-through-iap

# On the VM
cd /opt/kaladrius/release
sudo docker compose -f docker-compose.prod.yml ps
sudo docker compose -f docker-compose.prod.yml logs -f app
sudo /opt/kaladrius/bin/atualizar.sh --forcar   # update now
sudo /opt/kaladrius/bin/backup.sh               # backup now
sudo /opt/kaladrius/bin/saude.sh                # server health report
```

## Cautions

- Choose the **standard** disk: the console suggests "balanced", which is charged.
- The free tier exists only in US regions. With real patient data, that is an **international data transfer** under the LGPD (art. 33); assess it, or use the São Paulo region (paid).
- IPv6 only: the system opens only on networks with IPv6. Add an IPv4 to the VM to reach every network.
