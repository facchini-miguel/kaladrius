---
sidebar_position: 9
title: Preguntas frecuentes y problemas
---

# Preguntas frecuentes y problemas

## ¿Es solo para dentistas?

No. Agenda, pacientes, recordatorios, presupuestos y finanzas sirven para cualquier clínica. En la Configuración de la clínica, la clínica activa **Odontología**, **Medicina** o las dos (o ninguna, en otra área de la salud): las partes de odontología, como el odontograma en los presupuestos, solo aparecen con Odontología activa. Los módulos comunes (agenda, historia clínica, presupuestos, financiero, recordatorios, cumpleaños, convenios) también pueden desactivarse uno a uno.

## ¿Cuánto cuesta?

El programa es gratuito y de código abierto (Apache 2.0). Solo paga por dónde se ejecuta; en el free tier de Google Cloud, puede ser cero.

## ¿Una instalación atiende varias clínicas?

No: una instalación atiende a una clínica, y nadie elige clínica al ingresar. Para atender a otra clínica, instale el sistema de nuevo (otro servidor, u otro proyecto de Compose en el mismo servidor).

## La página no abre o el certificado falla

- Verifique que el dominio apunte al servidor: `dig +short AAAA clinica.ejemplo.com` (o `A`).
- Verifique que los puertos 80 y 443 estén abiertos en el firewall del servidor y en el proveedor de nube.
- Vea `kaladrius logs caddy`: Let's Encrypt explica por qué lo rechazó.
- En un servidor solo con IPv6, pruebe desde una red con IPv6 (por ejemplo, los datos móviles del celular).

## "Bad Request (400)"

Falta el dominio en `DJANGO_ALLOWED_HOSTS`. Agréguelo y ejecute `kaladrius up -d`.

## "CSRF verification failed" al ingresar

Falta el dominio, con `https://`, en `DJANGO_CSRF_TRUSTED_ORIGINS`.

## Alguien quedó bloqueado después de equivocarse de contraseña

El bloqueo termina solo después de 1 hora. Para liberarlo ahora:

```bash
kaladrius exec app python manage.py axes_reset_username <usuario>
```

## Alguien olvidó la contraseña

El administrador de la clínica define una nueva en **Registros > Equipo > Definir nueva contraseña**. Para el superusuario:

```bash
kaladrius exec app python manage.py changepassword <usuario>
```

## El servidor está lento o se quedó sin memoria

Con 1 GB de RAM, mantenga el swap activado. Todos ven memoria, swap y disco en **Ayuda > Salud del sistema** (instalación en Google Cloud). Con más usuarios, use 2 GB.

## ¿Dónde están los archivos del sistema?

No hay: todo está en la base, así que el backup de la base es el backup del sistema.
