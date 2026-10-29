---
sidebar_position: 4
---

# Producción de referencia

Entorno publicado en **https://kaladrius.facchini.eti.br** (acceso solo por **IPv6**), también en https://kaladrius.duckdns.org. Dirección de reserva: https://2600-1900-4020-f0b-0-0-0-0.sslip.io.

- **DNS:** `kaladrius.duckdns.org` (DuckDNS, gratuito) tiene solo un registro AAAA para el IPv6 de la VM. El token está en `DUCKDNS_TOKEN` en el `.env` del servidor y en el `.env.producao` local. Para reapuntar: `https://www.duckdns.org/update?domains=kaladrius&token=<token>&ipv6=<ipv6>` (con `ipv6` informado, DuckDNS no completa el IPv4). Atención: al **crear** un subdominio en el sitio, DuckDNS completa el IPv4 de quien lo creó (su casa); límpielo con `&clear=true` y vuelva a apuntar solo el `ipv6`.
- **Documentación:** el sitio de `docs/` corre en el mismo servidor, en https://kaladrius-docs.facchini.eti.br, también en https://docs.kaladrius.duckdns.org (DuckDNS responde cualquier `*.kaladrius.duckdns.org` con el mismo IPv6, sin crear nada). El CI publica la imagen `docs` junto a la `app`; solo arranca con `COMPOSE_PROFILES=docs` y `DOCS_HOSTNAME` en el `.env` del servidor. Es público y está abierto a los buscadores desde la apertura del código (decisión 077). Para verla en su computadora: `docker compose --profile docs up --build docs` → http://localhost:3000.
- **Dominio del titular:** `kaladrius.facchini.eti.br` y `kaladrius-docs.facchini.eti.br` son CNAMEs en Registro.br a los nombres de DuckDNS, así que siguen el IPv6 sin nada que actualizar. El servidor acepta todos los nombres: `SITE_HOSTNAME`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS` y `DOCS_HOSTNAME` son listas separadas por comas, y Caddy obtiene un certificado por nombre (decisión 084).
- **IPv6 fijo:** dirección reservada `kaladrius-ipv6` (`2600:1900:4020:f0b::`), gratuita; no cambia al reiniciar la VM.

## Arquitectura

```
git push (main) ─> GitHub Actions: pruebas ─> build ─> Artifact Registry (us-east1)
                                                          │ la VM verifica cada 5 min
                                                          ▼
