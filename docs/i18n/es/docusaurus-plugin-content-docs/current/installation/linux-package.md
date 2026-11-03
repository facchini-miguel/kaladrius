---
sidebar_position: 2
title: Paquete Linux (.deb, .rpm y Arch Linux)
---

# Paquete Linux (.deb, .rpm y Arch Linux)

La forma más simple de instalar Kaladrius en un servidor de la clínica o en un VPS: un paquete de la distribución, que instala Docker por sí solo y hace algunas preguntas en pantallas de texto. Ningún archivo para editar a mano.

## Sistemas admitidos

| Sistema | Paquete | Docker |
|---|---|---|
| Debian 13 o más nuevo, Ubuntu 24.04 o más nuevo | `.deb` | de la propia distribución, instalado junto con el paquete |
| Fedora, openSUSE Tumbleweed | `.rpm` | de la propia distribución, instalado junto con el paquete |
| Arch Linux, CachyOS | `.pkg.tar.zst` (descargado; fuera del repositorio) | de la propia distribución, instalado junto con el paquete. Distribuciones *rolling release*: buenas para probar Kaladrius; para el servidor de una clínica, prefiera uno de los sistemas de arriba |
| Rocky Linux, AlmaLinux, Red Hat Enterprise Linux | `.rpm` | agregue antes el [repositorio de Docker](https://docs.docker.com/engine/install/rhel/) (abajo) |
| Debian 12, Ubuntu 22.04 | `.deb` | su Docker Compose es demasiado antiguo: instale antes los [paquetes del propio Docker](https://docs.docker.com/engine/install/debian/) |

Solo procesadores Intel y AMD de 64 bits (`amd64` / `x86_64`). El servidor necesita los puertos **80** y **443** libres: Kaladrius trae su propio servidor web, Caddy, con HTTPS. Con un firewall activo (firewalld en Fedora, Rocky, AlmaLinux y openSUSE; ufw en Ubuntu), `kaladrius configurar` abre los dos. Memoria y disco: vea [Requisitos](requirements.md).

En Rocky Linux, AlmaLinux y Red Hat Enterprise Linux:

```bash
sudo dnf install -y dnf-plugins-core
sudo dnf config-manager --add-repo https://download.docker.com/linux/rhel/docker-ce.repo
```

## Instalar

### Desde el repositorio de paquetes

Con el repositorio de paquetes de Kaladrius (en [packages.facchini.eti.br](https://packages.facchini.eti.br/kaladrius/)) agregado, sus versiones nuevas llegan con las actualizaciones del propio sistema. En Debian y Ubuntu:

```bash
sudo apt install -y curl ca-certificates
sudo curl -fsSLo /etc/apt/sources.list.d/kaladrius.sources https://packages.facchini.eti.br/kaladrius/deb/kaladrius.sources
sudo apt update
sudo apt install kaladrius
```

Ese único archivo tiene la dirección del repositorio y su clave (el formato deb822 de apt).

En Fedora, Rocky Linux, AlmaLinux y Red Hat Enterprise Linux:

```bash
sudo curl -fsSLo /etc/yum.repos.d/kaladrius.repo https://packages.facchini.eti.br/kaladrius/rpm/kaladrius.repo
sudo dnf install kaladrius
```

En openSUSE:

```bash
sudo zypper addrepo https://packages.facchini.eti.br/kaladrius/rpm/kaladrius.repo
sudo zypper install kaladrius
```

El repositorio y sus paquetes `.rpm` están firmados con la [clave](https://packages.facchini.eti.br/facchini.asc) de packages.facchini.eti.br. Antes de confiar en ella, `dnf` y `zypper` muestran su huella digital, que debe ser `9D3A 0438 FF6C 00F9 1CA1 A0AB A5C3 35B2 EB36 7ABA`.

En Debian y Ubuntu las preguntas aparecen enseguida, en el idioma del servidor (portugués, español o inglés). Con `dnf` y `zypper`, ejecútelas usted mismo después:

```bash
sudo kaladrius configurar
```

### Con un paquete descargado

En Arch Linux y CachyOS, que el repositorio no atiende, o para elegir la versión a mano. Como los de Google Chrome y VS Code, el `.deb` y el `.rpm` agregan el repositorio de paquetes al instalarse (el mismo archivo de arriba, si todavía no está), así que las versiones siguientes llegan igual con las actualizaciones del sistema:

1. Descargue el paquete de la versión más nueva en la [página de releases](https://github.com/facchini-miguel/kaladrius/releases/latest), con el archivo `SHA256SUMS` para verificarlo. Por ejemplo, para la versión 0.54.0:

   ```bash
   curl -fLO https://github.com/facchini-miguel/kaladrius/releases/download/v0.54.0/kaladrius_0.54.0-1_amd64.deb
   curl -fLO https://github.com/facchini-miguel/kaladrius/releases/download/v0.54.0/SHA256SUMS
   sha256sum --ignore-missing -c SHA256SUMS    # debe decir: OK (o CORRECTO)
   ```

   En Fedora, openSUSE, Rocky y AlmaLinux el archivo es `kaladrius-0.54.0-1.x86_64.rpm`; en Arch Linux y CachyOS, `kaladrius-0.54.0-1-x86_64.pkg.tar.zst`.

2. Instálelo:

   ```bash
   sudo apt install ./kaladrius_0.54.0-1_amd64.deb       # Debian y Ubuntu
   sudo dnf install ./kaladrius-0.54.0-1.x86_64.rpm      # Fedora, Rocky, AlmaLinux
   sudo zypper install ./kaladrius-0.54.0-1.x86_64.rpm   # openSUSE
   sudo pacman -Syu && sudo pacman -U ./kaladrius-0.54.0-1-x86_64.pkg.tar.zst   # Arch Linux, CachyOS
   ```

   En Debian y Ubuntu las preguntas aparecen enseguida; con `dnf`, `zypper` y `pacman`, ejecute `sudo kaladrius configurar` después.

Un paquete descargado no está firmado: `dnf` y `zypper` lo avisan ("skipped OpenPGP checks", "unsigned rpm"). Lo que prueba que el archivo es el publicado es la verificación de `SHA256SUMS` de arriba; las actualizaciones que llegan después por el repositorio están firmadas.

## Las preguntas

1. **Cómo accederá la clínica a Kaladrius**
   - **Solo en la red interna de la clínica:** no necesita dominio. El instalador sugiere la dirección IP de este servidor en la red (por ejemplo `192.168.0.10`). Esa dirección no puede cambiar: resérvela para el servidor en el router (*reserva DHCP*), o dele al servidor una IP fija.
   - **Por internet, con dominio:** el dominio (por ejemplo `clinica.ejemplo.com`) ya debe apuntar a este servidor, con los puertos 80 y 443 abiertos a internet, para el certificado gratuito de Let's Encrypt. El instalador verifica el dominio en el DNS y no sigue sin él.
2. **El administrador:** el nombre de usuario (`admin` si no lo cambia), un correo opcional y la contraseña, escrita dos veces. Necesita al menos 10 caracteres, no puede tener solo números ni ser una contraseña común; cuando el sistema la rechaza, la pantalla dice por qué y la pide de nuevo. La contraseña no queda guardada en ningún archivo.

Después el sistema se descarga y se inicia (unos minutos la primera vez), y la última pantalla muestra la dirección para abrir en el navegador. Ingrese con el administrador y siga los [Primeros pasos](../first-steps.md): los datos de la clínica se completan allí.

Para cambiar la dirección después (una IP nueva, o pasar de la red interna a un dominio), ejecute `sudo kaladrius configurar` de nuevo: contraseñas, claves y datos se mantienen.

## Red interna: el certificado

En la red interna el certificado HTTPS lo emite la propia instalación, así que, hasta que las computadoras de la clínica confíen en él, el navegador muestra un aviso de seguridad. Exporte el certificado una vez:

```bash
sudo kaladrius certificado        # guarda kaladrius-certificado.crt en la carpeta actual
```

Copie ese archivo (en un pendrive, por ejemplo) a cada computadora de la clínica e instálelo:

| En | Cómo |
|---|---|
| Windows | doble clic en el archivo > **Instalar certificado** > **Equipo local** > **Colocar todos los certificados en el siguiente almacén** > **Entidades de certificación raíz de confianza** |
| macOS | doble clic > **Acceso a Llaveros**, llavero **Sistema**; luego abra el certificado, **Confiar** > **Confiar siempre** |
| Linux | `sudo cp kaladrius-certificado.crt /usr/local/share/ca-certificates/ && sudo update-ca-certificates` |
| Firefox (cualquier sistema) | **Ajustes** > **Privacidad y seguridad** > **Certificados** > **Ver certificados** > **Autoridades** > **Importar** |
| Android, iPhone | envíe el archivo al dispositivo y ábralo; en el iPhone, después actívelo en **Ajustes** > **General** > **Información** > **Ajustes de confianza de certificados** |

El certificado es solo de esta instalación. Sigue siendo el mismo cuando cambia la dirección del servidor, así que se instala una vez en cada computadora.

## Instalación por un técnico (sin preguntas)

Con todas las opciones y la contraseña del administrador en `KALADRIUS_SENHA_ADMIN`, `configurar` no pregunta nada. `read -rs` deja la contraseña fuera del historial de la terminal:

```bash
sudo DEBIAN_FRONTEND=noninteractive apt install -y ./kaladrius_0.54.0-1_amd64.deb
read -rs KALADRIUS_SENHA_ADMIN && export KALADRIUS_SENHA_ADMIN
sudo --preserve-env=KALADRIUS_SENHA_ADMIN kaladrius configurar \
  --acesso rede-interna --endereco 192.168.0.10 --usuario admin --email ti@clinica.ejemplo
```

`--acesso` es `rede-interna` (red interna) o `internet`; con `internet`, `--endereco` es el dominio. Ante un error (una dirección inválida, una contraseña rechazada) se detiene con el motivo y un código de salida distinto de cero.

Para instalar un paquete descargado sin agregar el repositorio de paquetes (un servidor actualizado a mano, por ejemplo): `sudo KALADRIUS_SEM_REPOSITORIO=1 apt install ./kaladrius_….deb` (o `dnf install`). La elección queda guardada en `/opt/kaladrius/sem-repositorio`, y los paquetes siguientes tampoco lo agregan.

## Comandos del día a día

| Comando | Qué hace |
|---|---|
| `sudo kaladrius estado` | dirección, versión y estado de los servicios |
| `sudo kaladrius saude` | procesador, memoria, disco, las últimas copias y las tareas programadas |
| `sudo kaladrius backup` | hace una copia de seguridad ahora |
| `sudo kaladrius testar-restauracao` | restaura la copia más nueva en una base descartable y la verifica |
| `sudo kaladrius certificado [ARCHIVO]` | el certificado para las computadoras de la red interna |
| `sudo kaladrius senha [USUARIO]` | cambia la contraseña de un usuario (la del administrador si no se indica) |
| `sudo kaladrius logs [app\|db\|caddy]` | los registros de los servicios (Ctrl+C para salir) |
| `sudo kaladrius reiniciar` | reinicia los servicios, aplicando los cambios de `/opt/kaladrius/.env` |
| `sudo kaladrius parar` / `iniciar` | detiene o inicia el sistema; los datos se mantienen |
| `kaladrius ayuda` | la lista de comandos |

## Copias de seguridad

Todos los días a las 06:00 UTC la base se guarda en `/var/backups/kaladrius`, y se conservan los últimos 14 días. Cada domingo la copia más nueva se restaura en una base descartable y se verifica. Cada copia queda registrada en el sistema: los superusuarios ven un aviso arriba de todas las páginas cuando la última tiene más de 26 horas.

:::warning
Una copia en el mismo disco no sobrevive a la pérdida del disco. Copie `/var/backups/kaladrius` todos los días a otra computadora, un disco externo o un almacenamiento en la nube (por ejemplo con `rclone`). Los archivos tienen datos de pacientes: guárdelos en un lugar privado y cifrado.
:::

La carpeta y la cantidad de días son `KALADRIUS_BACKUP_PASTA` y `KALADRIUS_BACKUP_DIAS` en `/opt/kaladrius/.env`. Para restaurar una copia, vea [Copia de seguridad y restauración](../operations/backup-restore.md#paquete-linux).

## Actualizaciones

Haga una copia antes (`sudo kaladrius backup`) y después:

- **Con el repositorio de paquetes** (agregado a mano o por el `.deb` o `.rpm` descargado): `sudo apt update && sudo apt upgrade`, `sudo dnf upgrade` o `sudo zypper update`, junto con el resto del sistema. Una versión nueva llega al repositorio dentro de una hora después de publicada.
- **En Arch Linux y CachyOS, o sin el repositorio:** descargue el paquete de la versión nueva e instálelo de la misma forma (`sudo apt install ./kaladrius_….deb`, `sudo dnf install ./kaladrius-….rpm` o `sudo pacman -U ./kaladrius-….pkg.tar.zst`).

El sistema se reinicia en la versión nueva; las migraciones de la base se ejecutan solas.

**Vuelta automática:** si la versión nueva no responde en 5 minutos, la anterior vuelve sola, con su archivo de Compose y su Caddyfile, y sigue en marcha, y `sudo kaladrius estado` muestra el aviso. `sudo kaladrius reiniciar`, `parar` e `iniciar` la mantienen en la versión anterior; instalar el paquete de nuevo (`sudo apt install --reinstall kaladrius`, `sudo dnf reinstall kaladrius`, `sudo zypper install -f kaladrius` o el archivo descargado) intenta otra vez la nueva.

## Correo y monitoreo (opcionales)

El archivo `/opt/kaladrius/.env` tiene la configuración de correo para la recuperación de contraseña (`DJANGO_EMAIL_*`, vea [Configuración](../configuration.md)) y acepta las direcciones del monitor externo (`MONITOR_*_URL`, vea [Monitoreo](../operations/monitoring.md)). Después de editarlo: `sudo kaladrius reiniciar`.

## Desinstalar

```bash
sudo apt remove kaladrius                      # Debian, Ubuntu
sudo dnf remove --noautoremove kaladrius       # Fedora, Rocky, AlmaLinux
sudo zypper remove kaladrius                   # openSUSE
sudo pacman -R kaladrius                       # Arch Linux, CachyOS
```

El sistema se detiene, y **los datos se mantienen**: la base (volumen Docker `kaladrius_pgdata`), las copias en `/var/backups/kaladrius` y `/opt/kaladrius/.env`, con la contraseña de la base. Instalar el paquete de nuevo trae el sistema de vuelta con ellos. Sin `--noautoremove`, dnf también quita Docker cuando vino con el paquete; los datos se mantienen, pero entonces instalar de nuevo necesita internet para descargar Docker. Borrarlos es irreversible y se hace a mano; los comandos se muestran al quitar el paquete.

El repositorio de paquetes también queda, y `sudo apt install kaladrius` (o `dnf`, `zypper`) trae el sistema de vuelta. Para quitarlo: `sudo apt purge kaladrius` en lugar de `remove` (Debian, Ubuntu; los datos siguen), `sudo rm /etc/yum.repos.d/kaladrius.repo` (Fedora, Rocky, AlmaLinux) o `sudo zypper removerepo kaladrius` (openSUSE).

## Dónde está cada cosa

| Ruta | Qué |
|---|---|
| `/opt/kaladrius/.env` | la configuración y las claves de la instalación (solo root la lee) |
| `/opt/kaladrius/release/` | el archivo de Compose y el Caddyfile de la versión instalada |
| `/opt/kaladrius/bin/` | el comando `kaladrius` y los scripts del servidor |
| `/var/backups/kaladrius/` | las copias diarias |
| `/etc/apt/sources.list.d/kaladrius.sources`, `/etc/yum.repos.d/kaladrius.repo`, `/etc/zypp/repos.d/kaladrius.repo` | el repositorio de paquetes |
| `kaladrius-*.timer` (systemd) | copia, muestras de salud cada 5 minutos, prueba semanal de restauración |
