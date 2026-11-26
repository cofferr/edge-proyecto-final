"""RF2 (ESP32-CAM, HTTP): sondeo de /status cada 1 s y descarga de /photo en cada evento PIR.

Un aumento de "events" en /status es un evento PIR de RF2. En ese momento se descarga
/photo y se guarda con marca de tiempo (aunque el nodo no confirme), junto con la decisión
local del nodo (last.confirmed y last.reason).
"""

import logging
import time

import httpx

from parcialfinal.almacen import iso
from parcialfinal.config import Rf2
from parcialfinal.nucleo import Nucleo

log = logging.getLogger("rf2")


class ClienteCam:
    """Cliente HTTP real. Prueba la URL mDNS y, si falla, la IP de respaldo."""

    def __init__(self, cfg: Rf2):
        self.bases = [cfg.url.rstrip("/")]
        if cfg.ip_respaldo:
            self.bases.append(f"http://{cfg.ip_respaldo}")
        self.http = httpx.Client(timeout=cfg.timeout_http_s)

    def _get(self, ruta: str) -> httpx.Response:
        ultimo = None
        for base in list(self.bases):
            try:
                r = self.http.get(base + ruta)
                r.raise_for_status()
                if base != self.bases[0]:
                    self.bases.remove(base)
                    self.bases.insert(0, base)  # recordar la que funciona
                return r
            except httpx.HTTPError as e:
                ultimo = e
        raise ultimo

    def status(self) -> dict:
        return self._get("/status").json()

    def foto(self) -> bytes:
        return self._get("/photo").content


class LectorCam:
    def __init__(self, nucleo: Nucleo, cliente, cfg: Rf2):
        self.nucleo, self.cliente, self.cfg = nucleo, cliente, cfg
        self.events_prev: int | None = None
        self._parar = False

    def sondear(self) -> None:
        """Un ciclo: lee /status y, si 'events' aumentó, descarga la foto."""
        st = self.cliente.status()
        t = time.time()  # marca de recepción del evento (antes de descargar la foto)
        last = st.get("last") or {}
        self.nucleo.actualizar_nodo(
            "RF2", t, pir=st.get("pir"), warming_up=st.get("warming_up"),
            background_ready=st.get("background_ready"), events=st.get("events"),
            confirmed=st.get("confirmed"), discarded=st.get("discarded"),
            last_confirmed=last.get("confirmed"), last_reason=last.get("reason"),
        )
        events = st.get("events", 0)
        previo, self.events_prev = self.events_prev, events
        if previo is None or events <= previo:  # primer sondeo o reinicio del nodo: sin evento
            return
        self._evento(t, events, last)

    def _evento(self, t: float, events: int, last: dict) -> None:
        ruta, tam = "", ""
        try:
            jpeg = self.cliente.foto()
            ruta, tam = self.nucleo.almacen.guardar_foto(jpeg, t), len(jpeg)
            self.nucleo.actualizar_nodo("RF2", t, ultima_foto=ruta, ultima_foto_t=t, ultima_foto_bytes=tam)
        except Exception as e:  # el evento cuenta aunque la foto falle
            log.warning("no se pudo descargar /photo: %s", e)
        decision = ("confirmada" if last.get("confirmed") else "descartada") + f":{last.get('reason', '')}"
        campos = ["area_pct", "threshold_used", "t_ms", "t_capture_us", "t_gray_us", "t_diff_us",
                  "t_morph_us", "t_metrics_us", "t_proc_us", "t_jpeg_us", "photo_bytes", "mask_bytes"]
        self.nucleo.almacen.escribir(
            "rf2_fotos.csv",
            {"t_recepcion": iso(t), "events": events, "confirmed": last.get("confirmed"),
             "reason": last.get("reason"), "ruta_foto": ruta, "tam_foto_bytes": tam,
             **{c: last.get(c) for c in campos}},
        )
        self.nucleo.evento_pir("RF2", t, decision, ruta, tam)

    def ejecutar(self) -> None:
        while not self._parar:
            inicio = time.time()
            try:
                self.sondear()
            except Exception as e:  # nodo caído: se sigue intentando; los demás nodos no se afectan
                log.warning("RF2 sin respuesta: %s", e)
            time.sleep(max(0.0, self.cfg.periodo_s - (time.time() - inicio)))

    def parar(self) -> None:
        self._parar = True
