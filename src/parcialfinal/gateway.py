"""Gateway RF4 (Fog). Arranque: `uv run python -m parcialfinal.gateway [--simular]`.

Un hilo por nodo (si uno cae, los demás siguen) más un hilo de mantenimiento que
publica el estado para el panel. El panel es un proceso aparte que solo lee estado.json.
"""

import argparse
import logging
import threading
import time

from parcialfinal import config as cfgmod
from parcialfinal.nodos.rf1_ble import LectorBle
from parcialfinal.nodos.rf2_http import ClienteCam, LectorCam
from parcialfinal.nodos.rf3_lora import AdaptadorRf3
from parcialfinal.nucleo import Nucleo

log = logging.getLogger("gateway")


def _hilo_resistente(nombre, lector):
    """Reinicia el lector si lanza una excepción inesperada, sin afectar a los demás."""
    def correr():
        while True:
            try:
                lector.ejecutar()
                return
            except Exception:
                log.exception("%s falló; reiniciando en 5 s", nombre)
                time.sleep(5)
    return threading.Thread(target=correr, name=nombre, daemon=True)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="Gateway Fog (RF4)")
    ap.add_argument("--config", default="config.toml")
    ap.add_argument("--simular", action="store_true", help="datos simulados de los tres nodos")
    ap.add_argument("--periodo-rf3", type=float, default=10.0, help="s entre uplinks simulados")
    ap.add_argument("--sin", nargs="*", default=[], choices=["rf1", "rf2", "rf3"], help="no arrancar estos nodos")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

    cfg = cfgmod.cargar(a.config)
    nucleo = Nucleo(cfg)
    rf1 = LectorBle(nucleo, cfg.rf1)
    rf3 = AdaptadorRf3(nucleo, cfg.rf3)
    sim = None
    if a.simular:
        from parcialfinal.simulador import CamFalsa, Simulador
        cam = CamFalsa()
        rf2 = LectorCam(nucleo, cam, cfg.rf2)
        sim = Simulador(rf1, cam, cfg.rf3, a.periodo_rf3)
        lectores = {"RF2": rf2, "RF3": rf3}  # RF1 lo alimenta el simulador (sin Bluetooth)
        log.info("MODO SIMULADO: sin hardware ni Bluetooth")
    else:
        lectores = {"RF1": rf1, "RF2": LectorCam(nucleo, ClienteCam(cfg.rf2), cfg.rf2), "RF3": rf3}
    for n in a.sin:
        lectores.pop(n.upper(), None)

    threading.Thread(target=nucleo.bucle_tick, name="tick", daemon=True).start()
    for nombre, lector in lectores.items():
        _hilo_resistente(nombre, lector).start()
    if sim:
        time.sleep(0.3)  # deja abrir el socket UDP antes de enviar
        sim.iniciar()
    log.info("Gateway en marcha. Estado en %s. Ctrl+C para salir.", nucleo.ruta_estado)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        log.info("Saliendo")


if __name__ == "__main__":
    main()
