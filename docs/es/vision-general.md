# Visión general

[🇺🇸 English](../en/overview.md) | [🇧🇷 Português](../pt-BR/visao-geral.md) | 🇪🇸 Español

## Qué es
Sistema de gestión de clínicas (odontológicas, médicas, de fisioterapia, psicología, etc.) con:
- una **web** para el equipo de la clínica (recepción, gestión, profesionales);
- una **app** (Android e iOS) para profesionales y pacientes.

## Público

| Quién | Dónde lo usa | Qué hace |
|---|---|---|
| Recepción / gestión de la clínica | Web | Agenda, registros, recordatorios, informes, usuarios |
| Profesional (odontólogo, médico…) | Web y app | Agenda propia, ficha del paciente |
| Paciente | App | Sus citas, pedir horario, recordatorios (fase 3) |
| Administrador de la plataforma | Web (admin) | Clínicas, planes, soporte |

## Módulos (paridad con el sistema antiguo)

1. **Pacientes:** persona física o jurídica, documentos, dirección, contactos, observaciones. Búsqueda por nombre, código y CPF/CNPJ (identificaciones fiscales brasileñas).
2. **Agenda:** grilla semanal por profesional en horarios configurables (30 min por defecto), con color por tipo de atención, repetición semanal, bloqueo de conflictos, y recordatorios y cumpleaños del día destacados.
3. **Recordatorios:** avisos de regreso (paciente + fecha + descripción).
4. **Cumpleaños:** consulta por mes.
5. **Profesionales:** registro de quienes atienden (antes "Dentistas").
6. **Tablas base:** estados, ciudades, bancos, estado civil, tipos de atención y colores.
7. **Usuarios y permisos:** perfiles por clínica con permisos de ver, crear, modificar y eliminar por módulo. El administrador de la clínica gestiona el equipo en Registros > Equipo (0.8.0).
8. **Novedades:** historial de versiones consultable en el sistema y en la app.
9. **Auditoría:** quién creó, modificó, eliminó o consultó qué y cuándo (LGPD, la ley brasileña de protección de datos).
10. **Idiomas:** portugués, inglés y español, a elección de cada usuario (0.13.0).
11. **Ayuda:** manual del usuario en los tres idiomas dentro del sistema; documentación técnica solo para el superusuario (0.14.0).

## Modelo de negocio (en estudio)
- App **gratuita** en las tiendas.
- Suscripción **paga** de la web para las clínicas, con más funciones.
- Por eso el sistema es **multiclínica** desde el inicio.

## Fases

| Fase | Entrega |
|---|---|
| **1** ✅ | Web del equipo con paridad de funciones + datos de prueba ficticios + Docker local. Concluida en la 0.7.0 y publicada en Google Cloud |
| Financiero | Cuentas por cobrar y por pagar, pagos, deudores, flujo de caja y caja del día (ver [plan-financiero.md](plan-financiero.md)) |
| 2 | API + app para profesionales y equipo |
| 3 | App para pacientes (acceso propio, citas, pedido de horario, push) |
| 4 | Planes, cobro, alta autónoma de clínicas, términos (lanzamiento comercial) |
| Futuro | Recordatorio por WhatsApp, historia clínica, presupuesto y comisión, búsqueda de dirección por código postal |
