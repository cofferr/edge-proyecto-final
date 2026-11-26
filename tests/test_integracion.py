from datetime import datetime

from parcialfinal import integracion as ig


def test_transiciones_cuenta_caidas_y_tiempo_fuera():
    m = [(0, True), (1, True), (2, False), (3, False), (5, True), (6, False), (8, False)]
    r = ig.transiciones(m)
    assert r["caidas"] == 2 and r["tiempo_fuera_de_linea_s"] == 5.0  # 2→5 y 6→8


def test_transiciones_sin_caidas():
    assert ig.transiciones([(0, True), (1, True)]) == {"caidas": 0, "tiempo_fuera_de_linea_s": 0.0}
    assert ig.transiciones([]) == {"caidas": 0, "tiempo_fuera_de_linea_s": 0.0}


def test_cpu():
    assert ig.estadisticas_cpu([]) == {"medible": False}
    r = ig.estadisticas_cpu([(2.0, 80.0), (6.0, 120.0)])
    assert r["cpu_media_pct"] == 4.0 and r["cpu_max_pct"] == 6.0 and r["rss_max_mb"] == 120.0


def test_contar_log():
    assert ig.contar_log("a RF1 conectado x\nb\nRF1 conectado", "RF1 conectado") == 2


def test_analizar_con_datos_del_nucleo(nucleo):
    from parcialfinal.config import Rf3
    from parcialfinal.nodos.rf3_lora import AdaptadorRf3
    t0 = datetime.now().timestamp()
    for i in range(3):  # RF1: tramas cada 2 s, con un hueco de 10 s
        for t in (t0 + i * 2 if i < 2 else t0 + 14,):
            nucleo.lectura("RF1", "temperatura", 20.0, t)
    a = AdaptadorRf3(nucleo, Rf3())
    for i, c in enumerate([0, 1, 3]):  # falta el cnt 2
        a.procesar({"ts": t0 + i * 10, "fcnt": c, "cnt": c, "rssi": -60, "snr": 9.0, "temp_c": 20.0,
                    "hum_pct": 50.0, "mov": 1 if i == 1 else 0}, t_gw=t0 + i * 10)
    nucleo.evento_pir("RF2", t0 + 11)  # RF3 tuvo PIR en t0+10 → alerta
    r = ig.analizar(nucleo.almacen.carpeta, t0 - 1, t0 + 30, 10, "RF2 sin respuesta\n", {"RF1": [(0, True), (1, False)]}, [])
    s = r["resumen"]
    assert s["rf1"]["tramas_recibidas"] == 3 and s["rf1"]["huecos_mayores_6s"] == 1
    assert s["rf1"]["caidas"] == 1 and s["rf2"]["fallos_de_sondeo"] == 1
    assert s["rf3"]["paquetes_perdidos_por_contador"] == 1
    assert s["quorum"]["sospechas"] == 1 and s["quorum"]["alertas"] == 1  # RF3 sospecha + RF2 alerta
    assert not s["cpu_gateway"]["medible"]
    assert any("RF1: 1 caída" in x for x in r["avisos"])
