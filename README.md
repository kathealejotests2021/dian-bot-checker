# DIAN citas checker v7

Bot temporal para revisar disponibilidad de citas en https://agendamiento.dian.gov.co/ usando GitHub Actions + Playwright.

## Qué hace esta versión

- Revisa el flujo de citas de la DIAN.
- Envía correo **si no hay citas** con asunto: `DIAN: No hay citas disponibles 😢`.
- Envía correo **si puede haber disponibilidad** con asunto: `DIAN: ¡Posible cita disponible! 🚨`.
- Valida que los secrets de email no estén vacíos antes de ejecutar el bot.
- Sube screenshots como artifact para depuración.

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

## Apagar cuando consigas cita

`Actions` → `DIAN citas checker` → `Disable workflow`
