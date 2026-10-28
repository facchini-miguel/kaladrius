---
sidebar_position: 1
title: Requirements
---

# Requirements

## Server

| | Minimum | Comfortable |
|---|---|---|
| CPU | 1 shared vCPU (Google Cloud e2-micro) | 2 vCPUs |
| Memory | 1 GB RAM + 1 GB swap | 2 GB RAM |
| Disk | 10 GB | 30 GB (database, images and local backups) |
| Operating system | Any Linux that runs Docker (tested on Debian 13) | |
| Software | Docker Engine with the Compose plugin, Git | |

The reference installation is a Google Cloud **e2-micro** (free tier) serving a small clinic.

## Network

- A **domain name** pointing to the server: an `A` record (IPv4) and/or `AAAA` record (IPv6). A free subdomain from [DuckDNS](https://www.duckdns.org) works.
- Ports **80** and **443** open to the internet (443/UDP too, for HTTP/3). Caddy, included, gets and renews the HTTPS certificate from Let's Encrypt by itself; port 80 is needed for that.
- An IPv6-only server is reachable only from networks with IPv6. Most mobile networks and many home and office connections have it; to reach everybody, give the server an IPv4 address.

## Browsers

Any current Chrome, Edge, Firefox or Safari, on computers, tablets and phones.

## Choosing how to install

| Option | For whom | Guide |
|---|---|---|
| **Your own server** | Any Linux server or VPS with Docker | [Own server (Docker Compose)](docker-compose.md) |
| **Google Cloud free tier** | No server cost; automatic updates, daily backups and server health monitoring | [Google Cloud](google-cloud.md) |
| **Your computer** | Evaluation and development | [Quick start](../quick-start.md) |

## Before storing real patient data

Health data is sensitive personal data under the LGPD (Brazil) and similar laws elsewhere. Check where the server is (the Google Cloud free tier is in the United States, which is an international data transfer), who can reach it, and that backups work and are kept safe. See [Security and privacy](../security.md).
