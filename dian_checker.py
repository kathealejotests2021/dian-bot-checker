import os
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


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise DianCheckerError(f"El secret/variable {name} está vacío o no existe en GitHub Actions")
    return value


def enviar_email(status: str):
    email_from = required_env("EMAIL_FROM")
    email_password = required_env("EMAIL_PASSWORD")
    email_to = required_env("EMAIL_TO")

    checked_at = now_colombia()

    if status == "sin_citas":
        subject = "DIAN: No hay citas disponibles 😢"
        body = (
            "No hay citas disponibles 😢\n\n"
            "El bot revisó el agendamiento de citas de la DIAN y todavía aparece "
            "el mensaje de no disponibilidad.\n\n"
            "No tienes que hacer nada por ahora.\n\n"
            f"Hora de revisión: {checked_at}\n"
            "URL: https://agendamiento.dian.gov.co/"
        )
    elif status == "posible_disponibilidad":
        subject = "DIAN: ¡Posible cita disponible! 🚨"
        body = (
            "Sí hay citas disponibles o ya no apareció el mensaje de no disponibilidad. 🚨\n\n"
            "Entra rápido a revisar y agendar manualmente:\n"
            "https://agendamiento.dian.gov.co/\n\n"
            f"Hora de detección: {checked_at}"
        )
    else:
        subject = "DIAN: Estado desconocido del bot ⚠️"
        body = (
            f"El bot terminó con un estado no esperado: {status} ⚠️\n\n"
            f"Hora: {checked_at}\n"
            "URL: https://agendamiento.dian.gov.co/"
        )

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = email_from
    msg["To"] = email_to

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=25) as server:
        server.login(email_from, email_password)
        server.send_message(msg)

    log(f"Email enviado con subject: {subject}")


def _find_text_info(page, fragment: str):
    return page.evaluate(
        r"""
        ({fragment}) => {
          const wanted = (fragment || '').replace(/[.]/g, '').replace(/\s+/g, ' ').trim().toLowerCase();
          const normalize = (s) => (s || '').replace(/[.]/g, '').replace(/\s+/g, ' ').trim().toLowerCase();
          const isVisible = (el) => {
            const r = el.getBoundingClientRect();
            const style = window.getComputedStyle(el);
            return r.width > 0 && r.height > 0 &&
                   style.display !== 'none' &&
                   style.visibility !== 'hidden' &&
                   style.opacity !== '0';
          };

          const nodes = Array.from(document.querySelectorAll('body *'));
          const matches = [];

          for (const el of nodes) {
            if (!isVisible(el)) continue;
            const t = normalize(el.innerText || el.textContent || '');
            if (!t || !t.includes(wanted)) continue;
            const r = el.getBoundingClientRect();
            const area = r.width * r.height;
            // Ignorar contenedores gigantes como body/app-root, pero dejar tarjetas.
            if (area > 500000) continue;
            matches.push({
              tag: el.tagName,
              text: t.slice(0, 120),
              x: Math.round(r.left + r.width / 2),
              y: Math.round(r.top + r.height / 2),
              width: Math.round(r.width),
              height: Math.round(r.height),
              area: Math.round(area),
              className: (el.className || '').toString().slice(0, 120)
            });
          }

          matches.sort((a, b) => a.area - b.area);
          return {wanted, count: matches.length, first: matches.slice(0, 12)};
        }
        """,
        {"fragment": fragment},
    )


def wait_text_fragment(page, fragment: str, timeout: int = 60_000):
    deadline = time.monotonic() + timeout / 1000
    last = None
    while time.monotonic() < deadline:
        last = _find_text_info(page, fragment)
        if last and last.get("count", 0) > 0:
            return last
        time.sleep(0.5)
    raise PlaywrightTimeoutError(f"No apareció texto visible que contenga: {fragment}. Último resultado: {last}")


