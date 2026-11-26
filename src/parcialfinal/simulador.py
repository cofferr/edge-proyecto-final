"""Modo --simular: genera datos de los tres nodos sin hardware ni Bluetooth.

Alimenta los MISMOS adaptadores que el modo real:
  RF1: tramas de 7 bytes -> LectorBle.al_recibir (prueba el decodificador).
  RF2: cliente HTTP falso -> LectorCam (prueba la detección de 'events' y la descarga de foto).
  RF3: datagramas UDP con el esquema de lorawan_ns.py -> AdaptadorRf3 (prueba el socket real).
Un escenario cíclico dispara un PIR aislado (sospecha) y luego dos PIR cercanos (alerta).
"""

import io
import json
import random
import socket
import struct
import threading
import time

from PIL import Image, ImageDraw


class CamFalsa:
    """Imita /status y /photo del ESP32-CAM."""

    def __init__(self):
        self.events = 0
        self.confirmed = 0
        self.discarded = 0
        self.last = {}

    def disparar(self, confirmada: bool) -> None:
        self.events += 1
        if confirmada:
            self.confirmed += 1
        else:
            self.discarded += 1
        self.last = {
            "confirmed": confirmada, "reason": "area_ok" if confirmada else "area_pequena",
            "area_pct": round(random.uniform(4, 9) if confirmada else random.uniform(0.1, 0.8), 2),
            "bbox": [100, 80, 60, 90], "centroid": [130, 125], "threshold_used": 25, "t_ms": int(time.time() * 1000) % 10**7,
            "t_capture_us": random.randint(30000, 40000), "t_gray_us": random.randint(800, 1200),
            "t_diff_us": random.randint(900, 1300), "t_morph_us": random.randint(3000, 4000),
            "t_metrics_us": random.randint(500, 900), "t_proc_us": random.randint(6000, 8000),
            "t_jpeg_us": random.randint(9000, 12000), "photo_bytes": 0, "mask_bytes": 0,
        }

    def status(self) -> dict:
        return {"pir": 0, "warming_up": False, "background_ready": True, "events": self.events,
                "confirmed": self.confirmed, "discarded": self.discarded, "last": self.last}

    def foto(self) -> bytes:
        img = Image.effect_noise((320, 240), 40).convert("L")
        d = ImageDraw.Draw(img)
        d.rectangle([100, 70, 170, 190], outline=255, width=3)
        d.text((8, 8), time.strftime("SIM %H:%M:%S"), fill=255)
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=70)
        return buf.getvalue()


class Simulador:
    def __init__(self, rf1, cam: CamFalsa, rf3_cfg, periodo_rf3_s: float = 10.0):
        self.rf1, self.cam, self.cfg3 = rf1, cam, rf3_cfg
        self.periodo_rf3_s = periodo_rf3_s
        self._parar = threading.Event()
        self.cnt = 0
        self.temp3, self.hum3 = 23.0, 60.0
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def _uplink(self, mov: int) -> None:
        """Envía un uplink con el esquema que publica lorawan_ns.py."""
        self.temp3 += random.uniform(-0.2, 0.3)
        self.hum3 += random.uniform(-0.8, 0.8)
        rec = {"ts": time.time(), "node": "rf3-lora", "devaddr": "01000001", "fcnt": self.cnt,
               "rssi": random.randint(-70, -45), "snr": round(random.uniform(8, 11), 1),
               "confirmed": False, "fport": 1, "payload_hex": "",
               "temp_c": round(self.temp3, 2), "hum_pct": round(self.hum3, 2), "mov": mov, "cnt": self.cnt}
        self.cnt += 1
        self.sock.sendto(json.dumps(rec).encode(), (self.cfg3.udp_host, self.cfg3.udp_puerto))

    def _hilo_rf1(self) -> None:
        t, h, s = 24.0, 55.0, 1400.0
        while not self._parar.wait(2.0):
            t += random.uniform(-0.25, 0.3)
            h += random.uniform(-1.0, 1.0)
            s += random.uniform(-40, 30)
            self.rf1.al_recibir(struct.pack("<hHHB", round(t * 100), round(h * 100), round(s), 0))

    def _hilo_rf3(self) -> None:
        while not self._parar.is_set():
            self._uplink(0)
            self._parar.wait(self.periodo_rf3_s)

    def _hilo_escenario(self) -> None:
        """Ciclo de 90 s: t=15 PIR solo de RF2 (sospecha); t=50 RF2 y t=56 RF3 (alerta)."""
        guion = [(15, "rf2", False), (50, "rf2", True), (56, "rf3", None)]
        while not self._parar.is_set():
            t0 = time.time()
            for t, quien, confirmada in guion:
                if self._parar.wait(max(0.0, t0 + t - time.time())):
                    return
                if quien == "rf2":
                    self.cam.disparar(confirmada)
                else:
                    self._uplink(1)
            self._parar.wait(max(0.0, t0 + 90 - time.time()))

    def iniciar(self) -> None:
        for f in (self._hilo_rf1, self._hilo_rf3, self._hilo_escenario):
            threading.Thread(target=f, daemon=True).start()

    def parar(self) -> None:
        self._parar.set()
