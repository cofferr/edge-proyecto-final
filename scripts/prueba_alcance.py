#!/usr/bin/env python3
"""Prueba de alcance de RF3: ventanas consecutivas a distintas distancias.

Desatendida: las ventanas arrancan por tiempo (pausa + ventana), sin esperar confirmación. Registra en
<datos>/alcance_log.csv la hora programada y la real de cada fase. Anuncia con `say` (si existe) cada punto.

  uv run python scripts/prueba_alcance.py                       # 5, 10 y 20 m, 3 min cada una, pausa 20 s
  uv run python scripts/prueba_alcance.py --solo 10             # una sola distancia (se fusiona con las anteriores)
  uv run python scripts/prueba_alcance.py --simular --distancias 5 10 --ventana-s 15 --pausa-s 2 --periodo 2

Ctrl+C cierra limpio: detiene gateway y servidor de red y guarda lo medido (la ventana en curso, parcial).
Lanza `caffeinate` mientras corre para que el Mac no se suspenda.
"""

import argparse
import csv
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from parcialfinal import informe
from parcialfinal.procesos import Sesion, espera_hasta

COLUMNAS_LOG = ["evento", "distancia_m", "t_programada", "t_real"]


def iso(t: float) -> str:
    return datetime.fromtimestamp(t).astimezone().isoformat(timespec="seconds")


def anunciar(texto: str, simular: bool) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {texto}", flush=True)
    if not simular and shutil.which("say"):
        subprocess.Popen(["say", texto])


def fila_distancia(dist, t0, t1, periodo, carpeta, estado) -> tuple[dict, list[str]]:
    r = informe.analizar_rf3(carpeta, t0, t1, periodo)
    s = r["resumen"]
    fila = {
        "distancia_m": dist, "estado": estado, "duracion_s": s["duracion_s"],
        "recibidos": s["uplinks_recibidos"], "esperados": s["uplinks_esperados"],
        "perdida_pct": s["perdida_por_tiempo_pct"], "perdidos_contador": s["paquetes_perdidos_por_contador"],
    }
    for nombre, clave in (("rssi", "rssi_dbm"), ("snr", "snr_db")):
        e = s[clave]
        fila.update({f"{nombre}_media": e.get("media"), f"{nombre}_min": e.get("min"), f"{nombre}_max": e.get("max")})
    avisos = [f"{dist} m: {x}" for x in r["avisos"]]
    if estado != "completa":
        avisos.append(f"{dist} m: ventana {estado}")
    return fila, avisos


