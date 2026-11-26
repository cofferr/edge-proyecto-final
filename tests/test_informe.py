import json
from datetime import datetime

import pytest

from parcialfinal import informe
from parcialfinal.config import Rf3
from parcialfinal.nodos.rf3_lora import AdaptadorRf3


def test_estadisticas():
    e = informe.estadisticas([-50, -60, -70])
    assert (e["n"], e["media"], e["min"], e["max"], e["desv"]) == (3, -60.0, -70, -50, 10.0)
    assert informe.estadisticas([]) == {"n": 0}
    assert informe.estadisticas([5])["desv"] == 0.0


def test_esperados_por_tiempo():
    assert informe.esperados_por_tiempo(300, 60) == 5
    assert informe.esperados_por_tiempo(179.99, 60) == 3   # milisegundos de menos no restan un envío
    assert informe.esperados_por_tiempo(89, 60) == 1
    assert informe.esperados_por_tiempo(180, 10) == 18
    assert informe.esperados_por_tiempo(10, 0) == 0


def test_perdida_pct():
    assert informe.perdida_pct(4, 5) == 20.0
    assert informe.perdida_pct(5, 5) == 0.0
    assert informe.perdida_pct(7, 5) == 0.0  # envíos extra por PIR: no hay pérdida negativa
    assert informe.perdida_pct(0, 5) == 100.0
    assert informe.perdida_pct(0, 0) is None


def _alimentar(nucleo, cnts, t_ini, paso=10.0, mov=None, temps=None):
    a = AdaptadorRf3(nucleo, Rf3())
    for i, c in enumerate(cnts):
        t = t_ini + i * paso
        a.procesar({"ts": t - 0.002, "fcnt": c, "cnt": c, "rssi": -60 - i, "snr": 9.0,
                    "temp_c": (temps[i] if temps else 20.0), "hum_pct": 50.0,
                    "mov": 1 if mov and i in mov else 0}, t_gw=t)


def test_analizar_rf3_con_perdidas_y_filtro(nucleo):
    t0 = datetime.now().timestamp()
    _alimentar(nucleo, [0, 1, 3, 4, 5], t0, temps=[20, 20, 21, 21, 21])  # falta el cnt 2
    r = informe.analizar_rf3(nucleo.almacen.carpeta, t0 - 1, t0 + 50, periodo_s=10)
    s = r["resumen"]
    assert s["uplinks_recibidos"] == 5 and s["uplinks_esperados"] == 5   # 51 s / 10 s = 5,1
    assert s["paquetes_perdidos_por_contador"] == 1
    assert s["perdida_por_contador_pct"] == pytest.approx(16.67)
    assert s["rssi_dbm"]["min"] == -64 and s["rssi_dbm"]["max"] == -60
    assert s["cadencia_mediana_s"] == 10.0
    assert s["latencia_servidor_red_a_gateway_ms"]["media"] == pytest.approx(2.0, abs=0.5)
    # filtro: humedad constante (1 aceptada de 5), temperatura 20→21 (2 aceptadas de 5)
    assert s["filtro_gateway"]["recibidas"] == 10 and s["filtro_gateway"]["aceptadas"] == 3
    assert s["ancho_de_banda"]["bytes_por_hora_sin_filtro_payload"] == 360 * 7
    assert s["ancho_de_banda"]["ahorro_pct"] == 70.0
    assert s["latencia_extremo_a_extremo"]["medible"] is False
    assert any("perdidos" in x for x in r["avisos"])


def test_ventana_vacia_avisa(nucleo):
    t = datetime.now().timestamp()
    r = informe.analizar_rf3(nucleo.almacen.carpeta, t, t + 180, periodo_s=60)
    assert r["resumen"]["uplinks_recibidos"] == 0 and r["resumen"]["perdida_por_tiempo_pct"] == 100.0
    assert any("cero uplinks" in x for x in r["avisos"])


def test_pir_lista_eventos_con_su_uplink(nucleo):
    t0 = datetime.now().timestamp()
    _alimentar(nucleo, [0, 1, 2], t0, mov={1})
    ev = informe.analizar_pir(nucleo.almacen.carpeta, t0 - 1, t0 + 60)
    assert len(ev) == 1 and ev[0]["cnt"] == "1" and ev[0]["tipo_quorum"] == "sospecha"


def test_guardar_resultado_reemplaza_la_seccion(tmp_path):
    informe.guardar_resultado(tmp_path, "x", "a", {"que_mide": "uno", "resumen": {"k": 1}}, "T")
    informe.guardar_resultado(tmp_path, "x", "a", {"que_mide": "dos", "resumen": {"k": 2}, "filas": [{"c": 1}]}, "T")
    d = json.loads((tmp_path / "x.json").read_text())
    assert d["a"]["resumen"]["k"] == 2 and "generado" in d["a"]
    md = (tmp_path / "x.md").read_text()
    assert "dos" in md and "uno" not in md and "| c |" in md


def test_perdida_al_final_de_la_ventana_avisa(nucleo):
    t0 = datetime.now().timestamp()
    _alimentar(nucleo, [26], t0)  # llegó 1 de 3 esperados: el contador no ve hueco
    r = informe.analizar_rf3(nucleo.almacen.carpeta, t0 - 1, t0 + 179, periodo_s=60)
    assert r["resumen"]["paquetes_perdidos_por_contador"] == 0
    assert r["resumen"]["perdida_por_tiempo_pct"] == pytest.approx(66.67)
    assert any("pérdida por tiempo" in x for x in r["avisos"])
