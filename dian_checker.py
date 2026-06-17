import os
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

DIAN_URL = "https://agendamiento.dian.gov.co/"
NO_DISPONIBLE_TEXT = "No se encontraron especialidades relacionadas según los filtros seleccionados."
APP_TIMEZONE = "America/Bogota"


def now_colombia() -> str:
    return datetime.now(ZoneInfo(APP_TIMEZONE)).isoformat(timespec="seconds")


def log(message: str):
    print(f"{now_colombia()} - {message}", flush=True)


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


def click_text(page, text: str, timeout: int = 20_000):
    log(f"Click en: {text}")
    page.get_by_text(text, exact=True).first.click(timeout=timeout)


def aplicar_filtros(page):
    """
    Ajusta este flujo si la DIAN te pide más campos.

    Para obtener el flujo real desde tu máquina:
        playwright codegen https://agendamiento.dian.gov.co/

    Luego copias aquí los clicks/selects generados.
    """

    click_text(page, "Persona Natural")
    click_text(page, "Videoatención")
    click_text(page, "Devoluciones.")

    # Si después aparecen más campos, agrégalos aquí.
    # Ejemplos:
    #
    # page.get_by_label("Departamento").select_option("Bogotá")
    # page.get_by_label("Ciudad").select_option("Bogotá D.C.")
    # page.get_by_text("Continuar").click()


def revisar_dian() -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
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
                    timeout=25_000,
                )

                log("Sin citas disponibles. Apareció el mensaje esperado.")
                page.screenshot(path="dian_sin_citas.png", full_page=True)
                return "sin_citas"

            except PlaywrightTimeoutError:
                body_text = page.locator("body").inner_text(timeout=10_000)

                if NO_DISPONIBLE_TEXT in body_text:
                    log("Sin citas disponibles. El texto apareció en el body.")
                    page.screenshot(path="dian_sin_citas.png", full_page=True)
                    return "sin_citas"

                log("No apareció el mensaje de no disponibilidad. Posible cita disponible.")
                page.screenshot(path="dian_posible_disponibilidad.png", full_page=True)
                return "posible_disponibilidad"

        except Exception as e:
            log(f"Error revisando DIAN: {repr(e)}")
            try:
                page.screenshot(path="dian_error.png", full_page=True)
            except Exception:
                pass
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
