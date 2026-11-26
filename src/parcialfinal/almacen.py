"""Almacenamiento CSV (anexar, con cabecera) y carpeta de fotos. Seguro entre hilos."""

import csv
import threading
from datetime import datetime
from pathlib import Path

COLUMNAS = {
    "telemetria.csv": ["nodo", "magnitud", "valor", "t_recepcion", "aceptada"],
    "eventos.csv": ["t_recepcion", "tipo", "fuente", "decision_local_rf2", "ruta_foto", "tam_foto_bytes", "t_proc_ms"],
    # Una fila por evento PIR de RF2: decisión local y tiempos por etapa que informa el nodo.
    "rf2_fotos.csv": [
        "t_recepcion", "events", "confirmed", "reason", "area_pct", "threshold_used",
        "t_ms", "t_capture_us", "t_gray_us", "t_diff_us", "t_morph_us", "t_metrics_us",
        "t_proc_us", "t_jpeg_us", "photo_bytes", "mask_bytes", "ruta_foto", "tam_foto_bytes",
    ],
    # Una fila por uplink: marca del servidor de red (t_ns) y de entrada al gateway (t_gw).
    "rf3_uplinks.csv": [
        "t_ns", "t_gw", "fcnt", "cnt", "rssi", "snr", "temp_c", "hum_pct", "mov", "t_proc_ms",
    ],
}


def iso(t: float) -> str:
    """Epoch -> ISO 8601 local con milisegundos y zona."""
    return datetime.fromtimestamp(t).astimezone().isoformat(timespec="milliseconds")


class Almacen:
    def __init__(self, carpeta: str | Path):
        self.carpeta = Path(carpeta)
        self.fotos = self.carpeta / "fotos"
        self.fotos.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def escribir(self, archivo: str, fila: dict) -> None:
        ruta = self.carpeta / archivo
        with self._lock:
            nuevo = not ruta.exists() or ruta.stat().st_size == 0
            with open(ruta, "a", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=COLUMNAS[archivo])
                if nuevo:
                    w.writeheader()
                w.writerow({c: fila.get(c, "") for c in COLUMNAS[archivo]})

    def guardar_foto(self, jpeg: bytes, t: float) -> str:
        """Guarda la foto con marca de tiempo; devuelve la ruta."""
        nombre = datetime.fromtimestamp(t).strftime("%Y%m%d_%H%M%S_%f")[:-3] + ".jpg"
        ruta = self.fotos / nombre
        ruta.write_bytes(jpeg)
        return str(ruta)
