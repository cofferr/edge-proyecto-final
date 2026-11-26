"""RF3 (LoRaWAN): adaptador del servidor de red lorawan_ns.py.

No se habla con el nodo: lorawan_ns.py ya validó MIC, descifró y decodificó el payload y
publica cada uplink como una línea JSON (UDP 127.0.0.1:9001 y lorawan_uplinks.jsonl) con:
  ts (epoch en el servidor de red), node, devaddr, fcnt, rssi, snr, confirmed, fport,
  payload_hex, temp_c (None = sin dato), hum_pct (None = sin dato), mov (1 = PIR), cnt.
Este módulo solo traduce ese esquema a llamadas al núcleo.
"""

import json
import logging
import socket
import time
from pathlib import Path

from parcialfinal.almacen import iso
from parcialfinal.config import Rf3
from parcialfinal.nucleo import Nucleo

log = logging.getLogger("rf3")

# campo del JSON del servidor de red -> magnitud del gateway
CAMPOS = {"temp_c": "temperatura", "hum_pct": "humedad_aire"}


class AdaptadorRf3:
    def __init__(self, nucleo: Nucleo, cfg: Rf3):
        self.nucleo, self.cfg = nucleo, cfg
        self._parar = False

    def procesar(self, rec: dict, t_gw: float | None = None) -> None:
        """Procesa un uplink. `t_gw` es la marca de entrada al gateway (por defecto, ahora)."""
        t_gw = time.time() if t_gw is None else t_gw
        if "cnt" not in rec:  # el servidor de red no pudo decodificar el payload
            log.warning("uplink sin payload decodificado: %s", rec)
            return
        for campo, magnitud in CAMPOS.items():
            if rec.get(campo) is not None:  # None = "sin dato": no es una lectura
                self.nucleo.lectura("RF3", magnitud, rec[campo], t_gw)
        self.nucleo.actualizar_nodo(
            "RF3", t_gw, rssi=rec.get("rssi"), snr=rec.get("snr"),
            cnt=rec["cnt"], fcnt=rec.get("fcnt"), mov=rec.get("mov"),
        )
        if rec.get("mov") == 1:
            self.nucleo.evento_pir("RF3", t_gw)
        self.nucleo.almacen.escribir(
            "rf3_uplinks.csv",
            {"t_ns": iso(rec["ts"]) if rec.get("ts") else "", "t_gw": iso(t_gw),
             "fcnt": rec.get("fcnt"), "cnt": rec["cnt"], "rssi": rec.get("rssi"), "snr": rec.get("snr"),
             "temp_c": rec.get("temp_c"), "hum_pct": rec.get("hum_pct"), "mov": rec.get("mov"),
             "t_proc_ms": round((time.time() - t_gw) * 1000, 3)},
        )

    def _procesar_linea(self, datos: bytes | str) -> None:
        try:
            self.procesar(json.loads(datos))
        except Exception:  # un datagrama raro no debe tumbar el lector
            log.exception("uplink inválido: %r", datos)

    def ejecutar(self) -> None:
        if self.cfg.modo == "archivo":
            self._seguir_archivo()
        else:
            self._escuchar_udp()

    def _escuchar_udp(self) -> None:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((self.cfg.udp_host, self.cfg.udp_puerto))
        s.settimeout(0.5)
        log.info("RF3 escuchando UDP %s:%d", self.cfg.udp_host, self.cfg.udp_puerto)
        while not self._parar:
            try:
                datos, _ = s.recvfrom(65535)
            except TimeoutError:
                continue
            self._procesar_linea(datos)

    def _seguir_archivo(self) -> None:
        """Alternativa a UDP: sigue el JSONL desde el final (solo uplinks nuevos)."""
        ruta = Path(self.cfg.archivo)
        pos = ruta.stat().st_size if ruta.exists() else 0
        while not self._parar:
            if ruta.exists() and ruta.stat().st_size > pos:
                with open(ruta, "rb") as f:
                    f.seek(pos)
                    for linea in f.read().splitlines():
                        if linea.strip():
                            self._procesar_linea(linea)
                    pos = f.tell()
            time.sleep(0.5)

    def parar(self) -> None:
        self._parar = True
