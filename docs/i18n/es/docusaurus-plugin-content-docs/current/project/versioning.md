---
sidebar_position: 5
---

# Versionado y versiones

## Número de versión: `MAYOR.MENOR.CORRECCIÓN`

Seguimos el [Versionado Semántico](https://semver.org/lang/es/):

| Parte | Cuándo aumenta | Ejemplo |
|---|---|---|
| **MAYOR** | Cambio grande, que rompe la compatibilidad (ej.: la app antigua deja de funcionar con el servidor nuevo) | 1.4.7 → **2.0.0** |
| **MENOR** | **Función nueva** o mejora relevante, compatible | 1.4.7 → **1.5.0** |
| **CORRECCIÓN** | **Corrección de un error** o ajuste pequeño | 1.4.6 → **1.4.7** |

- Durante el desarrollo usamos `0.x.y`. La versión **1.0.0** es la primera usada por una clínica real.
- Cuando sube la MENOR, la CORRECCIÓN vuelve a cero. Cuando sube la MAYOR, las dos vuelven a cero.
- La app (`kaladrius-app`) tiene su propia numeración e indica la versión mínima del servidor que necesita.

## Dónde están las novedades: `releases.yaml`

El archivo [`../../releases.yaml`](https://github.com/facchini-miguel/kaladrius/blob/main/releases.yaml) es la **única fuente** del historial. De él salen:
- la página **Novedades** dentro del sistema web;
- el endpoint de la API que la app usa para mostrar "Qué hay de nuevo";
- el número de versión que aparece en el pie de página del sistema;
- las *Releases* de GitHub, en inglés (comando `release_notes`).

Los textos se escriben en los **tres idiomas de la interfaz** (`pt-br`, `en`, `es`; decisión 049). Los nombres de los campos están en inglés (decisión 189); los valores (`novo`, `equipe`, los módulos) quedan en portugués.

### Formato

```yaml
- version: 1.5.0
  date: 2027-03-10
  title:
    pt-br: Lembretes de retorno no app
    en: Recall reminders in the app
    es: Recordatorios de regreso en la app
  items:
    - kind: novo            # novo | melhoria | correcao | seguranca
      module: Rechamadas    # uno de los nombres de MODULES en apps/whats_new/releases.py
      audience: [equipe, paciente]
      text:
        pt-br: >
          O paciente recebe no celular um aviso 7 dias antes da data de retorno.
        en: >
          Patients get a notice on their phone 7 days before the recall date.
        es: >
          El paciente recibe en el celular un aviso 7 días antes de la fecha de regreso.
```

| Campo | Obligatorio | Descripción |
|---|---|---|
| `version` | sí | Número en el formato `MAYOR.MENOR.CORRECCIÓN` |
| `date` | sí | Fecha de publicación (AAAA-MM-DD) |
| `title` | no | Lo más destacado de la versión, en una frase, en los tres idiomas |
| `items[].kind` | sí | `novo`, `melhoria`, `correcao` o `seguranca` |
| `items[].module` | sí | Área del sistema (Agenda, Pacientes…), en portugués; la pantalla muestra la traducción |
| `items[].audience` | sí | Quién ve el ítem: `equipe`, `paciente` o ambos |
| `items[].source` | no | `dependabot` para una actualización propuesta por Dependabot; se omite en los cambios del propio proyecto (decisión 133) |
| `items[].pr` | con `source` | Número del pull request; la página y el release de GitHub enlazan a él |
| `items[].text` | sí | **Pocas líneas**, en lenguaje de usuario: qué cambió y cómo usarlo. Un texto por idioma (`pt-br`, `en`, `es`); una prueba exige los tres |

### Reglas de redacción
- Escribir para el **usuario**, no para el programador. Por ejemplo, "La agenda ahora muestra…", y no "Refactorizado el componente X".
- Como máximo 3 líneas por ítem.
- Las correcciones de seguridad no describen la falla, solo que se corrigió.
- Los ítems solo internos (infraestructura, refactorización) no entran, o entran con `audience: []`, y entonces no aparecen para nadie.
- Los pacientes solo ven ítems con `paciente` en `audience`.
- Todo ítem de un pull request de Dependabot tiene `source: dependabot` y su `pr`: las Novedades muestran la etiqueta "Dependabot · #N" y el release de GitHub agrega "(Dependabot, #N)", para distinguir los cambios del titular de los de Dependabot.

## Cómo aparece

**Web (equipo):** menú **Ayuda → Novedades**, con las versiones de la más nueva a la más antigua, íconos por tipo (nuevo, mejora, corrección, seguridad) y filtro por módulo. Después de una actualización, aparece un aviso "El sistema se actualizó a la versión X.Y.Z" hasta que el usuario abre la página.

**App:** pantalla **Novedades** en el menú y, al abrir una versión nueva por primera vez, un resumen "Qué hay de nuevo". Usa el endpoint (los textos vienen en el idioma de `Accept-Language`):

```
GET /api/v1/releases?since=1.4.0&audience=paciente
```

## Proceso para publicar una versión
1. Agregar la entrada al inicio de `releases.yaml` en el mismo pull request del cambio.
2. Actualizar la versión del proyecto (`pyproject.toml`) y la línea "Versión actual" de los tres README. Las pruebas fallan si alguno queda distinto de `releases.yaml`.
3. **El CI crea solo la etiqueta Git `vX.Y.Z` y la *Release* de GitHub** **en inglés**, después de publicar la imagen, cuando la versión es nueva (decisión 119); con el secreto `SITE_TOKEN` también reconstruye el sitio del titular, que si no toma la versión en menos de una hora. El título y el texto son los que genera el comando (útil para revisarlos antes):
   ```bash
   docker compose exec app python manage.py release_notes X.Y.Z --title   # título
   docker compose exec app python manage.py release_notes X.Y.Z            # texto
   ```
4. El CI valida `releases.yaml` (formato, versión mayor que la anterior, fecha, los tres idiomas) antes del despliegue.

El servidor lee `releases.yaml` una vez y lo guarda en memoria. En desarrollo, después de editarlo, reinicie la app (`docker compose restart app`).