def main(argv=None):
    signal.signal(signal.SIGINT, signal.default_int_handler)  # Ctrl+C siempre como KeyboardInterrupt
    ap = argparse.ArgumentParser()
    ap.add_argument("--distancias", type=float, nargs="+", default=[5, 10, 20])
    ap.add_argument("--solo", type=float, help="una sola distancia (equivale a --distancias X)")
    ap.add_argument("--ventana-s", type=float, default=180)
    ap.add_argument("--pausa-s", type=float, default=20)
    ap.add_argument("--periodo", type=float, default=60, help="período de envío del firmware en s")
    ap.add_argument("--simular", action="store_true")
    ap.add_argument("--puerto")
    ap.add_argument("--salida", type=Path)
    a = ap.parse_args(argv)
    distancias = [a.solo] if a.solo else a.distancias
    if a.ventana_s < 2 * a.periodo:
        print(f"AVISO: ventana de {a.ventana_s:.0f} s con período {a.periodo:.0f} s da menos de 2 uplinks esperados")

    caf = None if a.simular or not shutil.which("caffeinate") else subprocess.Popen(
        ["caffeinate", "-dimsu", "-w", str(os.getpid())])
    interrumpido = []
    signal.signal(signal.SIGTERM, lambda *_: interrumpido.append(1))  # cierra limpio también con kill
    ventanas = []  # (dist, t0, t1, estado)
    try:
        with Sesion(a.simular, a.periodo, a.puerto) as s:
            salida = a.salida or s.salida
            salida.mkdir(parents=True, exist_ok=True)
            ruta_log = salida / "alcance_log.csv"
            nuevo = not ruta_log.exists()
            log = open(ruta_log, "a", newline="", encoding="utf-8")
            w = csv.writer(log)
            if nuevo:
                w.writerow(COLUMNAS_LOG)

            def registrar(evento, dist, prog):
                w.writerow([evento, dist, iso(prog), iso(time.time())])
                log.flush()

            base = time.time() + 2
            en_curso = None  # (dist, t0) de la ventana abierta, para guardarla parcial si se interrumpe
            try:
                for i, d in enumerate(distancias):
                    p_pausa = base + i * (a.pausa_s + a.ventana_s)
                    p_ini, p_fin = p_pausa + a.pausa_s, p_pausa + a.pausa_s + a.ventana_s
                    espera_hasta(p_pausa, lambda: bool(interrumpido))
                    registrar("pausa_inicio", d, p_pausa)
                    anunciar(f"Colócate a {d:g} metros. La ventana empieza en {a.pausa_s:.0f} segundos", a.simular)
                    espera_hasta(p_ini, lambda: bool(interrumpido))
                    if interrumpido:
                        break
                    t0 = time.time()
                    en_curso = (d, t0)
                    registrar("ventana_inicio", d, p_ini)
                    anunciar(f"Ventana de {d:g} metros iniciada", a.simular)
                    espera_hasta(p_fin, lambda: bool(interrumpido))
                    t1 = time.time()
                    registrar("ventana_interrumpida" if interrumpido else "ventana_fin", d, p_fin)
                    en_curso = None
                    ventanas.append((d, t0, t1, "interrumpida" if interrumpido else "completa"))
                    if interrumpido:
                        break
                anunciar("Prueba de alcance terminada", a.simular)
            except KeyboardInterrupt:
                print("\nCtrl+C: cerrando limpio y guardando lo medido")
                if en_curso:
                    registrar("ventana_interrumpida", en_curso[0], time.time())
                    ventanas.append((*en_curso, time.time(), "interrumpida"))
            finally:
                log.close()
    finally:
        if caf:
            caf.terminate()

    # análisis (con el gateway ya parado) y fusión con ventanas de ejecuciones anteriores
    ruta_json = salida / "alcance_resultados.json"
    previo = json.loads(ruta_json.read_text()).get("alcance", {}) if ruta_json.exists() else {}
    filas = {str(f["distancia_m"]): f for f in previo.get("filas", [])}
    avisos_prev = {x for x in previo.get("avisos", [])}
    for d, t0, t1, estado in ventanas:
        fila, avisos = fila_distancia(d, t0, t1, a.periodo, s.carpeta, estado)
        filas[str(d)] = fila
        avisos_prev = {x for x in avisos_prev if not x.startswith(f"{d} m:")} | set(avisos)
    if not ventanas:
        print("no se completó ninguna ventana; no hay nada que guardar")
        return 1
    datos = {
        "que_mide": "Alcance LoRaWAN de RF3: uplinks recibidos frente a esperados, pérdida y RSSI/SNR por distancia",
        "unidades": "distancia m; pérdida % (por tiempo y período); rssi dBm; snr dB",
        "filas": [filas[k] for k in sorted(filas, key=float)], "avisos": sorted(avisos_prev)}
    for base_json, titulo in (("alcance_resultados", "Resultados de la prueba de alcance de RF3"),
                              ("rf3_resultados", "Resultados de RF3 (LoRaWAN)")):
        informe.guardar_resultado(salida, base_json, "alcance", dict(datos), titulo)
    print(json.dumps(datos["filas"], indent=1, ensure_ascii=False))
    print("AVISOS:", datos["avisos"] or "ninguno")
    print(f"\nResultados en {salida / 'alcance_resultados.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
