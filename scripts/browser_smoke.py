"""Run the production UI against the production HTTP backend."""
from pathlib import Path
import os
import sys
import tempfile
import urllib.parse
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import android_backend as backend


def main():
    with tempfile.TemporaryDirectory(prefix="brisa-ui-") as directory:
        url = backend.start(directory)
        with sync_playwright() as playwright:
            options = {"headless": True}
            if os.environ.get("BRISA_CHROMIUM_SINGLE_PROCESS"):
                options["args"] = ["--single-process", "--no-zygote", "--disable-gpu"]
            browser = playwright.chromium.launch(**options)
            context = browser.new_context(viewport={"width": 390, "height": 844}, reduced_motion="reduce")
            context.add_init_script("""window.Android={ready(){},theme(){},setSharing(){},setReadOnly(){},copyLink(){},shareLink(){},showQr(){},saveFile(){},openPeer(){},closeApp(){}}""")
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(url)
            page.get_by_role("button", name="Añadir mis primeros archivos").wait_for()
            page.locator("#file-input").set_input_files([
                {"name": "Ideas para el viaje.txt", "mimeType": "text/plain", "buffer": b"Una brisa"},
                {"name": "Recuerdos.jpg", "mimeType": "image/jpeg", "buffer": b"test-image"},
                {"name": '<img onerror="window.injection=true">.txt', "mimeType": "text/plain", "buffer": b"safe"},
            ])
            page.wait_for_function("() => document.querySelectorAll('.file-row').length===3")
            assert page.evaluate("window.injection===undefined")
            page.get_by_label("Buscar archivos").fill("viaje")
            assert page.locator(".file-row").count() == 1
            page.get_by_label("Buscar archivos").fill("")
            page.get_by_role("button", name="Actividad", exact=True).click()
            assert page.locator(".transfer").count() == 3
            assert "Completado" in page.locator("#activity-list").inner_text()
            page.get_by_role("button", name="Inicio", exact=True).click()
            page.get_by_label("Crear carpeta", exact=True).click()
            page.get_by_label("Nombre de la carpeta").fill("Fotos")
            page.get_by_role("dialog").get_by_role("button", name="Crear carpeta", exact=True).click()
            page.wait_for_function("() => document.querySelectorAll('.file-row').length===4")
            page.get_by_role("button", name="Fotos Carpeta · Abrir carpeta").click()
            page.wait_for_function("() => currentPath==='Fotos'")
            page.get_by_role("button", name="Mis archivos", exact=True).click()
            page.wait_for_function("() => currentPath===''")
            page.get_by_role("button", name="Ajustes", exact=True).click()
            page.get_by_role("button", name="Claro", exact=True).click()
            assert page.locator("html").get_attribute("data-theme") == "light"
            page.reload()
            page.get_by_role("button", name="Ajustes", exact=True).click()
            assert page.get_by_role("button", name="Claro", exact=True).get_attribute("aria-pressed") == "true"
            page.get_by_role("button", name="Inicio", exact=True).click()
            for width in [320, 390, 768, 1200]:
                page.set_viewport_size({"width": width, "height": 844})
                assert page.evaluate("document.documentElement.scrollWidth<=innerWidth"), f"overflow at {width}"
            page.set_viewport_size({"width": 390, "height": 844})
            backend.delete_path('<img onerror="window.injection=true">.txt')
            page.evaluate("loadFiles()")
            page.wait_for_function("() => document.querySelectorAll('.file-row').length===3")
            page.evaluate("document.querySelector('#toast').hidden=true")
            (ROOT / "docs").mkdir(exist_ok=True)
            page.screenshot(path=str(ROOT / "docs/brisa-claro.png"), full_page=True)
            page.get_by_label("Cambiar a modo oscuro").click()
            page.screenshot(path=str(ROOT / "docs/brisa-oscuro.png"), full_page=True)
            page.get_by_role("button", name="Conectar", exact=True).last.click()
            page.get_by_label("Enlace del otro dispositivo").fill("http://192.168.1.1:8000/?token=prueba")
            page.get_by_role("button", name="Abrir en el navegador").click()
            assert not errors, errors

            # A guest uses the same real files, with no Android bridge.
            backend.set_sharing(True)
            guest_token = backend._server.token
            guest = browser.new_page(viewport={"width": 390, "height": 844})
            guest.goto(url.split("?")[0] + "?token=" + guest_token)
            guest.get_by_role("heading", name="Ya estás al otro lado.").wait_for()
            guest.get_by_label("Buscar archivos").fill("viaje")
            with guest.expect_download() as download:
                guest.get_by_label("Guardar Ideas para el viaje.txt", exact=True).click()
            assert Path(download.value.path()).read_bytes() == b"Una brisa"
            guest.locator("#file-input").set_input_files({"name": "desde-pc.txt", "mimeType": "text/plain", "buffer": b"enviado"})
            guest.wait_for_function("() => transfers.length===1&&transfers[0].done")
            assert (Path(directory) / "desde-pc.txt").read_bytes() == b"enviado"
            backend.set_read_only(True)
            guest.reload()
            assert guest.locator("#add-files").is_disabled()
            browser.close()
        backend.stop()
    print("UI verificada: subida, descarga, carpetas, búsqueda, temas, invitados y cuatro tamaños.")


if __name__ == "__main__":
    main()
