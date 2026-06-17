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


def _flexible_text_locator(page, text: str):
    escaped = re.escape(text.replace(".", "")).replace("\\ ", r"\s+")
    return page.get_by_text(re.compile(escaped, re.IGNORECASE)).first


def click_text(page, text: str, exact: bool = True, timeout: int = 30_000):
    """
    Click robusto por texto visible.
    Si exact=True falla, intenta una búsqueda flexible con regex.
    """
    log(f"Click en texto: {text}")

    try:
        locator = wait_visible_text(page, text, exact=exact, timeout=timeout)
    except PlaywrightTimeoutError:
        locator = _flexible_text_locator(page, text)
        locator.wait_for(state="visible", timeout=timeout)

    locator.scroll_into_view_if_needed(timeout=timeout)
    locator.click(timeout=timeout)


def esperar_pantalla_persona_natural(page, timeout: int = 40_000):
    wait_visible_text(page, "Persona Natural", timeout=timeout)


def click_agendar_cita(page):
    """
    En la primera pantalla, el click directo sobre el texto 'Agendar cita'
    a veces no dispara la navegación porque el listener está en la tarjeta.
    Por eso se intenta:
      1. Click normal sobre el texto.
      2. Click en el centro aproximado de la tarjeta, calculado desde el texto.
      3. Click JS sobre los ancestros del texto.
    """
    log("Click robusto en tarjeta: Agendar cita")

    locator = wait_visible_text(page, "Agendar cita", timeout=40_000)
    locator.scroll_into_view_if_needed(timeout=10_000)

    def normal_click():
        locator.click(timeout=10_000)

    def card_mouse_click():
        box = locator.bounding_box(timeout=10_000)
        if not box:
            raise DianCheckerError("No se pudo obtener bounding box de Agendar cita")

        # En la tarjeta, el icono + está a la izquierda del texto. Un click allí
        # suele disparar el evento de la tarjeta completa.
        x = max(box["x"] - 120, 10)
        y = box["y"] + 45
        log(f"Click por coordenadas en tarjeta Agendar cita: x={x:.0f}, y={y:.0f}")
        page.mouse.click(x, y)

    def js_ancestor_click():
        page.evaluate(
            """
            () => {
              const nodes = Array.from(document.querySelectorAll('*'));
              const el = nodes.find(n => (n.textContent || '').trim() === 'Agendar cita');
              if (!el) return false;

              let current = el;
              let clicks = 0;
              while (current && clicks < 8) {
                current.dispatchEvent(new MouseEvent('click', {
                  bubbles: true,
                  cancelable: true,
                  view: window
                }));
                current = current.parentElement;
                clicks++;
              }
              return true;
            }
            """
        )

    attempts = [normal_click, card_mouse_click, js_ancestor_click]
    last_error = None

    for index, attempt in enumerate(attempts, start=1):
        try:
            log(f"Intento {index} para abrir Agendar cita")
            attempt()
            esperar_pantalla_persona_natural(page, timeout=8_000)
            log("Pantalla Persona Natural visible. Click Agendar cita funcionó.")
            return
        except Exception as e:
            last_error = e
            log(f"Intento {index} no cambió de pantalla: {repr(e)}")
            screenshot(page, f"dian_agendar_intento_{index}.png")

    raise DianCheckerError(f"No se pudo pasar de Agendar cita. Último error: {repr(last_error)}")


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

    click_agendar_cita(page)
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