Navegador ──IPv6/HTTPS──> VM e2-micro "kaladrius" (us-east1-b, sin IPv4 público)
                           ├─ caddy  (HTTPS automático Let's Encrypt, red del host)
                           ├─ app    (Django + Gunicorn, solo en 127.0.0.1:8000)
                           ├─ db     (PostgreSQL 16, volumen pgdata)
                           └─ copia diaria 06:00 UTC ─> gs://kaladrius-backups
Mantenimiento: SSH solo por el túnel IAP de Google
```

## Por qué IPv6
Google cobra el IPv4 público de las VM (US$ 0,005/hora, cerca de US$ 3,65/mes; el free tier cubre solo 1 hora/mes). El IPv6 externo es gratuito. Consecuencia: el sistema solo abre en redes con IPv6 (la mayoría de las redes móviles y muchas fijas en Brasil). Para atender cualquier red, basta agregar un IPv4 a la VM (costo arriba). Ver la [página de precios](https://cloud.google.com/vpc/network-pricing).

## Recursos (proyecto `medical-system-facchini`, nombre visible "Kaladrius")

| Recurso | Nombre | Costo |
|---|---|---|
| VM | `kaladrius` (e2-micro, us-east1-b, disco estándar de 30 GB, Debian 13) | Free tier |
| Red | VPC `medical-system`, subred `medical-system-us-east1` (IPv4 interno + IPv6 externo, Private Google Access) | Gratis |
| IPv6 fijo | `kaladrius-ipv6` (`2600:1900:4020:f0b::`, reservado) | Gratis |
| Dominio | `kaladrius.facchini.eti.br` y `kaladrius-docs.facchini.eti.br` (dominio del titular en Registro.br, CNAMEs a DuckDNS); `kaladrius.duckdns.org` (DuckDNS) | Gratis (DuckDNS); el titular paga su dominio |
| Firewall | `medical-system-web-ipv6` (TCP 80/443 y UDP 443 para HTTP/3, desde ::/0), `medical-system-icmpv6`, `medical-system-ssh-iap` (22 solo desde IAP) | Gratis |
| Imágenes | Artifact Registry `kaladrius` (us-east1), limpieza automática (mantiene 5 versiones) | Free tier (0,5 GB) |
| Copias de seguridad | `gs://kaladrius-backups` (us-east1, privado, elimina después de 30 días) | Free tier (5 GB) |
| Cuentas de servicio | `kaladrius-vm` (lee imágenes, guarda copias), `github-ci` (publica imágenes) | Gratis |
| GitHub → Google | Workload Identity Federation (pool `github`), solo el repositorio y la rama `main` | Gratis |
| Alerta de presupuesto | R$ 5 (avisos en 10 %, 50 % y 100 %) | Gratis |

## Cómo funciona el servidor
- `deploy/servidor/instalar.sh` es el *startup script* de la VM: instala Docker, crea 1 GB de swap, instala las tareas programadas de systemd y levanta el sistema. Puede volver a ejecutarse sin problema.
- `deploy/servidor/atualizar.sh` (cada 5 min): descarga la imagen `latest`; si es distinta de la última instalada con éxito (`/opt/kaladrius/imagem-instalada`), extrae los archivos de `deploy/` de la imagen, actualiza las tareas de systemd y reinicia los contenedores. Si algo falla, lo intenta de nuevo en la siguiente vuelta. Las migraciones se ejecutan al iniciar la app.
- `deploy/servidor/backup.sh` (diario): `pg_dump` enviado a Cloud Storage y registrado en el sistema; después, elimina los intentos de acceso rechazados con más de 30 días (`aplicar_retencao`). Si falla, systemd lo intenta de nuevo cada 20 minutos (hasta 4 intentos en 3 horas). Si la última copia registrada tiene más de 26 horas, los superusuarios ven un aviso en la parte superior de las pantallas.
- `deploy/servidor/saude.sh --coletar` (cada 5 min, desde la 0.22.0): lee procesador, memoria, swap, disco, red y carga con comandos de Linux (`/proc`, `df`) y la memoria y el procesador de cada contenedor (`docker stats`), y agrega una línea en `/opt/kaladrius/saude/amostras.jsonl` (7 días guardados, cerca de 1,5 MB). La app lee ese archivo solo en modo lectura y muestra **Administración > Salud del sistema** a los superusuarios, con un aviso arriba de las pantallas si la recolección se detiene o si la memoria, el swap o el disco llegan al nivel crítico. La app no tiene acceso a Docker. Sin argumentos, `saude.sh` muestra un informe en la terminal.
- El compose de producción lee las variables `${...}` del `.env`, enlazado a su lado (`/opt/kaladrius/release/.env` → `../.env`). Solo la app recibe el archivo completo.
- Configuración y contraseñas: `/opt/kaladrius/.env` (solo root). Copia local en `.env.producao`, ignorada por Git.
- Sin claves guardadas: la VM y el CI usan tokens temporales de Google.

## Tareas comunes

```bash
# Entrar al servidor (túnel IAP)
gcloud compute ssh kaladrius --zone=us-east1-b --tunnel-through-iap

# En la VM: estado, logs y comandos de Django
cd /opt/kaladrius/release
sudo docker compose -f docker-compose.prod.yml ps
sudo docker compose -f docker-compose.prod.yml logs -f app
sudo docker compose -f docker-compose.prod.yml exec app python manage.py <comando>

# Forzar la actualización ahora / copia de seguridad ahora
sudo /opt/kaladrius/bin/atualizar.sh --forcar
sudo /opt/kaladrius/bin/backup.sh

# Salud del servidor: ahora, últimas 24 horas, contenedores y tareas programadas
sudo /opt/kaladrius/bin/saude.sh

# Listar las copias de seguridad (en su máquina)
gcloud storage ls -l gs://kaladrius-backups/
```

### Volver a una versión anterior
Lo normal es deshacer el commit (`git revert`) y enviarlo a `main`: el CI publica una imagen nueva y la VM la instala en hasta 5 minutos. En una emergencia, se puede fijar una imagen antigua en la VM (cada versión tiene la etiqueta `X.Y.Z`, que nunca cambia, y cada commit la etiqueta con los 12 primeros caracteres del SHA):

```bash
sudo systemctl stop kaladrius-atualizar.timer   # si no, la VM vuelve a latest en 5 min
cd /opt/kaladrius/release
sudo IMAGEM_APP=us-east1-docker.pkg.dev/medical-system-facchini/kaladrius/app:0.7.0 \
  docker compose -f docker-compose.prod.yml up -d app
# Después de corregir y publicar: sudo systemctl start kaladrius-atualizar.timer
```
Las migraciones no se deshacen: una versión antigua solo funciona si las migraciones nuevas son compatibles con ella (solo agregar tablas y campos, por ejemplo).

### Restaurar una copia de seguridad
```bash
# En la VM (¡reemplaza la base de datos actual!)
gcloud storage cp gs://kaladrius-backups/<archivo>.dump /tmp/restaurar.dump  # o descárguela en su máquina y cópiela con gcloud compute scp --tunnel-through-iap
cd /opt/kaladrius/release
sudo docker compose -f docker-compose.prod.yml exec -T db sh -c 'pg_restore --clean --if-exists -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < /tmp/restaurar.dump
```

### Probar la restauración de una copia de seguridad
Una copia solo vale si vuelve. La prueba se ejecuta en su máquina, en un PostgreSQL temporal: descarga la copia, la restaura (falla ante cualquier error), muestra cuántos registros hay en cada tabla y la última migración, y borra todo al final. No toca el servidor ni la base de desarrollo.

```bash
deploy/testar_backup.sh                   # la copia más reciente
deploy/testar_backup.sh <archivo>.dump    # una específica
```
Hecho el 27/10/2026 con la copia del 26/10 (datos ficticios de esa época): restaurada sin errores en 9 segundos. La misma prueba mostró que la copia automática de ese día había fallado (el servidor estaba entre la 0.7.0 y la 0.8.0, sin el enlace del `.env`) y que el aviso en la web no aparecía cuando **nunca** se había registrado una copia; desde la 0.17.1 los superusuarios también ven ese caso (`DJANGO_BACKUP_MONITORADO`, activado por defecto cuando `DJANGO_DEBUG` está desactivado).

## Cuentas públicas de demostración
La demostración publica dos cuentas en el sitio del titular, `demo.recepcao` y `demo.profissional` (decisión 085). Para crearlas, o para reiniciar las contraseñas:

```bash
docker compose -f docker-compose.prod.yml exec app python manage.py contas_demonstracao \
  --clinica "Clínica Sorriso" --profissional "Dra. Demonstração" --criar-profissional \
  --senha-recepcao <contraseña publicada> --senha-profissional <contraseña publicada>
```

Nunca use allí la contraseña de `DJANGO_SEED_PASSWORD`: los usuarios de prueba, incluido el administrador de prueba, la usan.

### Reinicio diario (decisión 086)
Todos los días a las 07:30 UTC (04:30 en Brasilia, después del respaldo) el servidor restaura una **base** guardada de la demostración, deshaciendo lo que cambiaron los visitantes, y adelanta todas las fechas por las semanas enteras desde que se guardó la base, para que la agenda siempre parezca actual y cada consulta quede en el mismo día de la semana (las fechas de nacimiento no cambian). La lista de respaldos se mantiene. Solo corre con `DJANGO_DEMONSTRACAO=1` en el `.env` del servidor. Para activarlo, una vez:

```bash
echo 'DJANGO_DEMONSTRACAO=1' | sudo tee -a /opt/kaladrius/.env
sudo /opt/kaladrius/bin/reiniciar_demonstracao.sh --salvar-base
```

El reinicio también devuelve **la cuenta y la configuración del titular** a como estaban en la base: después de cambiar una contraseña o una configuración que debe quedar, guarde la base de nuevo (`--salvar-base`). Para reiniciar en el momento: `sudo systemctl start kaladrius-demonstracao.service`.

## Cuidados
- **Datos reales de pacientes:** los datos quedan en EE. UU. (exigencia del free tier). Antes del uso real, revisar la LGPD (transferencia internacional, art. 33) o migrar a la región de São Paulo (paga).
- El disco **estándar** es el gratuito; la consola sugiere "balanced", que se cobra.
- Con datos reales en el servidor, **no ejecute** `popular_dados_teste` en producción: crea usuarios que comparten la misma contraseña (`DJANGO_SEED_PASSWORD`). Para eliminarlos, `remover_dados_teste --confirmar`, que nunca toca clínicas ni usuarios reales.
