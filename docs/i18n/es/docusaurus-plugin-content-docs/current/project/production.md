---
sidebar_position: 4
---

# Producción de referencia

Publicada en **https://kaladrius.facchini.eti.br** (IPv4 e IPv6), también en https://kaladrius.duckdns.org. El sitio de documentación está en **https://kaladrius-docs.facchini.eti.br**, también en https://docs.kaladrius.duckdns.org. Desde el 09/11/2026 los dos corren en la VPS del titular, gestionados con [Dokploy](https://dokploy.com) (decisión 208); antes, en una VM del free tier de Google Cloud, solo con IPv6.

- **DNS:** en Registro.br, `kaladrius` y `kaladrius-docs` tienen un registro `A` (`179.66.139.4`) y un `AAAA` (`2a02:4780:95:91b7::1`). Registro.br rechaza un CNAME y un A/AAAA con el mismo nombre en un mismo guardado: para cambiar un CNAME por A/AAAA, guarde primero la eliminación y después los registros nuevos. `kaladrius.duckdns.org` apunta a las mismas dos direcciones (`https://www.duckdns.org/update?domains=kaladrius&token=<token>&ip=<ipv4>&ipv6=<ipv6>`; el token es el `DUCKDNS_TOKEN` del `.env` del servidor), y DuckDNS responde cualquier `*.kaladrius.duckdns.org` con ellas.
- **Nombres:** el servidor acepta todos los nombres. `SITE_HOSTNAME`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS` y `DOCS_HOSTNAME` son listas separadas por comas, y Traefik obtiene un certificado por nombre, cada uno con su propio enrutador, así que un nombre cuyo DNS aún no está listo no frena a los demás.
- **Documentación:** pública y abierta a los buscadores desde la apertura del código (decisiones 077 y 207). Para verla en su computadora: `docker compose --profile docs up --build docs` → http://localhost:3000.

## Arquitectura

```
git push (main) ─> GitHub Actions: pruebas, build de la docs ─> imagen en ghcr.io
                                                                 │ el servidor revisa cada 5 min
                                                                 ▼
