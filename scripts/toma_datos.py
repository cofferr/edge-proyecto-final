#!/usr/bin/env python3
"""Toma de datos automatizada para el informe (RF1 y RF2). No cambia la lógica del gateway.

Cada tramo arranca el gateway real como subproceso (con --sin para omitir nodos no conectados),
espera/dispara lo necesario, lo detiene y analiza los CSV de data/ en el rango [inicio, fin].
Resultados en ~/Edge/InformeFinal/datos/resultados.json y resultados.md (cada tramo reemplaza
al anterior del mismo nombre).

Uso:
  uv run python scripts/toma_datos.py rf1_ble          # 2 min, solo RF1
  uv run python scripts/toma_datos.py filtrado_rf1     # 12 min, solo RF1
  uv run python scripts/toma_datos.py rf2_trigger      # 5 /trigger cada 10 s, solo RF2
  uv run python scripts/toma_datos.py rf2_pir          # hasta 5 eventos reales o 4 min, solo RF2
  uv run python scripts/toma_datos.py calculos         # recalcula cálculos con los tramos guardados
"""

import csv
import json
import statistics as st
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "data"
SALIDA = Path.home() / "Edge" / "InformeFinal" / "datos"
TRAMA_BLE_BYTES = 7


# ------------------------------------------------------------------ utilidades
def leer_csv(nombre: str, t0: float, t1: float) -> list[dict]:
    ruta = DATOS / nombre
    if not ruta.exists():
        return []
    with open(ruta, newline="", encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if t0 <= datetime.fromisoformat(r["t_recepcion"]).timestamp() <= t1]


def epoch(r: dict) -> float:
    return datetime.fromisoformat(r["t_recepcion"]).timestamp()


def resumen(v: list[float]) -> dict:
    return {"n": len(v), "min": min(v), "media": round(st.mean(v), 4), "max": max(v)} if v else {"n": 0}


def lanzar_gateway(tramo: str, sin: list[str]) -> subprocess.Popen:
    log = open(DATOS / f"gateway_{tramo}.log", "w")
    return subprocess.Popen(
        ["uv", "run", "python", "-m", "parcialfinal.gateway", "--sin", *sin],
        cwd=RAIZ, stdout=log, stderr=subprocess.STDOUT,
    )


def detener(p: subprocess.Popen) -> None:
    p.send_signal(2)  # SIGINT = Ctrl+C
    try:
        p.wait(10)
    except subprocess.TimeoutExpired:
        p.kill()


def guardar(tramo: str, datos: dict) -> None:
    SALIDA.mkdir(parents=True, exist_ok=True)
    ruta = SALIDA / "resultados.json"
    todo = json.loads(ruta.read_text()) if ruta.exists() else {}
    datos["generado"] = datetime.now().astimezone().isoformat(timespec="seconds")
    todo[tramo] = datos
    ruta.write_text(json.dumps(todo, indent=2, ensure_ascii=False), encoding="utf-8")
    escribir_md(todo)
    print(f"\n[{tramo}] guardado en {ruta}")


def aplanar(d: dict, pref="") -> list[tuple[str, object]]:
    out = []
    for k, v in d.items():
        if isinstance(v, dict):
            out += aplanar(v, f"{pref}{k}.")
        else:
            out.append((f"{pref}{k}", v))
    return out


