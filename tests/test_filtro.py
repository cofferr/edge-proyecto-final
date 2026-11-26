from parcialfinal.filtro import BancoFiltros, FiltroUmbral


def nuevo(u=0.5, lat=300):
    return FiltroUmbral(umbral=u, latido_s=lat)


def test_primera_lectura_se_acepta():
    assert nuevo().evaluar(20.0, 0)


def test_debajo_del_umbral_se_descarta():
    f = nuevo()
    f.evaluar(20.0, 0)
    assert not f.evaluar(20.49, 1)


def test_umbral_exacto_se_acepta():
    f = nuevo()
    f.evaluar(20.0, 0)
    assert f.evaluar(20.5, 1)


def test_umbral_exacto_con_coma_flotante():
    f = nuevo()
    f.evaluar(22.62, 0)
    assert f.evaluar(23.12, 1)  # 23.12 - 22.62 = 0.49999999999999645 en float


def test_umbral_en_sentido_negativo():
    f = nuevo()
    f.evaluar(20.0, 0)
    assert f.evaluar(19.5, 1)


def test_referencia_es_la_ultima_aceptada_no_la_ultima_recibida():
    f = nuevo()
    f.evaluar(20.0, 0)
    assert not f.evaluar(20.3, 1)  # descartada: la referencia sigue en 20.0
    assert f.evaluar(20.5, 2)      # 0.5 respecto a 20.0


def test_latido_acepta_sin_cambio():
    f = nuevo(lat=300)
    f.evaluar(20.0, 0)
    assert not f.evaluar(20.0, 299.9)
    assert f.evaluar(20.0, 300)  # T_lat exacto acepta


def test_latido_se_cuenta_desde_la_ultima_aceptada():
    f = nuevo(lat=300)
    f.evaluar(20.0, 0)
    f.evaluar(21.0, 200)  # aceptada por umbral: reinicia el latido
    assert not f.evaluar(21.0, 450)
    assert f.evaluar(21.0, 500)


def test_contadores():
    f = nuevo()
    for v, t in [(20, 0), (20.1, 1), (20.2, 2), (21, 3)]:
        f.evaluar(v, t)
    assert (f.recibidas, f.aceptadas) == (4, 2)
    assert f.fraccion == 0.5


def test_banco_separa_nodos_y_magnitudes():
    b = BancoFiltros({"temperatura": 0.5, "humedad_aire": 2.0}, 300)
    assert b.evaluar("RF1", "temperatura", 20, 0)
    assert b.evaluar("RF3", "temperatura", 20, 0)       # otro nodo: sin referencia
    assert b.evaluar("RF1", "humedad_aire", 50, 0)      # otra magnitud
    assert not b.evaluar("RF1", "humedad_aire", 51, 1)  # U = 2 %
    assert b.estadisticas()["RF1/humedad_aire"] == {"recibidas": 2, "aceptadas": 1}
