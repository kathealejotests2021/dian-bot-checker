import os
import re
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


DIAN_URL = "https://agendamiento.dian.gov.co/"
NO_DISPONIBLE_TEXT = "No se encontraron especialidades relacionadas según los filtros seleccionados."
APP_TIMEZONE = "America/Bogota"


class DianCheckerError(Exception):
    pass


def now_colombia() -> str:
    return datetime.now(ZoneInfo(APP_TIMEZONE)).isoformat(timespec="seconds")


def log(message: str):
    print(f"{now_colombia()} - {message}", flush=True)


def screenshot(page, name: str):
    try:
        page.screenshot(path=name, full_page=True)
        log(f"Screenshot guardado: {name}")
    except Exception as e:
        log(f"No se pudo guardar screenshot {name}: {repr(e)}")


def enviar_email():
    email_from = os.environ["EMAIL_FROM"]
    email_password = os.environ["EMAIL_PASSWORD"]
    email_to = os.environ["EMAIL_TO"]

    body = (
        "Posiblemente hay citas disponibles en la DIAN.\n\n"
        "Entra manualmente a revisar y agendar:\n"
        "https://agendamiento.dian.gov.co/\n\n"
        f"Hora de detección: {now_colombia()}"
    )

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = "Posible cita disponible en la DIAN"
    msg["From"] = email_from
    msg["To"] = email_to

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=25) as server:
        server.login(email_from, email_password)
        server.send_message(msg)

    log("Email enviado.")


def wait_visible_text(page, text: str, exact: bool = True, timeout: int = 30_000):
    locator = page.get_by_text(text, exact=exact).first
    locator.wait_for(state="visible", timeout=timeout)
    return locator


def click_text(page, text: str, exact: bool = True, timeout: int = 30_000):
    """
    Click robusto por texto visible.
    Si exact=True falla, intenta una búsqueda flexible con regex.
    """
    log(f"Click en: {text}")

    try:
        locator = wait_visible_text(page, text, exact=exact, timeout=timeout)
    except PlaywrightTimeoutError:
        escaped = re.escape(text.replace(".", "")).replace("\\ ", r"\s+")
        locator = page.get_by_text(re.compile(escaped, re.IGNORECASE)).first
        locator.wait_for(state="visible", timeout=timeout)

    locator.scroll_into_view_if_needed(timeout=timeout)
    locator.click(timeout=timeout)


def aplicar_filtros(page):
    """
    Flujo según las capturas compartidas:

    1. Agendar cita
    2. Persona Natural
    3. Videoatención
    4. Devoluciones.

    Si la DIAN cambia el texto o agrega campos adicionales, ajusta aquí.
    """

    screenshot(page, "dian_01_inicio.png")

    click_text(page, "Agendar cita")
    wait_visible_text(page, "Persona Natural", timeout=40_000)
    screenshot(page, "dian_02_agendar_cita.png")

    click_text(page, "Persona Natural")
    wait_visible_text(page, "Videoatención", timeout=30_000)
    screenshot(page, "dian_03_persona_natural.png")

    click_text(page, "Videoatención")
    wait_visible_text(page, "Devoluciones.", exact=False, timeout=30_000)
    screenshot(page, "dian_04_videoatencion.png")

    # En algunos navegadores el punto final puede romper el exact match.
    click_text(page, "Devoluciones.", exact=False)
    screenshot(page, "dian_05_despues_devoluciones.png")


def revisar_dian() -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--window-size=1366,900",
            ],
        )

        page = browser.new_page(
            viewport={"width": 1366, "height": 900},
            locale="es-CO",
            timezone_id=APP_TIMEZONE,
        )

        try:
            log("Abriendo página DIAN...")
            page.goto(DIAN_URL, wait_until="domcontentloaded", timeout=60_000)

            aplicar_filtros(page)

            try:
                page.get_by_text(NO_DISPONIBLE_TEXT).wait_for(
                    state="visible",
                    timeout=30_000,
                )

                log("Sin citas disponibles. Apareció el mensaje esperado.")
                screenshot(page, "dian_sin_citas.png")
                return "sin_citas"

            except PlaywrightTimeoutError:
                body_text = page.locator("body").inner_text(timeout=10_000)

                if NO_DISPONIBLE_TEXT in body_text:
                    log("Sin citas disponibles. El texto apareció en el body.")
                    screenshot(page, "dian_sin_citas.png")
                    return "sin_citas"

                log("No apareció el mensaje de no disponibilidad. Posible cita disponible.")
                screenshot(page, "dian_posible_disponibilidad.png")
                return "posible_disponibilidad"

        except Exception as e:
            log(f"Error revisando DIAN: {repr(e)}")
            screenshot(page, "dian_error.png")
            raise

        finally:
            browser.close()


def main():
    status = revisar_dian()

    if status == "posible_disponibilidad":
        enviar_email()
    else:
        log("No se envía email porque no hay citas.")


if __name__ == "__main__":
    main()