def escribir_md(todo: dict) -> None:
    l = ["# Resultados de la toma de datos (RF1 y RF2)", "",
         "Generado por `scripts/toma_datos.py`. Cada tramo indica qué mide y en qué unidades; "
         "las marcas de tiempo son las de recepción en el gateway.", ""]
    for tramo, d in todo.items():
        l += [f"## {tramo}", "", f"*{d.get('que_mide', '')}*", ""]
        if d.get("unidades"):
            l += [f"Unidades: {d['unidades']}", ""]
        l += ["| Cifra | Valor |", "|---|---|"]
        l += [f"| {k} | {v} |" for k, v in aplanar(d.get("resumen", {}))]
        if d.get("eventos"):
            cols = list(d["eventos"][0].keys())
            l += ["", "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
            l += ["| " + " | ".join(str(e.get(c, "")) for c in cols) + " |" for e in d["eventos"]]
        if d.get("avisos"):
            l += ["", "**Avisos:** " + "; ".join(d["avisos"])]
        l += ["", f"_Generado: {d.get('generado', '')}_", ""]
    (SALIDA / "resultados.md").write_text("\n".join(l), encoding="utf-8")


# ------------------------------------------------------------------ tramos RF1
def analizar_rf1(tramo, t0, t1, descripcion):
    tel = leer_csv("telemetria.csv", t0, t1)
    tel = [r for r in tel if r["nodo"] == "RF1"]
    por_mag = {}
    for r in tel:
        por_mag.setdefault(r["magnitud"], []).append(r)
    marcas = sorted(epoch(r) for r in por_mag.get("temperatura", []))  # una por trama
    gaps = [b - a for a, b in zip(marcas, marcas[1:])]
    tramas = len(marcas)
    suelo = len(por_mag.get("humedad_suelo_mv", []))
    log = (DATOS / f"gateway_{tramo}.log").read_text(errors="replace")
    invalidas = log.count("trama inválida")
    avisos = []
    cad = round((marcas[-1] - marcas[0]) / (tramas - 1), 3) if tramas > 1 else None
    if cad is None or not 1.5 <= cad <= 2.5:
        avisos.append(f"cadencia media {cad} s no está cerca de 2 s")
    if tramas - suelo:
        avisos.append(f"{tramas - suelo} tramas con suelo sin dato (0xFFFF)")
    if invalidas:
        avisos.append(f"{invalidas} tramas inválidas")
    if gaps and max(gaps) > 6:
        avisos.append(f"hueco máximo entre tramas {max(gaps):.1f} s (posible reconexión)")
    mags = {}
    for m, filas in por_mag.items():
        acept = sum(r["aceptada"] == "si" for r in filas)
        mags[m] = {"recibidas": len(filas), "aceptadas": acept, "r": round(acept / len(filas), 4),
                   "valores": resumen([float(r["valor"]) for r in filas])}
    rec = sum(x["recibidas"] for x in mags.values())
    ace = sum(x["aceptadas"] for x in mags.values())
    res = {
        "duracion_s": round(t1 - t0, 1), "tramas_recibidas": tramas,
        "cadencia_media_s": cad, "cadencia_mediana_s": round(st.median(gaps), 3) if gaps else None,
        "cadencia_max_s": round(max(gaps), 3) if gaps else None,
        "tramas_suelo_sin_dato": tramas - suelo, "tramas_invalidas": invalidas,
        "magnitudes": mags,
        "global": {"recibidas": rec, "aceptadas": ace, "r": round(ace / rec, 4) if rec else None,
                   "ahorro_pct": round((1 - ace / rec) * 100, 2) if rec else None},
    }
    guardar(tramo, {"que_mide": descripcion,
                    "unidades": "temperatura °C, humedad aire %, humedad suelo mV, cadencia s, r adimensional, ahorro %",
                    "resumen": res, "avisos": avisos})
    print(json.dumps(res, indent=1, ensure_ascii=False))
    print("AVISOS:", avisos or "ninguno")


def tramo_rf1(tramo, duracion_s, descripcion):
    p = lanzar_gateway(tramo, ["rf2", "rf3"])
    t0 = time.time()
    print(f"[{tramo}] gateway arrancado a las {datetime.now():%H:%M:%S}; duración {duracion_s} s")
    try:
        time.sleep(60)
        if not leer_csv("telemetria.csv", t0, time.time()):
            print("ERROR: en 60 s no llegó ninguna trama de RF1 (¿encendida, Bluetooth permitido?)")
            detener(p)
            sys.exit(2)
        time.sleep(max(0, duracion_s - 60))
    finally:
        detener(p)
    analizar_rf1(tramo, t0, time.time(), descripcion)


# ------------------------------------------------------------------ tramos RF2
def cliente_rf2():
    import tomllib
    cfg = tomllib.loads((RAIZ / "config.toml").read_text())["rf2"]
    bases = [cfg["url"].rstrip("/")] + ([f"http://{cfg['ip_respaldo']}"] if cfg.get("ip_respaldo") else [])
    return bases


def get(bases, ruta, timeout=3):
    for b in bases:
        try:
            r = httpx.get(b + ruta, timeout=timeout)
            r.raise_for_status()
            return r
        except httpx.HTTPError as e:
            ultimo = e
    raise ultimo


def analizar_rf2(tramo, t0, t1, descripcion, extra=None, avisos=None):
    fotos = leer_csv("rf2_fotos.csv", t0, t1)
    evs = [r for r in leer_csv("eventos.csv", t0, t1) if r["fuente"] == "RF2"]
    etapas = [("captura", "t_capture_us"), ("gris", "t_gray_us"), ("diferencia", "t_diff_us"),
              ("morfologia", "t_morph_us"), ("metricas", "t_metrics_us"), ("jpeg", "t_jpeg_us"),
              ("total", "t_proc_us")]
    lista, por_etapa = [], {n: [] for n, _ in etapas}
    for i, r in enumerate(fotos, 1):
        e = {"n": i, "hora": r["t_recepcion"][11:23], "foto_bytes": int(r["tam_foto_bytes"] or 0),
             "confirmed": r["confirmed"], "reason": r["reason"], "area_pct": r["area_pct"]}
        for n, c in etapas:
            us = float(r[c]) if r[c] else None
            e[f"{n}_us"] = us
            e[f"{n}_ms"] = round(us / 1000, 3) if us is not None else None
            if us is not None:
                por_etapa[n].append(us)
        ev = next((x for x in evs if x["ruta_foto"] == r["ruta_foto"]), None)
        e["latencia_deteccion_a_foto_ms"] = float(ev["t_proc_ms"]) if ev else None
        lista.append(e)
    tam = [e["foto_bytes"] for e in lista if e["foto_bytes"]]
    lat = [e["latencia_deteccion_a_foto_ms"] for e in lista if e["latencia_deteccion_a_foto_ms"] is not None]
    res = {
        "eventos": len(fotos), "fotos_guardadas": len(tam),
        "foto_bytes": {**resumen(tam), "mediana": st.median(tam) if tam else None},
        "tiempos_us": {n: {"media": round(st.mean(v), 1), "max": max(v)} for n, v in por_etapa.items() if v},
        "tiempos_ms": {n: {"media": round(st.mean(v) / 1000, 3), "max": round(max(v) / 1000, 3)}
                       for n, v in por_etapa.items() if v},
        "latencia_deteccion_a_foto_ms": resumen(lat),
        "confirmados_por_el_nodo": sum(e["confirmed"] in ("True", "true", "1") for e in lista),
        **(extra or {}),
    }
    guardar(tramo, {"que_mide": descripcion,
                    "unidades": "tiempos de etapa en µs (y ms), foto en bytes, latencia en ms, area_pct en %",
                    "resumen": res, "eventos": lista, "avisos": avisos or []})
    print(json.dumps(res, indent=1, ensure_ascii=False))


def tramo_rf2_trigger():
    bases = cliente_rf2()
    st0 = get(bases, "/status").json()
    print("RF2 responde. /status:", {k: st0.get(k) for k in ("pir", "warming_up", "background_ready", "events")})
    avisos = []
    if st0.get("warming_up") or not st0.get("background_ready"):
        avisos.append("al iniciar: warming_up/background_ready no listos; los primeros /trigger pueden descartarse")
    p = lanzar_gateway("rf2_trigger", ["rf1", "rf3"])
    t0 = time.time()
    try:
        time.sleep(4)  # línea base de events en el gateway
        for i in range(5):
            r = get(bases, "/trigger", timeout=10)
            print(f"/trigger {i + 1}/5 -> HTTP {r.status_code} {r.text[:80]!r}")
            time.sleep(10)
        time.sleep(3)
    finally:
        detener(p)
    analizar_rf2("rf2_trigger", t0, time.time(), "5 disparos con /trigger espaciados 10 s: foto, tiempos por etapa y decisión local de RF2", avisos=avisos)


def tramo_rf2_pir():
    bases = cliente_rf2()
    st0 = get(bases, "/status").json()
    print("RF2 responde. /status:", {k: st0.get(k) for k in ("pir", "warming_up", "background_ready", "events")})
    p = lanzar_gateway("rf2_pir", ["rf1", "rf3"])
    t0 = time.time()
    print(f"[rf2_pir] gateway arrancado a las {datetime.now():%H:%M:%S}; agita la mano frente al PIR (>10 s entre movimientos)")
    try:
        time.sleep(4)
        while time.time() - t0 < 240:
            n = len([r for r in leer_csv("eventos.csv", t0, time.time()) if r["fuente"] == "RF2"])
            if n >= 5:
                break
            time.sleep(1)
        time.sleep(2)
    finally:
        detener(p)
    t1 = time.time()
    avisos = []
    n = len(leer_csv("rf2_fotos.csv", t0, t1))
    if n < 5:
        avisos.append(f"solo {n} eventos de 5 en {t1 - t0:.0f} s")
    analizar_rf2("rf2_pir", t0, t1, "Eventos reales del PIR de RF2 (hasta 5 o 4 min): foto, tiempos, decisión local y latencia de detección a foto guardada", extra={"duracion_s": round(t1 - t0, 1)}, avisos=avisos)


# ------------------------------------------------------------------ cálculos
def calculos():
    ruta = SALIDA / "resultados.json"
    todo = json.loads(ruta.read_text())
    out, fuentes, avisos = {}, {}, []
    if "filtrado_rf1" in todo and "rf1_ble" in todo:
        f, b = todo["filtrado_rf1"]["resumen"], todo["rf1_ble"]["resumen"]
        cad = f["cadencia_media_s"] or b["cadencia_media_s"]
        tramas_h = 3600 / cad
        sin = tramas_h * TRAMA_BLE_BYTES
        r = f["global"]["r"]
        out["rf1"] = {
            "cadencia_usada_s": cad, "tramas_por_hora": round(tramas_h, 1),
            "bytes_por_hora_sin_filtro": round(sin), "r_global": r,
            "bytes_por_hora_con_filtro": round(sin * r), "ahorro_pct": round((1 - r) * 100, 2),
        }
        fuentes["rf1"] = "cadencia y r de filtrado_rf1 (12 min); trama BLE de 7 bytes"
        avisos.append("el filtro actúa en el gateway: la radio BLE ya recibió la trama; el ahorro es de lo que se guarda/reenvía aguas arriba, con r por lectura (3 lecturas por trama)")
    fotos = [e["foto_bytes"] for k in ("rf2_trigger", "rf2_pir") if k in todo for e in todo[k].get("eventos", []) if e["foto_bytes"]]
    if fotos:
        medio = st.mean(fotos)
        h1s = 3600 * medio
        obs = {}
        for N in (0, 5, 30):
            v = N * medio
            obs[f"N={N}"] = {"bytes_por_hora": round(v), "ahorro_vs_1_foto_por_s_pct": round((1 - v / h1s) * 100, 3)}
        out["rf2"] = {"fotos_usadas": len(fotos), "tam_medio_foto_bytes": round(medio), "tam_mediano_foto_bytes": st.median(fotos),
                      "bytes_por_hora_1_foto_por_s": round(h1s), "bytes_por_hora_fotos_por_evento": obs}
        fuentes["rf2"] = "fotos de rf2_trigger + rf2_pir"
        tot = [todo[k]["resumen"]["tiempos_us"]["total"] for k in ("rf2_trigger", "rf2_pir") if k in todo and "total" in todo[k]["resumen"].get("tiempos_us", {})]
        if tot:
            out["rf2"]["tiempo_procesamiento_ms"] = {
                "media": round(st.mean(x["media"] for x in tot) / 1000, 3), "max": round(max(x["max"] for x in tot) / 1000, 3)}
        lat = [todo[k]["resumen"]["latencia_deteccion_a_foto_ms"] for k in ("rf2_trigger", "rf2_pir") if k in todo]
        lat = [x for x in lat if x.get("n")]
        if lat:
            out["rf2"]["latencia_deteccion_a_foto_ms"] = {"media": round(st.mean(x["media"] for x in lat), 1), "max": max(x["max"] for x in lat)}
    guardar("calculos", {
        "que_mide": "Calc 3 (ancho de banda) y cifras de RF2 derivadas de los tramos; fuentes: " + json.dumps(fuentes, ensure_ascii=False),
        "unidades": "bytes por hora, % de ahorro, ms", "resumen": out, "avisos": avisos})
    print(json.dumps(out, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    DATOS.mkdir(exist_ok=True)
    tramo = sys.argv[1] if len(sys.argv) > 1 else ""
    if tramo == "rf1_ble":
        tramo_rf1("rf1_ble", 120, "2 min con solo RF1: tramas recibidas, cadencia y rango de cada magnitud")
    elif tramo == "filtrado_rf1":
        tramo_rf1("filtrado_rf1", 720, "12 min con solo RF1: lecturas recibidas/aceptadas por magnitud, r y ahorro (1 - r) del filtro por umbral")
    elif tramo == "rf2_trigger":
        tramo_rf2_trigger()
    elif tramo == "rf2_pir":
        tramo_rf2_pir()
    elif tramo == "calculos":
        calculos()
    else:
        sys.exit(__doc__)