def click_by_fragment(page, fragment: str, *, timeout: int = 30_000, prefer_card: bool = True):
    """
    Click robusto por fragmento visible.

    La UI de la DIAN tiene varios textos duplicados/ocultos, por eso NO usamos
    get_by_text(...).first. Buscamos elementos visibles cuyo texto contenga el
    fragmento y clickeamos el contenedor visible adecuado.
    """
    log(f"Click robusto por fragmento: {fragment}")
    wait_text_fragment(page, fragment, timeout=timeout)

    result = page.evaluate(
        r"""
        ({fragment, preferCard}) => {
          const wanted = (fragment || '').replace(/[.]/g, '').replace(/\s+/g, ' ').trim().toLowerCase();
          const normalize = (s) => (s || '').replace(/[.]/g, '').replace(/\s+/g, ' ').trim().toLowerCase();

          const isVisible = (el) => {
            const r = el.getBoundingClientRect();
            const style = window.getComputedStyle(el);
            return r.width > 0 && r.height > 0 &&
                   style.display !== 'none' &&
                   style.visibility !== 'hidden' &&
                   style.opacity !== '0';
          };

          const areaOf = (el) => {
            const r = el.getBoundingClientRect();
            return r.width * r.height;
          };

          const visibleTextNodes = Array.from(document.querySelectorAll('body *'))
            .filter(el => {
              if (!isVisible(el)) return false;
              const t = normalize(el.innerText || el.textContent || '');
              if (!t.includes(wanted)) return false;
              const area = areaOf(el);
              return area > 0 && area < 500000;
            })
            .sort((a, b) => areaOf(a) - areaOf(b));

          if (!visibleTextNodes.length) {
            return {ok: false, reason: 'visible fragment not found', wanted};
          }

          let base = visibleTextNodes[0];
          let target = base;

          if (preferCard) {
            // Subir desde el texto hasta una tarjeta/botón visible razonable.
            let current = base;
            for (let i = 0; current && i < 12; i++) {
              const r = current.getBoundingClientRect();
              const area = r.width * r.height;
              const tag = current.tagName;
              const role = current.getAttribute('role') || '';
              const className = (current.className || '').toString().toLowerCase();

              const looksClickable =
                tag === 'BUTTON' || tag === 'A' || role === 'button' ||
                className.includes('card') || className.includes('button') ||
                className.includes('option') || className.includes('item') ||
                className.includes('select');

              const looksLikeCard = r.width >= 120 && r.height >= 70 && area < 250000;

              if (isVisible(current) && (looksClickable || looksLikeCard)) {
                target = current;
                break;
              }
              current = current.parentElement;
            }
          }

          const r = target.getBoundingClientRect();
          const x = r.left + r.width / 2;
          const y = r.top + r.height / 2;

          target.scrollIntoView({block: 'center', inline: 'center'});

          const events = ['pointerover', 'mouseover', 'pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click'];
          for (const type of events) {
            target.dispatchEvent(new MouseEvent(type, {
              bubbles: true,
              cancelable: true,
              view: window,
              clientX: x,
              clientY: y
            }));
          }

          if (typeof target.click === 'function') target.click();

          return {
            ok: true,
            wanted,
            clickedTag: target.tagName,
            clickedText: normalize(target.innerText || target.textContent || '').slice(0, 150),
            x: Math.round(x),
            y: Math.round(y),
            width: Math.round(r.width),
            height: Math.round(r.height),
            className: (target.className || '').toString().slice(0, 120)
          };
        }
        """,
        {"fragment": fragment, "preferCard": prefer_card},
    )

    log(f"Resultado click fragmento {fragment}: {result}")
    if not result or not result.get("ok"):
        raise DianCheckerError(f"No se pudo clickear fragmento {fragment}: {result}")

    page.wait_for_timeout(900)
    return result


def click_siguiente(page, timeout: int = 30_000):
    """Click robusto en Siguiente, esperando que esté habilitado."""
    log("Click robusto en botón: Siguiente")
    deadline = time.monotonic() + timeout / 1000
    last = None

    while time.monotonic() < deadline:
        result = page.evaluate(
            r"""
            () => {
              const normalize = (s) => (s || '').replace(/\s+/g, ' ').trim().toLowerCase();
              const isVisible = (el) => {
                const r = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                return r.width > 0 && r.height > 0 &&
                       style.display !== 'none' &&
                       style.visibility !== 'hidden' &&
                       style.opacity !== '0';
              };
              const isDisabled = (el) => {
                const cls = (el.className || '').toString().toLowerCase();
                return el.disabled === true ||
                       el.getAttribute('disabled') !== null ||
                       el.getAttribute('aria-disabled') === 'true' ||
                       cls.includes('disabled') || cls.includes('disable');
              };

              const nodes = Array.from(document.querySelectorAll('button, a, [role="button"], div, span'));
              const matches = nodes.filter(el => isVisible(el) && normalize(el.innerText || el.textContent || '') === 'siguiente');
              if (!matches.length) return {ok: false, reason: 'not_found'};

              let target = matches[0];
              let current = target;
              for (let i = 0; current && i < 8; i++) {
                if ((current.tagName === 'BUTTON' || current.tagName === 'A' || current.getAttribute('role') === 'button') && isVisible(current)) {
                  target = current;
                  break;
                }
                current = current.parentElement;
              }

              if (isDisabled(target)) {
                return {ok: false, reason: 'disabled', tag: target.tagName, className: target.className || ''};
              }

              const r = target.getBoundingClientRect();
              const x = r.left + r.width / 2;
              const y = r.top + r.height / 2;
              target.scrollIntoView({block: 'center', inline: 'center'});
              const events = ['pointerover', 'mouseover', 'pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click'];
              for (const type of events) {
                target.dispatchEvent(new MouseEvent(type, {bubbles: true, cancelable: true, view: window, clientX: x, clientY: y}));
              }
              if (typeof target.click === 'function') target.click();
              return {ok: true, tag: target.tagName, x: Math.round(x), y: Math.round(y), className: target.className || ''};
            }
            """
        )
        last = result
        if result and result.get("ok"):
            log(f"Resultado Siguiente: {result}")
            page.wait_for_timeout(1200)
            return
        time.sleep(0.5)

    raise DianCheckerError(f"No se pudo clickear Siguiente. Último resultado: {last}")


