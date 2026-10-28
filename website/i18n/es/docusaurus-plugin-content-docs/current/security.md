---
sidebar_position: 7
title: Seguridad y privacidad
---

# Seguridad y privacidad

Kaladrius guarda datos de salud, el tipo más sensible de dato personal. Esta página resume lo que hace el sistema y lo que debe hacer la instalación.

## En el sistema

| Protección | Cómo |
|---|---|
| **Clínicas separadas** | Toda consulta a la base se limita a la clínica en uso; la persona solo llega a las clínicas a las que está vinculada |
| **Perfiles** | Administrador, recepción y profesional; el profesional ve solo su propia agenda y ningún valor de la clínica |
| **Contraseñas** | Guardadas con Argon2; mínimo 10 caracteres, no comunes, no solo números, no parecidas al nombre de usuario |
| **Bloqueo de ingreso** | 5 contraseñas erróneas para el mismo usuario desde la misma dirección lo bloquean por 1 hora |
| **Sesiones** | Hasta 8 horas, terminan al cerrar el navegador; cookies `HttpOnly` y, con `DJANGO_SECURE=1`, `Secure` |
| **HTTPS** | Certificado automático (Caddy); con `DJANGO_SECURE=1`, redirige a HTTPS y usa HSTS de un año |
| **Content Security Policy** | Solo se ejecutan los scripts del propio sistema; sin CDN, sin JavaScript incrustado en la página |
| **Auditoría** | Quién creó, cambió, eliminó o abrió cada registro, cuándo y desde qué dirección; no se puede modificar |
| **Envío de archivos** | Limitado a 6 MB |
| **Documentación de la API** | `/api/v1/docs` solo para superusuarios |

## Privacidad (LGPD)

- **Política de privacidad** en el sistema, en `/privacidade/`, en los tres idiomas: qué se trata, para qué, con qué base legal, quién tiene acceso, dónde se guarda, por cuánto tiempo y los derechos del paciente. Adáptela a su clínica: la clínica es la responsable de los datos. Vea [Política de privacidad](manual/privacidade.md).
- **Los pacientes archivados** salen de las listas y búsquedas; el administrador puede **eliminar definitivamente** al paciente que lo pida, manteniendo la agenda y las finanzas sin su identificación. Vea [Pacientes](manual/pacientes.md).
- **Retención:** los intentos de ingreso rechazados se borran a los 30 días; los backups en Google Cloud, a los 30 días.
- **Sin rastreo:** solo las cookies de sesión y de seguridad; sin analytics, sin scripts de terceros.

## Lo que debe hacer la instalación

- Dejar el `.env` legible solo por root, con una `DJANGO_SECRET_KEY` larga y contraseñas fuertes. Nunca ponerlo en Git.
- Ejecutar con `DJANGO_DEBUG=0`, `DJANGO_SECURE=1` y `DJANGO_PROXY_REVERSO=1` detrás de Caddy.
- Nunca ejecutar `popular_dados_teste` en un servidor con datos reales (sus usuarios comparten la contraseña).
- Exponer solo los puertos 80 y 443. La base y la app escuchan solo dentro del servidor.
- Restringir el SSH (solo con clave; en Google Cloud, solo por el túnel IAP).
- Hacer backup todos los días, guardar una copia cifrada fuera del servidor y [probar la restauración](operations/backup-restore.md).
- Saber dónde están los datos: un servidor fuera de Brasil es una transferencia internacional según la LGPD (art. 33).
- Mantener el sistema [actualizado](operations/upgrade.md).

## Cómo informar una vulnerabilidad

Por favor, **no** abra un issue público. Infórmela en privado por [GitHub Security Advisories](https://github.com/facchini-miguel/kaladrius/security/advisories/new), con los pasos para reproducirla. Recibirá respuesta en pocos días.
