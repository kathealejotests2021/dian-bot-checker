# DIAN citas checker v9

Bot temporal para revisar disponibilidad de citas en https://agendamiento.dian.gov.co/ usando GitHub Actions + Playwright.

## Qué hace esta versión

- Abre el flujo de agendamiento DIAN.
- Selecciona `Agendar cita` → `Persona Natural` → `Videoatención` → `Devoluciones`.
- Abre el checklist/dropdown del campo `Trámite`.
- Busca `Bogotá`, `Bogota`, `bogotá` o `bogota` **solo dentro de ese checklist**, no en toda la página.
- Esto evita falsos positivos causados por el footer de la DIAN, que también contiene la palabra Bogotá en la dirección.
- Envía correo con:
  - `DIAN: ¡Hay citas en Bogotá! 🚨`
  - `DIAN: No hay citas en Bogotá 😢`
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

## Screenshot clave

La versión v9 genera:

```txt
dian_09_checklist_tramite_abierto.png
```

Ese screenshot debe mostrar el checklist/dropdown abierto. La decisión de Bogotá se toma únicamente con el texto de ese checklist.

## Apagar cuando consigas cita

`Actions` → `DIAN citas checker` → `Disable workflow`
