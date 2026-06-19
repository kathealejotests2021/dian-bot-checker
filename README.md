# DIAN citas checker v8 - Bogotá

Bot temporal para revisar el agendamiento de citas de la DIAN usando GitHub Actions + Playwright.

## Qué hace esta versión

- Ejecuta el flujo:
  1. Agendar cita
  2. Persona Natural
  3. Videoatención
  4. Devoluciones
  5. Trámite de devolución, si aparece
- Ya no alerta solo por citas generales.
- Revisa si en la pantalla final aparece `Bogotá` o `Bogota`.
- Envía correo con:
  - `DIAN: ¡Hay citas en Bogotá! 🚨`
  - `DIAN: No hay citas en Bogotá 😢`
- Guarda screenshots como artifact para depuración.

## Secrets requeridos

En GitHub:

`Settings` → `Secrets and variables` → `Actions` → `New repository secret`

Crear estos 3 repository secrets:

```txt
EMAIL_FROM
EMAIL_PASSWORD
EMAIL_TO
```

`EMAIL_PASSWORD` debe ser la contraseña de aplicación de Gmail de 16 dígitos, no la contraseña normal.

## Probar manualmente

`Actions` → `DIAN citas checker` → `Run workflow`

## Nota sobre el schedule

Si el `schedule` de GitHub no te funciona, deja solo `workflow_dispatch` y usa cron-job.org para disparar el workflow por API.

## Apagar cuando consigas cita

`Actions` → `DIAN citas checker` → `Disable workflow`
