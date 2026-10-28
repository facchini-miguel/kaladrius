---
sidebar_position: 1
title: Requisitos
---

# Requisitos

## Servidor

| | Mínimo | Cómodo |
|---|---|---|
| Procesador | 1 vCPU compartida (e2-micro de Google Cloud) | 2 vCPUs |
| Memoria | 1 GB de RAM + 1 GB de swap | 2 GB de RAM |
| Disco | 10 GB | 30 GB (base de datos, imágenes y backups locales) |
| Sistema operativo | Cualquier Linux que ejecute Docker (probado en Debian 13) | |
| Programas | Docker Engine con el plugin Compose, Git | |

La instalación de referencia es una **e2-micro** de Google Cloud (free tier) que atiende una clínica pequeña.

## Red

- Un **dominio** que apunte al servidor: registro `A` (IPv4) y/o `AAAA` (IPv6). Sirve un subdominio gratuito de [DuckDNS](https://www.duckdns.org).
- Puertos **80** y **443** abiertos a internet (443/UDP también, para HTTP/3). Caddy, incluido, obtiene y renueva solo el certificado HTTPS de Let's Encrypt; para eso necesita el puerto 80.
- Un servidor solo con IPv6 solo es accesible desde redes con IPv6. La mayoría de las redes móviles y muchas conexiones de hogar y oficina lo tienen; para atender a todos, dé una dirección IPv4 al servidor.

## Navegadores

Cualquier Chrome, Edge, Firefox o Safari actual, en computadora, tableta o celular.

## Cómo instalar

| Opción | Para quién | Guía |
|---|---|---|
| **Servidor propio** | Cualquier servidor Linux o VPS con Docker | [Servidor propio (Docker Compose)](docker-compose.md) |
| **Free tier de Google Cloud** | Sin costo de servidor; actualización automática, backup diario y monitoreo de la salud del servidor | [Google Cloud](google-cloud.md) |
| **Su computadora** | Evaluación y desarrollo | [Inicio rápido](../quick-start.md) |

## Antes de guardar datos reales de pacientes

Los datos de salud son datos personales sensibles según la LGPD (Brasil) y leyes similares en otros países. Verifique dónde está el servidor (el free tier de Google Cloud está en Estados Unidos, lo que es una transferencia internacional de datos), quién tiene acceso a él, y que los backups funcionen y se guarden de forma segura. Vea [Seguridad y privacidad](../security.md).
