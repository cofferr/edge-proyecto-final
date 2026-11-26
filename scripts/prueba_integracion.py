#!/usr/bin/env python3
"""Prueba de integración: RF1 + RF2 + RF3 activos a la vez (por defecto 10 min).

  uv run python scripts/prueba_integracion.py [--duracion 600] [--periodo 60]
  uv run python scripts/prueba_integracion.py --simular --duracion 90      # sin hardware (data_sim/)

Guarda tramas y eventos por nodo, pérdidas, caídas/reinicios, uso de CPU del gateway (psutil) y los tiempos de
los eventos de quórum. Durante la prueba se pueden mover las manos frente a los PIR de RF2 y RF3 para generar
sospechas y alertas. Solo observa: no cambia la lógica del gateway.
Salida: <datos>/integracion_resultados.json/.md
"""

import argparse
import json
import signal
import sys
import time
from pathlib import Path

from parcialfinal import informe
from parcialfinal import integracion as ig
from parcialfinal.procesos import Sesion


_PROC = {}


def muestra_cpu(pid: int) -> tuple[float, float] | None:
    """(%CPU en el intervalo desde la muestra anterior, RSS en MB) con psutil; None si no se puede medir.

    El % es de un núcleo (100 = un núcleo completo). La primera llamada solo fija la referencia.
    """
    try:
        import psutil
        p = _PROC.get(pid)
        if p is None:
            p = _PROC[pid] = psutil.Process(pid)
            p.cpu_percent(None)
            return None
        return p.cpu_percent(None), p.memory_info().rss / 1048576
    except Exception:
        return None


def main(argv=None):
    signal.signal(signal.SIGINT, signal.default_int_handler)
    ap = argparse.ArgumentParser()
    ap.add_argument("--duracion", type=float, default=600)
    ap.add_argument("--periodo", type=float, default=60, help="período de envío de RF3 (s)")
    ap.add_argument("--simular", action="store_true")
    ap.add_argument("--puerto")
    ap.add_argument("--salida", type=Path)
    a = ap.parse_args(argv)
    periodo = 2.0 if a.simular else a.periodo
    sesion = Sesion(a.simular, periodo, a.puerto, sin=(), ventana_s=5, timeout_rf3_s=12, nombre="integracion")
    estados = {"RF1": [], "RF2": [], "RF3": []}
    cpu, reinicios_rf2, ev_prev = [], 0, None
    with sesion as s:
        salida = a.salida or s.salida
        t0 = time.time()
        print(f"[integracion] iniciada {time.strftime('%H:%M:%S')}; {a.duracion:.0f} s con RF1+RF2+RF3. "
              "Mueve las manos frente a los PIR de RF2 y RF3 cuando quieras (alertas = ambos en < W).", flush=True)
        proximo_cpu = 0
        try:
            while time.time() - t0 < a.duracion:
                try:
                    e = json.loads((s.carpeta / "estado.json").read_text())
                    for n in estados:
                        estados[n].append((e["t_estado"], e["nodos"][n]["en_linea"]))
                    ev = e["nodos"]["RF2"]["extra"].get("events")
                    if ev is not None and ev_prev is not None and ev < ev_prev:
                        reinicios_rf2 += 1  # el contador de eventos del nodo bajó: se reinició
                    ev_prev = ev if ev is not None else ev_prev
                except (OSError, ValueError, KeyError):
                    pass
                if time.time() >= proximo_cpu:
                    m = muestra_cpu(s.gateway.pid)
                    if m:
                        cpu.append(m)
                    proximo_cpu = time.time() + 5
                time.sleep(1)
        except KeyboardInterrupt:
            print("interrumpido: se analiza lo recogido hasta ahora")
        t1 = time.time()
    log = (s.carpeta / "gateway_rf3.log").read_text(errors="replace")
    r = ig.analizar(s.carpeta, t0, t1, periodo, log, estados, cpu, reinicios_rf2)
    informe.guardar_resultado(salida, "integracion_resultados", "integracion", {
        "que_mide": "RF1, RF2 y RF3 activos a la vez: tramas/eventos por nodo, pérdidas, caídas, CPU del gateway y tiempos de quórum",
        "unidades": "duración s; cadencias s; pérdidas %; procesamiento y alerta_declarada en ms; CPU % de un núcleo; RSS MB",
        **r}, "Resultados de la prueba de integración")
    print(json.dumps(r["resumen"], indent=1, ensure_ascii=False))
    print("AVISOS:", r["avisos"] or "ninguno")
    print(f"\nResultados en {salida / 'integracion_resultados.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
