"""Capturas automáticas del panel Gradio con Playwright (usa el Chrome instalado; no descarga navegadores).

Mantiene una página abierta durante toda la prueba para poder capturar en el instante del estado.
Si algo falla, `ok` queda en False y la prueba sigue (las capturas se toman a mano).
"""

import shutil
import time
from pathlib import Path


class Capturador:
    def __init__(self, url: str, carpetas: list[Path]):
        self.url, self.carpetas = url, carpetas
        self.ok, self.error, self._pw, self._nav, self._pag = False, "", None, None, None
        self.guardadas: list[str] = []

    def abrir(self, espera_s: float = 40.0) -> None:
        try:
            from playwright.sync_api import sync_playwright
            self._pw = sync_playwright().start()
            self._nav = self._pw.chromium.launch(channel="chrome", headless=True)
            self._pag = self._nav.new_page(viewport={"width": 1280, "height": 1000})
            fin = time.time() + espera_s
            while True:  # el panel tarda unos segundos en abrir el puerto
                try:
                    self._pag.goto(self.url, timeout=5000)
                    break
                except Exception:
                    if time.time() > fin:
                        raise
                    time.sleep(1)
            self._pag.wait_for_selector("text=Panel RF5", timeout=15000)
            self.ok = True
        except Exception as e:
            self.error = f"{type(e).__name__}: {e}"
            self.cerrar()

    def capturar(self, nombre: str, espera_s: float = 2.0) -> bool:
        """Espera al siguiente refresco del panel (gr.Timer) y guarda <nombre>.png en cada carpeta."""
        if not self.ok:
            return False
        try:
            self._pag.wait_for_timeout(int(espera_s * 1000))
            primera = self.carpetas[0] / f"{nombre}.png"
            primera.parent.mkdir(parents=True, exist_ok=True)
            self._pag.screenshot(path=str(primera), full_page=True)
            for c in self.carpetas[1:]:
                c.mkdir(parents=True, exist_ok=True)
                shutil.copy(primera, c / primera.name)
            self.guardadas.append(f"{nombre}.png")
            return True
        except Exception as e:
            self.error = f"{type(e).__name__}: {e}"
            return False

    def cerrar(self) -> None:
        for obj, m in ((self._nav, "close"), (self._pw, "stop")):
            try:
                if obj:
                    getattr(obj, m)()
            except Exception:
                pass
        self._nav = self._pw = self._pag = None
        self.ok = False
