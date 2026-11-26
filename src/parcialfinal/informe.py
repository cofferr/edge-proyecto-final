"""Cálculos y salida (JSON + Markdown) de las pruebas de RF3 y de alcance. Sin E/S de hardware."""

import csv
import json
import statistics as st
from datetime import datetime
from pathlib import Path

from parcialfinal.metricas import paquetes_perdidos

TRAMA_APP_BYTES = 7         # payload de aplicación de RF3 (temp, hum, mov, cnt)
TRAMA_LORAWAN_BYTES = 20    # 7 de aplicación + 13 de cabecera/MIC (MHDR 1, DevAddr 4, FCtrl 1, FCnt 2, FPort 1, MIC 4)


# ------------------------------------------------------------------ estadística básica
def estadisticas(v: list[float]) -> dict:
    """n, media, mínimo, máximo y desviación típica muestral (0 si n < 2)."""
    if not v:
        return {"n": 0}
    return {"n": len(v), "media": round(st.mean(v), 3), "min": round(min(v), 3), "max": round(max(v), 3),
            "desv": round(st.stdev(v), 3) if len(v) > 1 else 0.0}


def esperados_por_tiempo(duracion_s: float, periodo_s: float) -> int:
    """Uplinks periódicos esperados en la ventana: round(duración / período).

    Una ventana de duración D contiene D/P envíos de media (según la fase, floor o ceil); se redondea
    para que una ventana de 180 s con período 60 s espere 3 y no 2 por unos milisegundos de diferencia.
    """
    return round(duracion_s / periodo_s) if periodo_s > 0 else 0


def perdida_pct(recibidos: int, esperados: int) -> float | None:
    """Pérdida en % respecto a lo esperado; nunca negativa (None si no se esperaba nada)."""
    if esperados <= 0:
        return None
    return round(max(0.0, (esperados - recibidos) / esperados * 100), 2)


# ------------------------------------------------------------------ lectura de CSV
def leer_filas(carpeta, archivo: str, campo_t: str, t0: float, t1: float) -> list[dict]:
    ruta = Path(carpeta) / archivo
    if not ruta.exists():
        return []
    with open(ruta, newline="", encoding="utf-8") as f:
        return [r for r in csv.DictReader(f)
                if r[campo_t] and t0 <= datetime.fromisoformat(r[campo_t]).timestamp() <= t1]


def _ep(s: str) -> float:
    return datetime.fromisoformat(s).timestamp()


def _num(filas, campo) -> list[float]:
    return [float(r[campo]) for r in filas if r.get(campo) not in (None, "")]


# ------------------------------------------------------------------ análisis de RF3
NO_MEDIBLE_E2E = {
    "medible": False,
    "motivo": "el payload de RF3 (temp, hum, mov, cnt) no lleva marca de tiempo del nodo y el servidor "
              "de red no registra la hora de recepción en el receptor (ts se genera al validar el uplink).",
    "aproximacion": "latencia ≈ tiempo en el aire del nodo (ToA, que el firmware imprime por serie; ~57 ms "
                    "teóricos para SF7/BW125 con 20 B) + receptor→servidor de red por USB (no medido) + "
                    "servidor de red→gateway (t_gw − t_ns, medido). Contrastar con cronómetro/vídeo moviendo "
                    "la mano frente al PIR de RF3 y viendo la alerta en el panel.",
}


