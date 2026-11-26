from conftest import filas
from parcialfinal.config import Almacen, Config
from parcialfinal.nucleo import Nucleo


def test_filtrado_antes_de_historial_con_contadores(nucleo):
    assert nucleo.lectura("RF1", "temperatura", 20.0, 0)
    assert not nucleo.lectura("RF1", "temperatura", 20.2, 1)
    assert [f["aceptada"] for f in filas(nucleo, "telemetria.csv")] == ["si", "no"]
    assert nucleo.estado()["filtros"]["RF1/temperatura"] == {"recibidas": 2, "aceptadas": 1}


def test_alerta_por_quorum_y_fin(tmp_path):
    reloj = [1000.0]
    n = Nucleo(Config(almacen=Almacen(carpeta=str(tmp_path))), reloj=lambda: reloj[0])
    assert n.evento_pir("RF2", 1000.0) == "sospecha"
    reloj[0] = 1010.0
    assert n.evento_pir("RF3", 1010.0) == "alerta"
    assert n.estado()["alerta_activa"]
    reloj[0] = 1041.0
    n.tick()
    assert not n.estado()["alerta_activa"]
    assert [f["tipo"] for f in filas(n, "eventos.csv")] == ["sospecha", "alerta", "fin_alerta"]
    assert (tmp_path / "estado.json").exists()


def test_nodo_fuera_de_linea_por_tiempo(tmp_path):
    reloj = [0.0]
    n = Nucleo(Config(almacen=Almacen(carpeta=str(tmp_path))), reloj=lambda: reloj[0])
    n.actualizar_nodo("RF1", 0.0)
    assert n.estado()["nodos"]["RF1"]["en_linea"]
    reloj[0] = 11.0  # timeout RF1 = 10 s
    assert not n.estado()["nodos"]["RF1"]["en_linea"]
    assert not n.estado()["nodos"]["RF2"]["en_linea"]


def test_panel_renderiza_estado(nucleo):
    from parcialfinal.panel import banner, tarjeta
    nucleo.lectura("RF1", "humedad_suelo_mv", 1200.0)
    nucleo.actualizar_nodo("RF1", nucleo.reloj())
    nucleo.evento_pir("RF2", nucleo.reloj())
    nucleo.evento_pir("RF3", nucleo.reloj())
    e = nucleo.estado()
    assert "1200 mV" in tarjeta("RF1", e["nodos"]["RF1"], e["t_estado"])
    assert "ALERTA ACTIVA" in banner(e, e["t_estado"])
    assert "sin publicar" in banner(e, e["t_estado"] + 60)
