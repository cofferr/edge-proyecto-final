import struct

import pytest

from parcialfinal.config import Rf1
from parcialfinal.nodos.rf1_ble import LectorBle, decodificar


def test_decodifica_trama():
    d = struct.pack("<hHHB", -150, 5540, 1234, 0)
    assert decodificar(d) == {"temperatura": -1.5, "humedad_aire": 55.4, "humedad_suelo_mv": 1234.0}


def test_suelo_sin_dato():
    assert "humedad_suelo_mv" not in decodificar(struct.pack("<hHHB", 2000, 5000, 0xFFFF, 0))


def test_longitud_invalida():
    with pytest.raises(ValueError):
        decodificar(b"\x00" * 6)


def test_al_recibir_escribe_telemetria_y_marca_nodo(nucleo):
    LectorBle(nucleo, Rf1()).al_recibir(struct.pack("<hHHB", 2312, 5540, 900, 0))
    e = nucleo.estado()["nodos"]["RF1"]
    assert e["lecturas"]["humedad_suelo_mv"] == 900.0 and e["en_linea"]
