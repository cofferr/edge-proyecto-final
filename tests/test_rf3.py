import json

from conftest import filas
from parcialfinal.config import Rf3
from parcialfinal.nodos.rf3_lora import AdaptadorRf3

# Línea real de lorawan_uplinks.jsonl
REC = json.loads('{"ts": 1795637086.47, "node": "rf3-lora", "devaddr": "01000001", "fcnt": 0, "rssi": -53, '
                 '"snr": 10.0, "confirmed": false, "fport": 1, "payload_hex": "42097418010000", '
                 '"temp_c": 23.7, "hum_pct": 62.6, "mov": 1, "cnt": 0}')


def test_uplink_con_pir_filtra_guarda_y_registra_sospecha(nucleo):
    a = AdaptadorRf3(nucleo, Rf3())
    a.procesar(REC, t_gw=1795637086.50)
    tel = filas(nucleo, "telemetria.csv")
    assert {(f["magnitud"], f["valor"], f["aceptada"]) for f in tel} == {
        ("temperatura", "23.7", "si"), ("humedad_aire", "62.6", "si")}
    up = filas(nucleo, "rf3_uplinks.csv")[0]
    assert up["rssi"] == "-53" and up["snr"] == "10.0" and up["cnt"] == "0"
    assert up["t_ns"] and up["t_gw"]
    ev = filas(nucleo, "eventos.csv")[0]
    assert (ev["tipo"], ev["fuente"]) == ("sospecha", "RF3")


def test_sin_dato_no_cuenta_como_lectura(nucleo):
    a = AdaptadorRf3(nucleo, Rf3())
    a.procesar({**REC, "temp_c": None, "hum_pct": None, "mov": 0}, t_gw=100.0)
    assert not (nucleo.almacen.carpeta / "telemetria.csv").exists()
    assert filas(nucleo, "rf3_uplinks.csv")[0]["temp_c"] == ""


def test_uplink_sin_decodificar_se_ignora(nucleo):
    AdaptadorRf3(nucleo, Rf3()).procesar({"ts": 1, "fcnt": 3, "payload_hex": "00"})
    assert not (nucleo.almacen.carpeta / "rf3_uplinks.csv").exists()


def test_linea_basura_no_lanza(nucleo):
    AdaptadorRf3(nucleo, Rf3())._procesar_linea(b"no es json")
