"""Lanzamiento y parada de los procesos que usan las pruebas: gateway y servidor de red LoRaWAN."""

import glob
import signal
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]


def buscar_puerto_receptor() -> str | None:
    """Primer puerto serie USB del receptor (usbserial / usbmodem)."""
    p = sorted(glob.glob("/dev/cu.usbserial*") + glob.glob("/dev/cu.usbmodem*") + glob.glob("/dev/cu.SLAB*"))
    return p[0] if p else None


def ns_en_marcha() -> bool:
    return subprocess.run(["pgrep", "-f", "lorawan_ns.py"], capture_output=True).returncode == 0


def lanzar_gateway(log: Path, config: str, extra: list[str]) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-m", "parcialfinal.gateway", "--config", config, *extra],
        cwd=RAIZ, stdout=open(log, "w"), stderr=subprocess.STDOUT)


def lanzar_ns(log: Path, puerto: str) -> subprocess.Popen:
    """Servidor de red real (hay que ejecutarlo desde la raíz: guarda ns_state.json y el JSONL ahí)."""
    return subprocess.Popen([sys.executable, "lorawan_ns.py", "--port", puerto],
                            cwd=RAIZ, stdout=open(log, "w"), stderr=subprocess.STDOUT)


def detener(p: subprocess.Popen | None) -> None:
    """SIGINT (Ctrl+C) → SIGTERM → kill. Escalar es necesario: lanzado desde un proceso en segundo
    plano el hijo hereda SIGINT ignorado y no se detendría con Ctrl+C."""
    if p is None:
        return
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGKILL):
        if p.poll() is not None:
            return
        p.send_signal(sig)
        try:
            p.wait(4)
            return
        except subprocess.TimeoutExpired:
            continue


def espera_hasta(t: float, parar=lambda: False) -> None:
    """Duerme hasta el instante `t` (epoch) en rebanadas cortas, para atender Ctrl+C."""
    while time.time() < t and not parar():
        time.sleep(min(0.5, max(0.0, t - time.time())))


class Sesion:
    """Gateway (solo RF3) + servidor de red LoRaWAN, o gateway simulado. Úsese con `with`.

    Real: usa `data/` y la salida va a ~/Edge/InformeFinal/datos. Simulado: todo va a `data_sim/`
    para no mezclar datos simulados con los reales.
    """

    def __init__(self, simular: bool, periodo_s: float, puerto: str | None = None):
        self.simular, self.periodo_s, self.puerto = simular, periodo_s, puerto
        self.gateway = self.ns = None
        if simular:
            self.carpeta = RAIZ / "data_sim" / "pruebas_rf3"
            self.salida = RAIZ / "data_sim" / "informe"
        else:
            self.carpeta = RAIZ / "data"
            self.salida = Path.home() / "Edge" / "InformeFinal" / "datos"
        self.config = "config.toml"

    def __enter__(self):
        self.carpeta.mkdir(parents=True, exist_ok=True)
        if self.simular:
            texto = (RAIZ / "config.toml").read_text().replace('carpeta = "data"', f'carpeta = "{self.carpeta}"')
            ruta = self.carpeta / "config.sim.toml"
            ruta.write_text(texto)
            self.config = str(ruta)
            extra = ["--simular", "--periodo-rf3", str(self.periodo_s), "--sin", "rf2"]
        else:
            extra = ["--sin", "rf1", "rf2"]
            if not ns_en_marcha():
                puerto = self.puerto or buscar_puerto_receptor()
                if not puerto:
                    raise SystemExit("ERROR: no encuentro el receptor LoRa por USB (/dev/cu.usbserial*); "
                                     "conéctalo o pasa --puerto")
                self.ns = lanzar_ns(self.carpeta / "lorawan_ns.log", puerto)
                time.sleep(2)
        self.gateway = lanzar_gateway(self.carpeta / "gateway_rf3.log", self.config, extra)
        time.sleep(4)  # el gateway abre el socket UDP y arranca los hilos
        return self

    def __exit__(self, *exc):
        detener(self.gateway)
        detener(self.ns)
        return False
