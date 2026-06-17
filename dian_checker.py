import os
import re
import time
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
    """
    Busca un texto visible, evitando el problema de la DIAN donde existen
    muchos nodos duplicados ocultos con el mismo texto.

    page.get_by_text(...).first puede apuntar a un <span> oculto. Por eso
    iteramos los matches hasta encontrar uno realmente visible.
    """
    deadline = time.monotonic() + (timeout / 1000)
    last_count = 0

    while time.monotonic() < deadline:
        locator = page.get_by_text(text, exact=exact)

        try:
            last_count = locator.count()
        except Exception:
            last_count = 0

        for index in range(min(last_count, 120)):
            item = locator.nth(index)
            try:
                if item.is_visible(timeout=250):
                    return item
            except Exception:
                pass

        time.sleep(0.25)

    raise PlaywrightTimeoutError(
        f'No se encontró texto visible: {text}. Matches encontrados: {last_count}'
    )


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
    En la primera pantalla, el listener de Angular parece estar en la tarjeta
    completa y además hay varios <span> ocultos con el texto "Agendar cita".

    Por eso NO hacemos wait sobre get_by_text("Agendar cita").first, porque
    puede tomar un span oculto. Probamos primero coordenadas fijas sobre la
    tarjeta, usando viewport 1366x900, y luego intentos por DOM/JS.
    """
    log("Click robusto en tarjeta: Agendar cita")

    def wait_persona_natural_after_click():
        esperar_pantalla_persona_natural(page, timeout=10_000)
        log("Pantalla Persona Natural visible. Click Agendar cita funcionó.")

    def click_card_center():
        # Coordenadas para viewport 1366x900. La tarjeta izquierda está aprox.
        # entre x=341..716 y y=280..455. El centro cae en x=530, y=370.
        log("Intentando click por coordenadas en el centro de la tarjeta")
        page.mouse.click(530, 370)

    def click_plus_icon():
        # Click sobre el ícono + de la tarjeta.
        log("Intentando click por coordenadas sobre el ícono +")
        page.mouse.click(420, 365)

    def click_visible_text_parent_by_js():
        log("Intentando click por JavaScript sobre ancestro visible")
        result = page.evaluate(
            """
            () => {
              const normalize = (s) => (s || '').replace(/\s+/g, ' ').trim();
              const nodes = Array.from(document.querySelectorAll('span, div, p, h1, h2, h3, h4, b, strong'));

              const isVisible = (el) => {
                const r = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                return r.width > 0 && r.height > 0 &&
                       style.display !== 'none' &&
                       style.visibility !== 'hidden' &&
                       style.opacity !== '0';
              };

              const el = nodes.find(n => normalize(n.innerText || n.textContent) === 'Agendar cita' && isVisible(n));
              if (!el) {
                return {ok: false, reason: 'visible text node not found'};
              }

              let current = el;
              for (let i = 0; current && i < 10; i++) {
                const r = current.getBoundingClientRect();
                // Buscar una tarjeta grande clickeable.
                if (r.width >= 250 && r.height >= 120) {
                  current.dispatchEvent(new MouseEvent('click', {
                    bubbles: true,
                    cancelable: true,
                    view: window,
                    clientX: r.left + r.width / 2,
                    clientY: r.top + r.height / 2
                  }));
                  current.click();
                  return {ok: true, clicked: current.tagName, className: current.className || ''};
                }
                current = current.parentElement;
              }

              el.click();
              return {ok: true, clicked: el.tagName, className: el.className || ''};
            }
            """
        )
        log(f"Resultado JS Agendar cita: {result}")
        if not result or not result.get("ok"):
            raise DianCheckerError(f"JS no encontró tarjeta visible: {result}")

    def click_visible_text_locator():
        log("Intentando click sobre texto visible Agendar cita")
        locator = wait_visible_text(page, "Agendar cita", timeout=8_000)
        locator.scroll_into_view_if_needed(timeout=5_000)
        locator.click(force=True, timeout=5_000)

    attempts = [
        click_card_center,
        click_plus_icon,
        click_visible_text_parent_by_js,
        click_visible_text_locator,
    ]

    last_error = None
    for index, attempt in enumerate(attempts, start=1):
        try:
            log(f"Intento {index} para abrir Agendar cita")
            attempt()
            wait_persona_natural_after_click()
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
