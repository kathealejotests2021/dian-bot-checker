# DIAN Citas Checker

Bot temporal para revisar disponibilidad de citas en https://agendamiento.dian.gov.co/ usando GitHub Actions cada 20 minutos.

## Archivos incluidos

- `dian_checker.py`: script principal con Playwright.
- `requirements.txt`: dependencias de Python.
- `.github/workflows/dian-checker.yml`: workflow programado cada 20 minutos.
- `.env.example`: ejemplo para pruebas locales.

## Configurar en GitHub

1. Crea un repositorio en GitHub.
2. Sube estos archivos al repositorio.
3. Ve a `Settings` → `Secrets and variables` → `Actions` → `New repository secret`.
4. Crea estos secrets:

```txt
EMAIL_FROM
EMAIL_PASSWORD
EMAIL_TO
```

`EMAIL_PASSWORD` debe ser una contraseña de aplicación de Gmail, no tu contraseña normal.

## Probar manualmente

En GitHub:

`Actions` → `DIAN citas checker` → `Run workflow`

Si falla, revisa el artifact `dian-screenshots` para ver en qué pantalla quedó.

## Ajustar filtros

Edita la función `aplicar_filtros()` en `dian_checker.py` si la DIAN te pide más campos después de:

- Persona Natural
- Videoatención
- Devoluciones.

Puedes generar los selectores desde tu máquina con:

```bash
playwright codegen https://agendamiento.dian.gov.co/
```

Luego copia los clicks/selects generados dentro de `aplicar_filtros()`.

## Desactivar cuando consigas cita

En GitHub:

`Actions` → `DIAN citas checker` → `Disable workflow`