Navegador ──IPv4/IPv6, HTTPS──> VPS (Ubuntu 24.04, Hostinger, Boston, EE. UU.)
                                 ├─ traefik  (proxy de Dokploy: HTTPS Let's Encrypt, puertos 80/443)
                                 └─ Compose "kaladrius" de Dokploy
                                     ├─ app   (Django + Gunicorn, imagen de ghcr.io)
                                     ├─ db    (PostgreSQL 16, volumen pgdata)
                                     └─ docs  (generada de docs/ de main en cada deploy)
Respaldo diario 06:00 UTC ─> /var/backups/kaladrius (30 días)
Mantenimiento: SSH solo con llave (sin contraseña, sin root); panel de Dokploy solo por túnel SSH
```

## Servidor

| Elemento | Valor |
|---|---|
| Máquina | VPS en Hostinger (Boston, EE. UU.): 8 vCPU, 32 GB de RAM, 400 GB de disco, Ubuntu 24.04 |
| Acceso | `ssh facchini@179.66.139.4`, solo con llave; `sudo` para administrar |
| Firewall | ufw: solo 22, 80 y 443. Docker publica puertos por fuera de ufw, así que el panel de Dokploy (3000) queda cerrado a internet por una regla en la cadena `DOCKER-USER` (`bloquear-painel-dokploy.service`) |
| Dokploy | proyecto **Kaladrius**, Compose **kaladrius** (archivo Compose guardado en el propio Dokploy). El panel: `ssh -L 3000:localhost:3000 facchini@179.66.139.4` y después http://localhost:3000 |
| Configuración | el entorno del Compose en Dokploy (escrito como `.env` junto al archivo Compose). Viene del `.env` de Google Cloud, sin el nombre `sslip.io` |

El archivo Compose sigue `deploy/docker-compose.prod.yml`, con Traefik en lugar de Caddy: las etiquetas dan HTTPS a cada nombre, redirigen HTTP a HTTPS, comprimen las respuestas, quitan el encabezado `Server` y limitan el cuerpo de una solicitud a 11 MB (el mayor envío legítimo es un adjunto de 10 MB de la historia clínica, como el `request_body` del Caddyfile). La app confía en la dirección del cliente que Traefik pone al final de `X-Forwarded-For` (`DJANGO_REVERSE_PROXY=1`).

**La documentación no depende del app** (decisión 209): sus rutas usan middlewares de Traefik propios (`kaladrius-docs-comprime`, `kaladrius-docs-sem-server`, `kaladrius-docs-https`), declarados en el servicio `docs`. Cuando usaban los declarados en `app`, Traefik quitaba las rutas de la documentación cada vez que el app se detenía (el reinicio nocturno, cada actualización). `update-dokploy.sh`, como `reset_demo.sh`, marca la parada como mantenimiento, para que `health.sh` no la informe.

## Cómo funciona el servidor

Los scripts de `deploy/server/` corren tal como están, desde `/opt/kaladrius/bin`, con las units de systemd del repositorio. `/opt/kaladrius` los conecta al Compose de Dokploy:

- `release/docker-compose.prod.yml` y `release/.env` son enlaces al archivo Compose y al `.env` de Dokploy. El `.env` da el nombre del proyecto Compose (`COMPOSE_PROJECT_NAME`), así que `docker compose -f /opt/kaladrius/release/docker-compose.prod.yml` llega a los contenedores que Dokploy levantó.
- `/opt/kaladrius/.env` es una copia sin comillas, que `sync-env.py` vuelve a escribir antes de cada unit `kaladrius-*` (drop-in `/etc/systemd/system/kaladrius-.service.d/env.conf`). Dokploy escribe `CLAVE="valor"`, que Docker Compose entiende, pero `env_value` de `common.sh` lee la línea tal cual: con comillas, `DJANGO_DEMO="1"` nunca sería igual a `1` y las direcciones de los monitores quedarían inválidas. Cambie la configuración en Dokploy, nunca en esa copia.
- `release/linux-package` pone los scripts en el modo de una instalación en servidor propio (decisión 140): respaldos y prueba de restauración en una carpeta local, y los sitios revisados desde el propio servidor. La imagen y las actualizaciones quedan con Dokploy.

| Timer | Qué hace |
|---|---|
| `kaladrius-update.timer` (cada 5 min) | `update-dokploy.sh`: descarga `ghcr.io/facchini-miguel/kaladrius:latest`; si es distinta de la app en marcha, pide a Dokploy un deploy del Compose (app nueva, docs generada de nuevo de main), espera `/api/v1/health` y avisa a `MONITOR_UPDATE_URL`. Las migraciones corren cuando la app arranca. Aquí no hay la vuelta automática de la decisión 135: vea abajo |
| `kaladrius-backup.timer` (06:00 UTC) | `backup.sh`: `pg_dump` en `/var/backups/kaladrius`, guardando `KALADRIUS_BACKUP_DAYS` (30) días; lo registra en el sistema y aplica la retención de 30 días de los inicios de sesión rechazados |
| `kaladrius-restore-test.timer` (domingos 07:00 UTC) | `test_restore.sh`: restaura el respaldo más nuevo en una base desechable y lo revisa |
| `kaladrius-demo-reset.timer` (07:30 UTC) | `reset_demo.sh`: el reinicio diario de la demostración (abajo) |
| `kaladrius-health.timer` (cada 5 min) | `health.sh --collect`: las muestras de **Administración > Salud del sistema** (`/opt/kaladrius/health`) y los monitores de los sitios, certificados y recursos |
| `backup-dokploy.timer` (05:30 UTC) | la base del propio Dokploy y `/etc/dokploy` en `/var/backups/dokploy` (14 días) |

Los monitores externos (Healthchecks.io, decisión 078) son los `MONITOR_*_URL` del `.env`, los mismos de Google Cloud. Por dentro, el Prometheus y el Grafana del VPS (https://grafana.facchini.eti.br, repositorio `facchini-miguel/grafana.facchini.eti.br`) muestran la máquina, los contenedores, Traefik, la base (rol `monitoring`, solo estadísticas) y, por `/opt/kaladrius/metrics`, los backups, reinicios, pruebas de restauración y actualizaciones (decisión 211).

**Por ahora los respaldos quedan en el disco de la VPS.** Falta elegir dónde guardar una copia fuera de ella. Los 18 respaldos del bucket de Google Cloud (26/10 al 09/11) están en `/var/backups/kaladrius/google`.

## Tareas comunes

```bash
# Entrar al servidor
ssh facchini@179.66.139.4

# En el servidor: estado, logs y comandos de Django
cd /opt/kaladrius/release
sudo docker compose -f docker-compose.prod.yml ps
sudo docker compose -f docker-compose.prod.yml logs -f app
sudo docker compose -f docker-compose.prod.yml exec app python manage.py <comando>

# Actualizar ahora / respaldo ahora
sudo systemctl start kaladrius-update.service
sudo systemctl start kaladrius-backup.service

# Salud del servidor: ahora, últimas 24 horas, contenedores y timers
sudo /opt/kaladrius/bin/health.sh

# Listar los respaldos
sudo ls -l /var/backups/kaladrius
```

### Volver a una versión anterior
El camino normal es revertir el commit (`git revert`) en una rama y llevarlo a `main` por pull request (`main` no recibe otra cosa, decisión 141; el administrador puede hacer push directo, pasando por encima del ruleset): el CI publica una imagen nueva y el servidor la instala hasta 5 minutos después del merge. En una emergencia, se puede fijar una imagen vieja (cada versión tiene en ghcr.io una etiqueta `X.Y.Z` que nunca se mueve, y cada commit una etiqueta con los 12 primeros caracteres del SHA): detenga `kaladrius-update.timer`, cambie el `image:` de la app en el archivo Compose de Dokploy por `ghcr.io/facchini-miguel/kaladrius:<etiqueta>` y haga el deploy. Después de corregir y publicar, vuelva a `latest` y encienda el timer de nuevo.

Las migraciones no se deshacen: una versión vieja solo funciona si las migraciones nuevas son compatibles con ella (tablas nuevas, o campos que pueden quedar vacíos o tienen `db_default`, por ejemplo; el informe de migraciones de cada pull request señala el resto, decisión 139).

### Restaurar un respaldo
```bash
# En el servidor (¡reemplaza la base de datos actual!)
cd /opt/kaladrius/release
sudo docker compose -f docker-compose.prod.yml exec -T db sh -c 'pg_restore --clean --if-exists -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < /var/backups/kaladrius/<archivo>.dump
```

### Probar la restauración de un respaldo
Un respaldo solo vale si vuelve. El servidor prueba el más nuevo cada domingo (`kaladrius-restore-test.timer`), en una base desechable que nunca toca la real; para probar ahora, `sudo systemctl start kaladrius-restore-test.service`. (`deploy/test_backup.sh` prueba en su máquina los respaldos de un bucket de Google Cloud, el modo de una instalación en Google Cloud.)

Hecho el 09/11/2026, en el paso a la VPS: el dump de producción se restauró sin errores (9 usuarios, 1.093 pacientes, 19.446 citas), y la prueba de restauración pasó con el primer respaldo de la VPS.

## Cuentas públicas de demostración
La demostración publica una cuenta de cada perfil en el sitio del titular: `demo.recepcao`, `demo.profissional`, `demo.financeiro` y `demo.admin` (decisiones 085 y 089). Por ser de demostración, nunca cambian la contraseña, envían adjuntos, cambian el equipo o la configuración de la clínica, ni ven las IP en la auditoría. Para crearlas, o para reiniciar las contraseñas:

```bash
docker compose -f docker-compose.prod.yml exec app python manage.py demo_accounts \
  --clinic "Clínica Sorriso" --practitioner "Dra. Demonstração" --create-practitioner \
  --front-desk-password <contraseña publicada> --practitioner-password <contraseña publicada> \
  --finance-password <contraseña publicada> --admin-password <contraseña publicada>
```

Nunca use allí la contraseña de `DJANGO_SEED_PASSWORD`: los usuarios de prueba, incluido el administrador de prueba, la usan.

### Reinicio diario (decisión 086)
Todos los días a las 07:30 UTC (04:30 en Brasilia, después del respaldo) el servidor restaura una **base** guardada de la demostración, deshaciendo lo que cambiaron los visitantes, y adelanta todas las fechas por las semanas enteras desde que se guardó la base, para que la agenda siempre parezca actual y cada consulta quede en el mismo día de la semana (las fechas de nacimiento no cambian). La lista de respaldos se mantiene. Solo corre con `DJANGO_DEMO=1` en el `.env` del servidor (en Dokploy). La base es `/opt/kaladrius/demo/base.dump`, traída de Google Cloud (guardada el 07/11/2026) y guardada otra vez en el VPS el 11/11/2026, justo después de un reinicio, para que el reinicio ya no reaplique las migraciones desde 0.62 (decisión 209). Su fecha (`base-date`) sigue siendo 07/11/2026, la fecha de las citas en ella: una base guardada justo después de un reinicio todavía tiene las fechas de la base anterior, ya que el reinicio solo las mueve después de una semana entera. Para guardarla de nuevo:

```bash
sudo /opt/kaladrius/bin/reset_demo.sh --save-base
```

Las cuentas de los **administradores del sistema** (superusuarios) se mantienen en el reinicio (decisión 118): contraseña, correo, idioma, verificación en dos pasos y códigos de recuperación quedan como estaban. El resto de la configuración **del titular** (la de la clínica, por ejemplo) vuelve a la base: después de cambiar una que debe quedar, guarde la base de nuevo (`--save-base`). Para reiniciar en el momento: `sudo systemctl start kaladrius-demo-reset.service`.

## Cuidados
- **Datos reales de pacientes:** el servidor está en Estados Unidos. Antes del uso real, revisar la LGPD (transferencia internacional, art. 33) o pasar a un servidor en Brasil.
- Con datos reales en el servidor, **no ejecute** `seed_sample_data` en producción: crea usuarios que comparten la misma contraseña (`DJANGO_SEED_PASSWORD`). Para eliminarlos, `remove_sample_data --confirm`, que nunca toca clínicas ni usuarios reales.
- La llave de API de Dokploy (`~/.dokploy-api-key` de `facchini` en el servidor) es lo que permite a `update-dokploy.sh` hacer el deploy: cuando venza o se revoque, las actualizaciones se detienen y `MONITOR_UPDATE_URL` avisa.
