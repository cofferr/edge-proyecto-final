from conftest import filas
from parcialfinal.config import Rf2
from parcialfinal.nodos.rf2_http import LectorCam


class Falso:
    def __init__(self):
        self.events, self.confirmed, self.foto_ok = 0, False, True

    def status(self):
        return {"pir": 0, "warming_up": False, "background_ready": True, "events": self.events,
                "confirmed": 0, "discarded": 0,
                "last": {"confirmed": self.confirmed, "reason": "area_ok", "area_pct": 3.2,
                         "t_capture_us": 100, "t_proc_us": 500, "photo_bytes": 4000}}

    def foto(self):
        if not self.foto_ok:
            raise OSError("sin foto")
        return b"\xff\xd8jpeg\xff\xd9"


def test_primer_sondeo_fija_linea_base_sin_evento(nucleo):
    c = Falso()
    c.events = 7
    LectorCam(nucleo, c, Rf2()).sondear()
    assert not (nucleo.almacen.carpeta / "eventos.csv").exists()


def test_aumento_de_events_descarga_foto_y_registra(nucleo):
    c = Falso()
    l = LectorCam(nucleo, c, Rf2())
    l.sondear()
    c.events = 1
    l.sondear()
    ev = filas(nucleo, "eventos.csv")[0]
    assert ev["fuente"] == "RF2" and ev["tipo"] == "sospecha"
    assert ev["decision_local_rf2"] == "descartada:area_ok" and ev["tam_foto_bytes"] == "8"
    assert open(ev["ruta_foto"], "rb").read().startswith(b"\xff\xd8")
    assert filas(nucleo, "rf2_fotos.csv")[0]["t_proc_us"] == "500"
    l.sondear()  # sin cambio: no hay evento nuevo
    assert len(filas(nucleo, "eventos.csv")) == 1


def test_evento_cuenta_aunque_falle_la_foto(nucleo):
    c = Falso()
    l = LectorCam(nucleo, c, Rf2())
    l.sondear()
    c.events, c.foto_ok = 1, False
    l.sondear()
    assert filas(nucleo, "eventos.csv")[0]["ruta_foto"] == ""


def test_reinicio_del_nodo_no_es_evento(nucleo):
    c = Falso()
    c.events = 5
    l = LectorCam(nucleo, c, Rf2())
    l.sondear()
    c.events = 0
    l.sondear()
    assert not (nucleo.almacen.carpeta / "eventos.csv").exists()
