---
sidebar_position: 3
title: Free tier de Google Cloud
---

# Free tier de Google Cloud

La instalación de referencia de Kaladrius funciona en el **free tier** de Google Cloud, sin costo mensual:

| Recurso | Elección | Costo |
|---|---|---|
| VM | `e2-micro` en `us-east1`, `us-west1` o `us-central1`, disco **standard** de 30 GB, Debian | Free tier |
| Dirección | Solo **IPv6** externa (una IPv4 cuesta unos US$ 3,65/mes) | Gratis |
| Dominio | Subdominio de DuckDNS con registro `AAAA` | Gratis |
| Imágenes | Artifact Registry (hasta 0,5 GB) | Free tier |
| Backups | Bucket de Cloud Storage en la misma región (hasta 5 GB), borrados a los 30 días | Free tier |

Además de lo que tiene el [servidor propio](docker-compose.md), esta instalación incluye:

- **Actualización automática:** cada 5 minutos la VM busca una imagen nueva; si la hay, la instala y reinicia (`deploy/servidor/atualizar.sh`).
- **Backup diario** a las 06:00 UTC en Cloud Storage, registrado en el sistema, con reintentos (`deploy/servidor/backup.sh`).
- **Salud del servidor** cada 5 minutos (procesador, memoria, swap, disco, red, contenedores), mostrada a los superusuarios en **Administración > Salud del sistema** (`deploy/servidor/saude.sh`).
- **1 GB de swap**, necesario con 1 GB de RAM.
- Ninguna contraseña ni clave de Google guardada: la VM y el CI usan tokens temporales.

## Cómo funciona

```
git push (main) ─> GitHub Actions: pruebas ─> build ─> Artifact Registry
                                                         │ la VM verifica cada 5 min
                                                         ▼
Navegador ──IPv6/HTTPS──> VM e2-micro (sin IPv4 pública)
                           ├─ caddy  (HTTPS automático)
                           ├─ app    (Django + Gunicorn, 127.0.0.1:8000)
                           ├─ db     (PostgreSQL 16)
                           └─ backup diario ─> bucket de Cloud Storage
Mantenimiento: SSH solo por el túnel IAP de Google
```

## Pasos

La [guía de despliegue](https://github.com/facchini-miguel/medical-system/blob/main/docs/es/despliegue.md) del proyecto registra cada recurso de la instalación de referencia. En resumen:

1. **Proyecto y presupuesto.** Cree un proyecto en Google Cloud y una alerta de presupuesto (por ejemplo, R$ 5) para notar cualquier cobro inesperado.
2. **Red.** Una VPC con subred en la región del free tier e **IPv6 externa**; reserve la IPv6 como fija (gratis). Firewall: TCP 80/443 y UDP 443 desde `::/0`, ICMPv6, y SSH (22) solo desde el rango de IAP `35.235.240.0/20`.
3. **Registro y bucket.** Un repositorio en Artifact Registry para la imagen y un bucket privado en Cloud Storage con regla de borrado a los 30 días.
4. **Cuentas de servicio.** Una para la VM (lee imágenes, escribe backups) y una para GitHub Actions mediante Workload Identity Federation (publica imágenes), limitada a su repositorio y a la rama `main`.
5. **VM.** `e2-micro`, disco standard, sin IPv4 externa, con `deploy/servidor/instalar.sh` como **startup script**. Instala Docker, crea el swap, instala las tareas programadas de systemd e inicia el sistema.
6. **Configuración.** Cree `/opt/medical-system/.env` (solo root) con los valores de [Configuración](../configuration.md), incluidos `SITE_HOSTNAME` y `DUCKDNS_TOKEN`.
7. **Dominio.** Cree el subdominio en DuckDNS y apúntelo a la IPv6:
   ```bash
   curl "https://www.duckdns.org/update?domains=<nombre>&token=<token>&ipv6=<IPv6 de la VM>"
   ```
8. **Primer administrador.** Por el túnel IAP:
   ```bash
   gcloud compute ssh <vm> --zone=<zona> --tunnel-through-iap --command \
     'cd /opt/medical-system/release && sudo docker compose -f docker-compose.prod.yml exec app python manage.py criar_admin'
   ```

## En el día a día

```bash
# Entrar al servidor
gcloud compute ssh <vm> --zone=<zona> --tunnel-through-iap

# En la VM
cd /opt/medical-system/release
sudo docker compose -f docker-compose.prod.yml ps
sudo docker compose -f docker-compose.prod.yml logs -f app
sudo /opt/medical-system/bin/atualizar.sh --forcar   # actualizar ahora
sudo /opt/medical-system/bin/backup.sh               # backup ahora
sudo /opt/medical-system/bin/saude.sh                # informe de la salud del servidor
```

## Cuidados

- Elija el disco **standard**: la consola sugiere "balanced", que se cobra.
- El free tier solo existe en regiones de EE. UU. Con datos reales de pacientes, eso es una **transferencia internacional de datos** según la LGPD (art. 33); evalúelo, o use la región de São Paulo (paga).
- Solo IPv6: el sistema solo abre en redes con IPv6. Agregue una IPv4 a la VM para atender cualquier red.
