from datetime import datetime, timedelta

from parcialfinal.metricas import calcular, formatear, paquetes_perdidos


def test_paquetes_perdidos():
    assert paquetes_perdidos([1, 2, 3]) == 0
    assert paquetes_perdidos([1, 2, 5, 6]) == 2
    assert paquetes_perdidos([65534, 65535, 0, 1]) == 0   # rollover de 16 bits
    assert paquetes_perdidos([65534, 1]) == 2             # 65535 y 0 perdidos
    assert paquetes_perdidos([10, 11, 0, 1]) == 0         # reinicio del nodo: no es pérdida


def test_calcular_sobre_datos_reales_del_nucleo(nucleo):
    from parcialfinal.config import Rf3
    from parcialfinal.nodos.rf3_lora import AdaptadorRf3
    a = AdaptadorRf3(nucleo, Rf3())
    ahora = datetime.now().timestamp()
    for i, cnt in enumerate([0, 1, 4]):  # se perdieron 2 y 3
        a.procesar({"ts": ahora + i, "fcnt": cnt, "cnt": cnt, "rssi": -50 - i, "snr": 9.0,
                    "temp_c": 20.0, "hum_pct": 50.0, "mov": 0}, t_gw=ahora + i)
    nucleo.evento_pir("RF2", ahora)
    nucleo.evento_pir("RF3", ahora + 5)
    m = calcular(nucleo.almacen.carpeta, datetime.now().astimezone() - timedelta(hours=1),
                 datetime.now().astimezone() + timedelta(hours=1))
    assert m["telemetria"]["RF3"]["recibidas"] == 6 and m["telemetria"]["RF3"]["aceptadas"] == 2
    assert m["rf3"]["paquetes_perdidos"] == 2 and m["rf3"]["rssi_medio"] == -51
    assert (m["sospechas"], m["alertas"]) == (1, 1)
    assert "r=0.333" in formatear(m)
