"""Cálculo de métricas para el informe a partir de los CSV (lógica separada del script)."""

import csv
from datetime import datetime
from pathlib import Path
from statistics import mean


def _leer(carpeta: Path, archivo: str, campo_t: str, desde, hasta) -> list[dict]:
    ruta = Path(carpeta) / archivo
    if not ruta.exists():
        return []
    with open(ruta, newline="", encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    return [r for r in filas if r[campo_t] and desde <= datetime.fromisoformat(r[campo_t]) <= hasta]


def _num(filas, campo) -> list[float]:
    return [float(r[campo]) for r in filas if r.get(campo) not in (None, "")]


def paquetes_perdidos(cnts: list[int]) -> int:
    """Huecos en el contador de 16 bits de la trama. Un salto 'hacia atrás' (reinicio del nodo) no cuenta."""
    perdidos = 0
    for prev, cnt in zip(cnts, cnts[1:]):
        delta = (cnt - prev) % 65536
        if 1 < delta <= 32768:
            perdidos += delta - 1
    return perdidos


def calcular(carpeta, desde: datetime, hasta: datetime) -> dict:
    tel = _leer(carpeta, "telemetria.csv", "t_recepcion", desde, hasta)
    por_nodo = {}
    for r in tel:
        d = por_nodo.setdefault(r["nodo"], {"recibidas": 0, "aceptadas": 0, "magnitudes": {}})
        m = d["magnitudes"].setdefault(r["magnitud"], {"recibidas": 0, "aceptadas": 0})
        for x in (d, m):
            x["recibidas"] += 1
            x["aceptadas"] += r["aceptada"] == "si"
    for d in por_nodo.values():
        for x in (d, *d["magnitudes"].values()):
            x["r"] = x["aceptadas"] / x["recibidas"]

    fotos = _leer(carpeta, "rf2_fotos.csv", "t_recepcion", desde, hasta)
    etapas = ["t_capture_us", "t_gray_us", "t_diff_us", "t_morph_us", "t_metrics_us", "t_proc_us", "t_jpeg_us"]
    tam = _num(fotos, "tam_foto_bytes")
    rf2 = {
        "eventos": len(fotos),
        "tam_medio_foto_bytes": mean(tam) if tam else None,
        "etapas_us": {e: mean(v) for e in etapas if (v := _num(fotos, e))},
    }

    up = sorted(_leer(carpeta, "rf3_uplinks.csv", "t_gw", desde, hasta), key=lambda r: r["t_gw"])
    rssi, snr, proc = _num(up, "rssi"), _num(up, "snr"), _num(up, "t_proc_ms")
    rf3 = {
        "uplinks": len(up),
        "rssi_medio": mean(rssi) if rssi else None,
        "snr_medio": mean(snr) if snr else None,
        "paquetes_perdidos": paquetes_perdidos([int(r["cnt"]) for r in up]),
        "t_proc_medio_ms": mean(proc) if proc else None,
        "latencia_ns_a_gateway_medio_ms": mean(
            (datetime.fromisoformat(r["t_gw"]) - datetime.fromisoformat(r["t_ns"])).total_seconds() * 1000
            for r in up if r["t_ns"]
        ) if any(r["t_ns"] for r in up) else None,
    }

    ev = _leer(carpeta, "eventos.csv", "t_recepcion", desde, hasta)
    return {
        "telemetria": por_nodo, "rf2": rf2, "rf3": rf3,
        "sospechas": sum(r["tipo"] == "sospecha" for r in ev),
        "alertas": sum(r["tipo"] == "alerta" for r in ev),
    }


def _f(x, fmt="{:.2f}"):
    return "—" if x is None else fmt.format(x)


def formatear(m: dict) -> str:
    l = ["== Telemetría: recibidas / aceptadas / r =="]
    for nodo, d in sorted(m["telemetria"].items()):
        l.append(f"{nodo}: {d['recibidas']} / {d['aceptadas']} / r={d['r']:.3f}")
        for mag, x in sorted(d["magnitudes"].items()):
            l.append(f"    {mag}: {x['recibidas']} / {x['aceptadas']} / r={x['r']:.3f}")
    if not m["telemetria"]:
        l.append("(sin lecturas en el rango)")
    r2, r3 = m["rf2"], m["rf3"]
    l += ["", "== RF2 (ESP32-CAM) ==", f"eventos con foto: {r2['eventos']}",
          f"tamaño medio de foto: {_f(r2['tam_medio_foto_bytes'], '{:.0f}')} bytes",
          "tiempos medios por etapa (µs):"]
    l += [f"    {e}: {v:.0f}" for e, v in r2["etapas_us"].items()]
    l += ["", "== RF3 (LoRaWAN) ==", f"uplinks: {r3['uplinks']}",
          f"RSSI medio: {_f(r3['rssi_medio'])} dBm   SNR medio: {_f(r3['snr_medio'])} dB",
          f"paquetes perdidos (contador de la trama): {r3['paquetes_perdidos']}",
          f"procesamiento en gateway medio: {_f(r3['t_proc_medio_ms'], '{:.3f}')} ms",
          f"latencia servidor de red -> gateway media: {_f(r3['latencia_ns_a_gateway_medio_ms'], '{:.3f}')} ms",
          "", "== Quórum PIR ==", f"sospechas: {m['sospechas']}   alertas: {m['alertas']}"]
    return "\n".join(l)