def click_siguiente_if_available(page, timeout: int = 5_000):
    try:
        click_siguiente(page, timeout=timeout)
        return True
    except Exception as e:
        log(f"Siguiente opcional no disponible o no requerido: {repr(e)}")
        return False


def wait_any_fragment(page, fragments, timeout: int = 40_000):
    deadline = time.monotonic() + timeout / 1000
    last = None
    while time.monotonic() < deadline:
        for fragment in fragments:
            info = _find_text_info(page, fragment)
            last = info
            if info and info.get("count", 0) > 0:
                log(f"Pantalla detectada por texto: {fragment}")
                return fragment
        time.sleep(0.5)
    raise PlaywrightTimeoutError(f"No apareció ninguno de estos textos: {fragments}. Último resultado: {last}")


def dump_visible_matches(page, label: str, fragments):
    """Diagnóstico liviano para ver qué textos detecta Playwright/JS."""
    log(f"Dump visible matches: {label}")
    for fragment in fragments:
        try:
            info = _find_text_info(page, fragment)
            log(f"Fragmento '{fragment}': {info}")
        except Exception as e:
            log(f"No se pudo inspeccionar fragmento {fragment}: {repr(e)}")


def aplicar_filtros(page):
    # La página es SPA: domcontentloaded ocurre antes de que cargue la UI real.
    # Por eso primero esperamos la pantalla inicial y solo después tomamos screenshot/click.
    wait_any_fragment(page, ["Agendar cita", "Gestionar cita"], timeout=90_000)
    screenshot(page, "dian_01_inicio_cargado.png")
    dump_visible_matches(page, "inicio", ["Agendar cita", "Programe cita", "Gestionar cita"])

    click_by_fragment(page, "Agendar cita", timeout=30_000, prefer_card=True)
    wait_any_fragment(page, ["Persona Natural", "Persona Jurídica", "Seleccione el tipo de persona"], timeout=60_000)
    screenshot(page, "dian_02_paso_persona.png")

    click_by_fragment(page, "Persona Natural", timeout=30_000, prefer_card=True)
    screenshot(page, "dian_03_persona_natural_click.png")
    click_siguiente(page)

    wait_any_fragment(page, ["Videoatención", "Presencial", "Cómo prefiere", "¿Cómo prefiere la cita?"], timeout=60_000)
    screenshot(page, "dian_04_paso_tipo_cita.png")

    click_by_fragment(page, "Videoatención", timeout=30_000, prefer_card=True)
    screenshot(page, "dian_05_videoatencion_click.png")
    click_siguiente(page)

    wait_any_fragment(page, ["Devoluciones", "RUT y orientación", "Seleccione el tipo de servicio"], timeout=60_000)
    screenshot(page, "dian_06_paso_servicio.png")

    click_by_fragment(page, "Devoluciones", timeout=30_000, prefer_card=True)
    screenshot(page, "dian_07_devoluciones_click.png")
    click_siguiente_if_available(page, timeout=8_000)
    screenshot(page, "dian_08_despues_devoluciones.png")


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
                page.get_by_text(NO_DISPONIBLE_TEXT).wait_for(state="visible", timeout=30_000)
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

    # Enviar correo en ambos casos:
    # - sin_citas: confirmación de que todavía no hay disponibilidad
    # - posible_disponibilidad: alerta para entrar rápido
    enviar_email(status)


if __name__ == "__main__":
    main()
