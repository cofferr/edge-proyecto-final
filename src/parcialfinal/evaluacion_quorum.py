"""Lógica de evaluación de los escenarios de la prueba de quórum (pura, sin hardware).

Un "evento" es un dict {t: epoch, tipo: sospecha|alerta|fin_alerta, fuente: RF2|RF3|"", t_proc_ms: float}
tal como lo escribe el gateway en eventos.csv. La evaluación solo observa; nunca decide por el gateway.
"""

from datetime import datetime

from parcialfinal.informe import leer_filas

PIR = ("sospecha", "alerta")


def leer_eventos(carpeta, t0: float, t1: float) -> list[dict]:
    """Eventos de eventos.csv en [t0, t1], ordenados por hora de recepción."""
    out = []
    for r in leer_filas(carpeta, "eventos.csv", "t_recepcion", t0, t1):
        out.append({"t": datetime.fromisoformat(r["t_recepcion"]).timestamp(), "tipo": r["tipo"],
                    "fuente": r["fuente"], "decision_local": r["decision_local_rf2"],
                    "t_proc_ms": float(r["t_proc_ms"] or 0)})
    return sorted(out, key=lambda e: e["t"])


def _hora(t: float) -> str:
    return datetime.fromtimestamp(t).strftime("%H:%M:%S.%f")[:-3]


def _lista(evs: list[dict]) -> list[str]:
    return [f"{_hora(e['t'])} {e['fuente'] or '-'} {e['tipo']}" for e in evs]


def evaluar_sospecha(eventos: list[dict], fuente: str) -> dict:
    """Solo `fuente` se activa: se espera ≥1 sospecha de esa fuente, ninguna de la otra y ninguna alerta."""
    pir = [e for e in eventos if e["tipo"] in PIR]
    propios = [e for e in pir if e["fuente"] == fuente]
    ajenos = [e for e in pir if e["fuente"] != fuente]
    alertas = [e for e in pir if e["tipo"] == "alerta"]
    if not pir:
        return {"coincide": False, "resultado": "sin eventos (ambiguo)",
                "nota": f"el PIR de {fuente} no generó ningún evento: no se puede juzgar", "eventos": []}
    if ajenos or alertas:
        return {"coincide": False, "resultado": "alerta" if alertas else "evento de la otra fuente",
                "nota": "se activó también la otra fuente (movimiento no aislado)", "eventos": _lista(pir)}
    if any(e["tipo"] != "sospecha" for e in propios):
        return {"coincide": False, "resultado": "inesperado", "nota": "tipo distinto de sospecha", "eventos": _lista(pir)}
    return {"coincide": True, "resultado": "sospecha", "nota": "", "eventos": _lista(pir),
            "n_sospechas": len(propios)}


def evaluar_alerta(eventos: list[dict], ventana_s: float, tolerancia_s: float = 1.5) -> dict:
    """RF2 y RF3 dentro de W: se espera alerta; mide la declaración y el apagado."""
    pir = [e for e in eventos if e["tipo"] in PIR]
    alertas = [e for e in pir if e["tipo"] == "alerta"]
    if not alertas:
        fuentes = {e["fuente"] for e in pir}
        return {"coincide": False, "resultado": "sin alerta",
                "nota": ("solo se activó " + "/".join(sorted(fuentes))) if len(fuentes) < 2 else
                        "las dos fuentes se activaron pero a más de W entre sí",
                "eventos": _lista(pir)}
    a = alertas[0]
    previos = [e for e in pir if e["t"] < a["t"] and e["fuente"] != a["fuente"]]
    primero = previos[-1] if previos else None
    fins = [e for e in eventos if e["tipo"] == "fin_alerta" and e["t"] > a["t"]]
    res = {"coincide": True, "resultado": "alerta", "nota": "", "eventos": _lista(eventos),
           "primer_pir": f"{primero['fuente']} {_hora(primero['t'])}" if primero else "",
           "segundo_pir": f"{a['fuente']} {_hora(a['t'])}",
           "separacion_pirs_s": round(a["t"] - primero["t"], 3) if primero else None,
           "declaracion_alerta_ms": round(a["t_proc_ms"], 3)}
    if not fins:
        res.update({"coincide": False, "nota": "la alerta no se apagó durante la observación (¿siguieron los movimientos?)",
                    "apagado_s": None})
        return res
    ultimo = max(e["t"] for e in pir if e["t"] < fins[0]["t"])
    apagado = fins[0]["t"] - ultimo
    res["apagado_s"] = round(apagado, 3)
    res["ventana_esperada_s"] = ventana_s
    if not ventana_s < apagado <= ventana_s + tolerancia_s:
        res.update({"coincide": False, "nota": f"apagado a {apagado:.2f} s del último evento; se esperaba W={ventana_s} s "
                                               f"(+{tolerancia_s} s de resolución del tick)"})
    return res


def evaluar_nodo_caido(eventos: list[dict], fuente_viva: str, t_ultimo_dato_caido: float | None,
                       t_fuera_de_linea: float | None, timeout_s: float) -> dict:
    """El nodo caído deja de aportar: se espera sospecha de la fuente viva, sin alerta, y que el gateway
    acabe marcando el nodo caído como fuera de línea (tras `timeout_s` sin datos)."""
    pir = [e for e in eventos if e["tipo"] in PIR]
    propios = [e for e in pir if e["fuente"] == fuente_viva]
    alertas = [e for e in pir if e["tipo"] == "alerta"]
    res = {"eventos": _lista(pir), "timeout_configurado_s": timeout_s,
           "ultimo_dato_nodo_caido": _hora(t_ultimo_dato_caido) if t_ultimo_dato_caido else None,
           "fuera_de_linea_a_las": _hora(t_fuera_de_linea) if t_fuera_de_linea else None}
    if t_fuera_de_linea and t_ultimo_dato_caido:
        res["tiempo_hasta_detectar_caida_s"] = round(t_fuera_de_linea - t_ultimo_dato_caido, 2)
    notas = []
    if not propios:
        notas.append(f"el PIR de {fuente_viva} no generó eventos: no se probó la reacción a la caída")
    if alertas:
        a = alertas[0]
        previos = [e for e in pir if e["fuente"] != a["fuente"] and 0 <= a["t"] - e["t"] <= 1e9 and e["t"] < a["t"]]
        if previos:
            sep = a["t"] - previos[-1]["t"]
            notas.append(f"alerta por quórum legítima: el último PIR de {previos[-1]['fuente']} fue {sep:.1f} s antes "
                         "(dentro de W); el escenario no queda aislado, hay que repetirlo esperando más de W tras apagar el nodo")
        else:
            notas.append("hubo alerta con un nodo caído (inesperado)")
    if not t_fuera_de_linea:
        notas.append("el gateway no marcó el nodo como fuera de línea durante la observación")
    notas.append("el gateway no emite un aviso aparte: la caída solo se ve como estado 'fuera de línea' "
                 "en estado.json y en el panel")
    res["coincide"] = bool(propios) and not alertas and bool(t_fuera_de_linea)
    res["resultado"] = ("sospecha sin alerta" if propios and not alertas else
                        "alerta" if alertas else "sin eventos (ambiguo)")
    res["nota"] = "; ".join(notas)
    return res
