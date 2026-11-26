"""Análisis de la prueba de integración (RF1 + RF2 + RF3 a la vez). Funciones puras sobre CSV, log y muestras."""

import statistics as st
from datetime import datetime

from parcialfinal import informe


def contar_log(texto: str, patron: str) -> int:
    return sum(patron in linea for linea in texto.splitlines())


def transiciones(muestras: list[tuple[float, bool]]) -> dict:
    """De una serie (t, en_linea) cuenta las caídas (True→False) y el tiempo total fuera de línea."""
    caidas, fuera_s, t_caida = 0, 0.0, None
    previo = None
    for t, ok in muestras:
        if previo is True and ok is False:
            caidas += 1
            t_caida = t
        if previo is False and ok is True and t_caida is not None:
            fuera_s += t - t_caida
            t_caida = None
        previo = ok
    if t_caida is not None and muestras:
        fuera_s += muestras[-1][0] - t_caida
    return {"caidas": caidas, "tiempo_fuera_de_linea_s": round(fuera_s, 1)}


def estadisticas_cpu(muestras: list[tuple[float, float]]) -> dict:
    """muestras: (cpu_pct, rss_mb)."""
    if not muestras:
        return {"medible": False}
    cpu = [m[0] for m in muestras]
    return {"medible": True, "muestras": len(muestras), "cpu_media_pct": round(st.mean(cpu), 2),
            "cpu_max_pct": round(max(cpu), 2), "rss_max_mb": round(max(m[1] for m in muestras), 1)}


def analizar(carpeta, t0: float, t1: float, periodo_rf3: float, log: str,
             estados: dict[str, list[tuple[float, bool]]], cpu: list[tuple[float, float]],
             eventos_rf2_reinicio: int = 0) -> dict:
    dur = t1 - t0
    avisos = []
    # RF1
    tel = [r for r in informe.leer_filas(carpeta, "telemetria.csv", "t_recepcion", t0, t1) if r["nodo"] == "RF1"]
    marcas = sorted(datetime.fromisoformat(r["t_recepcion"]).timestamp() for r in tel if r["magnitud"] == "temperatura")
    gaps = [b - a for a, b in zip(marcas, marcas[1:])]
    huecos = [g for g in gaps if g > 6]
    rf1 = {"tramas_recibidas": len(marcas), "cadencia_media_s": round(st.mean(gaps), 3) if gaps else None,
           "huecos_mayores_6s": len(huecos), "hueco_max_s": round(max(gaps), 2) if gaps else None,
           "tramas_perdidas_estimadas": sum(round(g / 2) - 1 for g in huecos),
           "conexiones_ble": contar_log(log, "RF1 conectado"), "sesiones_terminadas": contar_log(log, "RF1 sesión terminada"),
           **transiciones(estados.get("RF1", []))}
    # RF2
    fotos = informe.leer_filas(carpeta, "rf2_fotos.csv", "t_recepcion", t0, t1)
    rf2 = {"eventos_pir": len(fotos), "fotos_sin_descargar": sum(1 for r in fotos if not r["tam_foto_bytes"] or r["tam_foto_bytes"] == "0"),
           "fallos_de_sondeo": contar_log(log, "RF2 sin respuesta"), "reinicios_detectados": eventos_rf2_reinicio,
           **transiciones(estados.get("RF2", []))}
    # RF3
    r3 = informe.analizar_rf3(carpeta, t0, t1, periodo_rf3)
    s3 = r3["resumen"]
    rf3 = {"uplinks_recibidos": s3["uplinks_recibidos"], "uplinks_esperados": s3["uplinks_esperados"],
           "perdida_por_tiempo_pct": s3["perdida_por_tiempo_pct"], "paquetes_perdidos_por_contador": s3["paquetes_perdidos_por_contador"],
           "eventos_pir_mov1": s3["eventos_pir_mov1"], "rssi_medio_dbm": s3["rssi_dbm"].get("media"),
           **transiciones(estados.get("RF3", []))}
    avisos += [f"RF3: {x}" for x in r3["avisos"]]
    # quórum
    evs = informe.leer_filas(carpeta, "eventos.csv", "t_recepcion", t0, t1)
    pir = [r for r in evs if r["tipo"] in ("sospecha", "alerta")]
    proc = [float(r["t_proc_ms"]) for r in pir if r["t_proc_ms"]]
    quorum = {"sospechas": sum(r["tipo"] == "sospecha" for r in pir), "alertas": sum(r["tipo"] == "alerta" for r in pir),
              "fines_de_alerta": sum(r["tipo"] == "fin_alerta" for r in evs),
              "procesamiento_evento_ms": informe.estadisticas(proc),
              "alerta_declarada_ms": informe.estadisticas([float(r["t_proc_ms"]) for r in pir if r["tipo"] == "alerta"])}
    for n, d in (("RF1", rf1), ("RF2", rf2), ("RF3", rf3)):
        if d["caidas"]:
            avisos.append(f"{n}: {d['caidas']} caída(s) a fuera de línea, {d['tiempo_fuera_de_linea_s']} s en total")
    if rf1["huecos_mayores_6s"]:
        avisos.append(f"RF1: {rf1['huecos_mayores_6s']} hueco(s) de más de 6 s entre tramas (máx {rf1['hueco_max_s']} s)")
    if rf2["fotos_sin_descargar"]:
        avisos.append(f"RF2: {rf2['fotos_sin_descargar']} evento(s) sin foto descargada")
    if rf1["tramas_recibidas"] == 0:
        avisos.append("RF1: no llegó ninguna trama")
    if rf3["uplinks_recibidos"] == 0:
        avisos.append("RF3: no llegó ningún uplink")
    return {"resumen": {"duracion_s": round(dur, 1), "rf1": rf1, "rf2": rf2, "rf3": rf3, "quorum": quorum,
                        "cpu_gateway": estadisticas_cpu(cpu)}, "avisos": avisos}
