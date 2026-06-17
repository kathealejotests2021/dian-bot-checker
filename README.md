# DIAN citas checker

Bot temporal para revisar disponibilidad de citas en https://agendamiento.dian.gov.co/ usando GitHub Actions + Playwright.

## Flujo configurado

Según las capturas compartidas, el bot hace:

1. `Agendar cita`
2. `Persona Natural`
3. `Videoatención`
4. `Devoluciones.`

Después espera el mensaje:

```text
No se encontraron especialidades relacionadas según los filtros seleccionados.
```

Si el mensaje aparece, asume que no hay citas. Si no aparece, envía un correo.

## Secrets requeridos en GitHub

En el repositorio:

`Settings` → `Secrets and variables` → `Actions` → `New repository secret`

Crea:

```text
EMAIL_FROM
EMAIL_PASSWORD
EMAIL_TO
```

`EMAIL_PASSWORD` debe ser una contraseña de aplicación de Gmail, no la contraseña normal.

## Ejecutar manualmente

En GitHub:

`Actions` → `DIAN citas checker` → `Run workflow`

## Programación

Corre cada 20 minutos entre 8:00 a. m. y 7:00 p. m. hora Colombia.

## Ver capturas si falla

Cada ejecución sube un artifact llamado `dian-screenshots` con capturas como:

```text
dian_01_inicio.png
dian_02_agendar_cita.png
dian_03_persona_natural.png
dian_04_videoatencion.png
dian_05_despues_devoluciones.png
dian_error.png
```

## Apagar cuando consigas la cita

Ve a:

`Actions` → `DIAN citas checker` → `Disable workflow`


## v5

Esta versión corrige el caso en el que `get_by_text("Agendar cita").first` apunta a un `<span>` oculto. Ahora intenta primero coordenadas sobre la tarjeta y usa una búsqueda que ignora nodos ocultos.


## v5

Esta versión agrega clicks robustos para las tarjetas `Persona Natural`, `Videoatención`, `Devoluciones.` y el botón `Siguiente`.

Flujo actual:

1. Agendar cita
2. Persona Natural
3. Siguiente
4. Videoatención
5. Siguiente
6. Devoluciones.
7. Siguiente opcional si la UI lo exige
