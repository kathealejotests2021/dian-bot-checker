# DIAN citas checker v6

Versión con espera real de la SPA antes de hacer click y clicks por fragmentos visibles, no por `get_by_text(...).first`.

## Cambios principales

- Espera a que aparezca `Agendar cita` o `Gestionar cita` antes de tomar screenshot/click.
- Clicks por fragmento visible: `Agendar cita`, `Persona Natural`, `Videoatención`, `Devoluciones`.
- Evita spans ocultos y contenedores gigantes.
- Agrega logs `Dump visible matches` para diagnosticar qué elementos está viendo el runner.
- Usa raw strings en JS para quitar warnings por `\s`.

## Secrets requeridos en GitHub Actions

Repository secrets:

- `EMAIL_FROM`
- `EMAIL_PASSWORD`
- `EMAIL_TO`

## Ejecutar

Sube los archivos al repo y ejecuta manualmente:

Actions → DIAN citas checker → Run workflow