def analizar_rf3(carpeta, t0: float, t1: float, periodo_s: float) -> dict:
    """Métricas de enlace y de filtrado de RF3 en [t0, t1] a partir de los CSV del gateway."""
    duracion = t1 - t0
    up = sorted(leer_filas(carpeta, "rf3_uplinks.csv", "t_gw", t0, t1), key=lambda r: r["t_gw"])
    n = len(up)
    esperados = esperados_por_tiempo(duracion, periodo_s)
    cnts = [int(r["cnt"]) for r in up]
    perdidos = paquetes_perdidos(cnts)
    huecos = [_ep(b["t_gw"]) - _ep(a["t_gw"]) for a, b in zip(up, up[1:])]
    lat = [(_ep(r["t_gw"]) - _ep(r["t_ns"])) * 1000 for r in up if r["t_ns"]]
    avisos = []
    if n == 0:
        avisos.append("cero uplinks recibidos en la ventana")
    elif n > esperados:
        avisos.append(f"{n} uplinks > {esperados} esperados: hay envíos extra (probables eventos PIR); "
                      "la pérdida por tiempo se acota a 0")
    pt = perdida_pct(n, esperados)
    if n and pt:
        avisos.append(f"pérdida por tiempo {pt} % ({n} de {esperados}); el contador solo detecta huecos "
                      "entre uplinks recibidos, no los perdidos al final de la ventana")
    if perdidos:
        avisos.append(f"{perdidos} paquetes perdidos según el contador de la trama")
    if any(b < a and a - b < 60000 for a, b in zip(cnts, cnts[1:])):
        avisos.append("el contador retrocedió (reinicio del nodo o nuevo join); esos saltos no cuentan como pérdida")

    tel = [r for r in leer_filas(carpeta, "telemetria.csv", "t_recepcion", t0, t1) if r["nodo"] == "RF3"]
    mags = {}
    for r in tel:
        m = mags.setdefault(r["magnitud"], {"recibidas": 0, "aceptadas": 0})
        m["recibidas"] += 1
        m["aceptadas"] += r["aceptada"] == "si"
    for m in mags.values():
        m["r"] = round(m["aceptadas"] / m["recibidas"], 4)
    rec = sum(m["recibidas"] for m in mags.values())
    ace = sum(m["aceptadas"] for m in mags.values())
    r_glob = ace / rec if rec else None

    cad = st.median(huecos) if huecos else None
    ancho = None
    if cad and r_glob is not None:
        por_hora = 3600 / cad
        ancho = {"uplinks_por_hora": round(por_hora, 1),
                 "bytes_por_hora_sin_filtro_payload": round(por_hora * TRAMA_APP_BYTES),
                 "bytes_por_hora_con_filtro_payload": round(por_hora * TRAMA_APP_BYTES * r_glob),
                 "bytes_por_hora_aire_lorawan": round(por_hora * TRAMA_LORAWAN_BYTES),
                 "ahorro_pct": round((1 - r_glob) * 100, 2)}
    return {
        "resumen": {
            "duracion_s": round(duracion, 1), "periodo_nominal_s": periodo_s,
            "uplinks_recibidos": n, "uplinks_esperados": esperados,
            "perdida_por_tiempo_pct": perdida_pct(n, esperados),
            "paquetes_perdidos_por_contador": perdidos,
            "perdida_por_contador_pct": round(perdidos / (n + perdidos) * 100, 2) if n + perdidos else None,
            "cadencia_mediana_s": round(cad, 3) if cad else None,
            "rssi_dbm": estadisticas(_num(up, "rssi")), "snr_db": estadisticas(_num(up, "snr")),
            "latencia_servidor_red_a_gateway_ms": estadisticas(lat),
            "eventos_pir_mov1": sum(r["mov"] == "1" for r in up),
            "filtro_gateway": {"magnitudes": mags, "recibidas": rec, "aceptadas": ace,
                               "r": round(r_glob, 4) if r_glob is not None else None},
            "ancho_de_banda": ancho,
            "latencia_extremo_a_extremo": NO_MEDIBLE_E2E,
        },
        "avisos": avisos,
    }


def analizar_pir(carpeta, t0: float, t1: float) -> list[dict]:
    """Eventos PIR de RF3 en [t0, t1], cada uno con su uplink asociado (misma marca de entrada al gateway)."""
    ups = {r["t_gw"]: r for r in leer_filas(carpeta, "rf3_uplinks.csv", "t_gw", t0, t1)}
    out = []
    for e in leer_filas(carpeta, "eventos.csv", "t_recepcion", t0, t1):
        if e["fuente"] != "RF3":
            continue
        u = ups.get(e["t_recepcion"], {})
        out.append({"hora": e["t_recepcion"][11:23], "tipo_quorum": e["tipo"], "fcnt": u.get("fcnt", ""),
                    "cnt": u.get("cnt", ""), "rssi": u.get("rssi", ""), "snr": u.get("snr", "")})
    return out


# ------------------------------------------------------------------ salida JSON + Markdown
def _aplanar(d: dict, pref="") -> list[tuple[str, object]]:
    out = []
    for k, v in d.items():
        out += _aplanar(v, f"{pref}{k}.") if isinstance(v, dict) else [(f"{pref}{k}", v)]
    return out


def escribir_md(todo: dict, ruta: Path, titulo: str) -> None:
    l = [f"# {titulo}", "", "Cada sección indica qué mide y en qué unidades; marcas de tiempo = recepción en el gateway.", ""]
    for clave, d in todo.items():
        l += [f"## {clave}", "", f"*{d.get('que_mide', '')}*", ""]
        if d.get("unidades"):
            l += [f"Unidades: {d['unidades']}", ""]
        if d.get("resumen"):
            l += ["| Cifra | Valor |", "|---|---|"] + [f"| {k} | {v} |" for k, v in _aplanar(d["resumen"])]
        if d.get("filas"):
            cols = list(d["filas"][0].keys())
            l += ["", "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
            l += ["| " + " | ".join(str(f.get(c, "")) for c in cols) + " |" for f in d["filas"]]
        if d.get("avisos"):
            l += ["", "**Avisos:** " + "; ".join(d["avisos"])]
        l += ["", f"_Generado: {d.get('generado', '')}_", ""]
    ruta.write_text("\n".join(l), encoding="utf-8")


def guardar_resultado(salida: Path, base: str, clave: str, datos: dict, titulo: str) -> Path:
    """Reemplaza la sección `clave` en <salida>/<base>.json y regenera <base>.md."""
    salida.mkdir(parents=True, exist_ok=True)
    ruta = salida / f"{base}.json"
    todo = json.loads(ruta.read_text()) if ruta.exists() else {}
    datos["generado"] = datetime.now().astimezone().isoformat(timespec="seconds")
    todo[clave] = datos
    ruta.write_text(json.dumps(todo, indent=2, ensure_ascii=False), encoding="utf-8")
    escribir_md(todo, salida / f"{base}.md", titulo)
    return ruta
