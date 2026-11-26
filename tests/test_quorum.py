from parcialfinal.quorum import ALERTA, SOSPECHA, Quorum


def q(w=30):
    return Quorum(w)


def test_un_solo_pir_es_sospecha():
    assert q().evento("RF2", 0) == SOSPECHA


def test_mismo_pir_repetido_no_confirma():
    x = q()
    x.evento("RF2", 0)
    assert x.evento("RF2", 5) == SOSPECHA
    assert not x.activa


def test_dos_pir_dentro_de_la_ventana_confirman():
    x = q()
    x.evento("RF2", 0)
    assert x.evento("RF3", 10) == ALERTA
    assert x.activa


def test_dos_pir_en_el_limite_exacto_confirman():
    x = q()
    x.evento("RF3", 0)
    assert x.evento("RF2", 30) == ALERTA


def test_dos_pir_fuera_de_la_ventana_son_dos_sospechas():
    x = q()
    assert x.evento("RF2", 0) == SOSPECHA
    assert x.evento("RF3", 30.01) == SOSPECHA
    assert not x.activa


def test_orden_inverso_tambien_confirma():
    x = q()
    x.evento("RF3", 0)
    assert x.evento("RF2", 5) == ALERTA


def test_alerta_se_mantiene_con_eventos_de_una_fuente():
    x = q()
    x.evento("RF2", 0)
    x.evento("RF3", 10)
    x.evento("RF2", 35)      # sigue activa, extiende la ventana
    assert not x.actualizar(60)   # 60 - 35 = 25 <= 30
    assert x.activa


def test_alerta_se_desactiva_tras_w_sin_eventos():
    x = q()
    x.evento("RF2", 0)
    x.evento("RF3", 10)
    assert not x.actualizar(40)   # 40 - 10 = 30 (inclusivo): aún activa
    assert x.actualizar(40.01)    # primera llamada tras caducar devuelve True
    assert not x.activa
    assert not x.actualizar(100)  # ya apagada


def test_evento_tardio_tras_caducar_no_hereda_la_alerta():
    x = q()
    x.evento("RF2", 0)
    x.evento("RF3", 10)
    assert x.evento("RF2", 100) == SOSPECHA
    assert not x.activa
