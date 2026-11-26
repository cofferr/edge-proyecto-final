#!/usr/bin/env python3
"""Prueba de enlace de RF3 (LoRaWAN) y prueba PIR de RF3.

  uv run python scripts/prueba_rf3.py [--duracion 300] [--periodo 60]   # enlace, filtro, ancho de banda
  uv run python scripts/prueba_rf3.py --pir                              # 60 s: lista los eventos PIR de RF3
  uv run python scripts/prueba_rf3.py --simular --duracion 20 --periodo 2   # sin hardware (datos en data_sim/)

Necesita RF3 y el receptor conectados (si lorawan_ns.py no está ya en marcha, lo lanza este script).
Salida: <datos>/rf3_resultados.json y .md (secciones rf3_enlace y rf3_pir; cada ejecución reemplaza la suya).
"""

import argparse
import importlib.util
import statistics as st
import signal
import sys
import tempfile
import time
from pathlib import Path

from parcialfinal import informe
from parcialfinal.procesos import RAIZ, Sesion


def bench_servidor_red(n: int = 200) -> dict:
    """Tiempo de validar + descifrar + guardar un uplink en lorawan_ns.py con tramas sintéticas.

    El servidor de red real no registra cuándo recibió la trama del receptor, así que esto es una
    medida sintética en este Mac (mismo código, misma E/S de disco), no la de los uplinks reales.
    """
    import struct

    spec = importlib.util.spec_from_file_location("lorawan_ns", RAIZ / "lorawan_ns.py")
    ns_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ns_mod)
    d = tempfile.mkdtemp()
    sent = []
    ns = ns_mod.NetworkServer(lambda dl, fr: sent.append(fr), f"{d}/s.json", f"{d}/l.jsonl", quiet=True)

    class SinUdp:  # no publicar datagramas de prueba al gateway
        def sendto(self, *a):
            pass
    ns.sock = SinUdp()
    dev = "70B3D57ED0000001"
    key = bytes.fromhex(ns_mod.DEVICES[dev]["app_key"])
    jr = bytes([0]) + ns_mod.le(1, 8) + ns_mod.le(int(dev, 16), 8) + ns_mod.le(0, 2)
    ns.handle_frame(jr + ns_mod.cmac4(key, jr))
    body = ns_mod.aes_enc(key, sent.pop()[1:])[:-4]
    jn, devaddr = ns_mod.unle(body[0:3]), ns_mod.unle(body[6:10])

    def deriva(tag):
        return ns_mod.aes_enc(key, (bytes([tag]) + ns_mod.le(jn, 3) + ns_mod.le(ns_mod.NET_ID, 3) + ns_mod.le(0, 2)).ljust(16, b"\0"))
    nwk, app = deriva(1), deriva(2)
    tiempos = []
    for fcnt in range(n):
        frm = ns_mod.crypt_payload(app, devaddr, fcnt, True, struct.pack("<hHBH", 2300, 5500, 0, fcnt))
        msg = bytes([0x40]) + ns_mod.le(devaddr, 4) + bytes([0]) + ns_mod.le(fcnt, 2) + bytes([1]) + frm
        trama = msg + ns_mod.data_mic(nwk, devaddr, fcnt, True, msg)
        t = time.perf_counter()
        ns.handle_frame(trama, -50, 9.0)
        tiempos.append((time.perf_counter() - t) * 1000)
    return {**informe.estadisticas(tiempos), "mediana": round(st.median(tiempos), 3), "n_tramas_sinteticas": n}


def main(argv=None):
    signal.signal(signal.SIGINT, signal.default_int_handler)  # Ctrl+C siempre como KeyboardInterrupt
    ap = argparse.ArgumentParser()
    ap.add_argument("--duracion", type=float, default=300, help="segundos de la prueba de enlace")
    ap.add_argument("--periodo", type=float, default=60, help="período de envío del firmware en s (60 por defecto)")
    ap.add_argument("--pir", action="store_true", help="prueba PIR de 60 s")
    ap.add_argument("--simular", action="store_true")
    ap.add_argument("--puerto", help="puerto serie del receptor (autodetectado por defecto)")
    ap.add_argument("--salida", type=Path, help="carpeta de resultados")
    a = ap.parse_args(argv)
    duracion = 60.0 if a.pir else a.duracion

    with Sesion(a.simular, a.periodo, a.puerto) as s:
        salida = a.salida or s.salida
        t0 = time.time()
        print(f"[{'rf3_pir' if a.pir else 'rf3_enlace'}] iniciado {time.strftime('%H:%M:%S')}; duración {duracion:.0f} s"
              + ("; MUEVE LA MANO delante del PIR de RF3 (>10 s entre movimientos)" if a.pir else ""))
        try:
            while time.time() - t0 < duracion:
                time.sleep(0.5)
        except KeyboardInterrupt:
            print("interrumpido: se analiza lo recogido hasta ahora")
        t1 = time.time()

    titulo = "Resultados de RF3 (LoRaWAN)"
    if a.pir:
        filas = informe.analizar_pir(s.carpeta, t0, t1)
        avisos = [] if filas else ["no se recibió ningún evento PIR de RF3"]
        informe.guardar_resultado(salida, "rf3_resultados", "rf3_pir", {
            "que_mide": "Eventos PIR de RF3 (uplink con mov=1) en la ventana, con el uplink asociado",
            "unidades": "hora local de recepción en el gateway; rssi dBm; snr dB",
            "resumen": {"duracion_s": round(t1 - t0, 1), "eventos_pir": len(filas)},
            "filas": filas, "avisos": avisos}, titulo)
        print(f"{len(filas)} eventos PIR de RF3:")
        for f in filas:
            print("  ", f)
    else:
        r = informe.analizar_rf3(s.carpeta, t0, t1, a.periodo)
        try:
            r["resumen"]["servidor_red_procesamiento_ms_sintetico"] = bench_servidor_red()
        except Exception as e:  # el benchmark es accesorio
            r["avisos"].append(f"no se pudo medir el servidor de red con tramas sintéticas: {e}")
        informe.guardar_resultado(salida, "rf3_resultados", "rf3_enlace", {
            "que_mide": "Enlace LoRaWAN de RF3: pérdida, RSSI/SNR, tiempos, filtro del gateway y ancho de banda",
            "unidades": "pérdida %, rssi dBm, snr dB, latencias ms, bytes por hora, r adimensional, ahorro %",
            **r}, titulo)
        import json
        print(json.dumps(r, indent=1, ensure_ascii=False))
    print(f"\nResultados en {salida / 'rf3_resultados.md'}")


if __name__ == "__main__":
    sys.exit(main())
