# Documentación de Kaladrius

[🇺🇸 English](../en/README.md) | [🇧🇷 Português](../pt-BR/README.md) | 🇪🇸 Español

| Documento | Contenido |
|---|---|
| [vision-general.md](vision-general.md) | Qué hace el sistema, para quién, módulos y fases |
| [arquitectura.md](arquitectura.md) | Stack, repositorios, infraestructura, seguridad, idiomas |
| [modelo-de-datos.md](modelo-de-datos.md) | Entidades, multiclínica, relación con el sistema antiguo |
| [plan-fase-1.md](plan-fase-1.md) | Plan detallado de la fase 1 (web + datos de prueba) |
| [plan-financiero.md](plan-financiero.md) | Plan del módulo financiero (cuentas por cobrar, por pagar, flujo de caja) |
| [versionado-y-versiones.md](versionado-y-versiones.md) | Cómo numeramos las versiones y registramos las novedades |
| [despliegue.md](despliegue.md) | Publicación en Google Cloud (free tier, IPv6), operación y copias de seguridad |
| [sistema-heredado.md](sistema-heredado.md) | Resumen del antiguo sistema PHP usado como referencia |
| [decisiones/](decisiones/README.md) | Registro de las decisiones técnicas y de producto, con fecha y motivo |
| [manual/](manual/inicio.md) | Manual del usuario (también en el sistema: **Ayuda > Manual del usuario**) |
| [website/](../../website/) | Sitio de documentación público de Kaladrius (Docusaurus, 3 idiomas): instalación, configuración, operación y el manual. `cd website && npm install && npm start` |

## Convenciones
- La documentación se escribe primero en **portugués** (`docs/pt-BR/`) y se traduce al **inglés** (`docs/en/`) y al **español** (`docs/es/`), con la misma estructura. Todo cambio actualiza los tres idiomas en el mismo commit.
- **Los comentarios y docstrings del código se escriben en inglés.** Los textos que ve el usuario (pantallas, mensajes, novedades) se escriben en portugués en el código y se traducen al inglés y al español en `locale/` (ver [arquitectura.md](arquitectura.md#idiomas-version-0130-decision-049)).
- El código usa nombres en **portugués para el dominio** (Paciente, Agendamento) e inglés solo en lo que es del framework.
- Toda decisión importante se registra en `decisiones/`.
- Toda versión publicada tiene una entrada en [`../../releases.yaml`](../../releases.yaml).

## Glosario (términos del dominio que quedan en portugués en el código)

| Portugués | Español |
|---|---|
| Clínica | Clínica (inquilino, *tenant*) |
| Paciente | Paciente |
| Profissional | Profesional (odontólogo, médico…) |
| Agendamento / Agenda | Cita / Agenda |
| Rechamada | Recordatorio de regreso |
| Aniversariantes | Cumpleaños |
| Vínculo | Vínculo de un usuario con una clínica |
| Papel | Perfil (rol) |
| Cadastros | Registros (menú) |
