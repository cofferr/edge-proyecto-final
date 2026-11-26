import pytest

from parcialfinal import evaluacion_quorum as q


def e(t, tipo, fuente="", ms=0.5):
    return {"t": t, "tipo": tipo, "fuente": fuente, "decision_local": "", "t_proc_ms": ms}


def test_sospecha_un_solo_pir_coincide():
    r = q.evaluar_sospecha([e(100, "sospecha", "RF3")], "RF3")
    assert r["coincide"] and r["resultado"] == "sospecha"


def test_sospecha_sin_eventos_es_ambigua():
    r = q.evaluar_sospecha([], "RF2")
    assert not r["coincide"] and "ambiguo" in r["resultado"]


def test_sospecha_con_la_otra_fuente_no_coincide():
    r = q.evaluar_sospecha([e(100, "sospecha", "RF3"), e(101, "sospecha", "RF2")], "RF3")
    assert not r["coincide"]


def test_sospecha_que_deriva_en_alerta_no_coincide():
    r = q.evaluar_sospecha([e(100, "sospecha", "RF3"), e(105, "alerta", "RF2")], "RF3")
    assert not r["coincide"] and r["resultado"] == "alerta"


def test_alerta_declaracion_y_apagado():
    evs = [e(100, "sospecha", "RF3"), e(110, "alerta", "RF2", ms=2.5), e(140.4, "fin_alerta")]
    r = q.evaluar_alerta(evs, 30)
    assert r["coincide"] and r["declaracion_alerta_ms"] == 2.5
    assert r["separacion_pirs_s"] == 10 and r["apagado_s"] == pytest.approx(30.4)


def test_alerta_apagado_fuera_de_tolerancia():
    r = q.evaluar_alerta([e(100, "sospecha", "RF3"), e(110, "alerta", "RF2"), e(150, "fin_alerta")], 30)
    assert not r["coincide"] and "apagado" in r["nota"]


def test_apagado_se_cuenta_desde_el_ultimo_evento_y_no_desde_la_alerta():
    evs = [e(100, "sospecha", "RF3"), e(110, "alerta", "RF2"), e(120, "sospecha", "RF3"), e(150.5, "fin_alerta")]
    assert q.evaluar_alerta(evs, 30)["apagado_s"] == pytest.approx(30.5)


def test_alerta_no_se_apaga_en_la_observacion():
    r = q.evaluar_alerta([e(100, "sospecha", "RF3"), e(110, "alerta", "RF2")], 30)
    assert not r["coincide"] and r["apagado_s"] is None


def test_dos_pir_fuera_de_ventana_sin_alerta():
    r = q.evaluar_alerta([e(100, "sospecha", "RF3"), e(140, "sospecha", "RF2")], 30)
    assert not r["coincide"] and "más de W" in r["nota"]


def test_nodo_caido_coincide():
    r = q.evaluar_nodo_caido([e(200, "sospecha", "RF2")], "RF2", 150.0, 301.0, 150)
    assert r["coincide"] and r["tiempo_hasta_detectar_caida_s"] == 151.0


def test_nodo_caido_sin_deteccion_o_sin_evento():
    assert not q.evaluar_nodo_caido([e(200, "sospecha", "RF2")], "RF2", 150.0, None, 150)["coincide"]
    r = q.evaluar_nodo_caido([], "RF2", 150.0, 301.0, 150)
    assert not r["coincide"] and "ambiguo" in r["resultado"]


def test_nodo_caido_alerta_legitima_por_evento_previo_del_nodo_caido():
    evs = [e(100, "sospecha", "RF3"), e(122, "alerta", "RF2")]  # el último PIR de RF3 fue 22 s antes (< W)
    r = q.evaluar_nodo_caido(evs, "RF2", 100.0, 250.0, 150)
    assert not r["coincide"] and "legítima" in r["nota"] and "22.0 s" in r["nota"]
