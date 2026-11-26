# Resultados de la prueba de integración

Cada sección indica qué mide y en qué unidades; marcas de tiempo = recepción en el gateway.

## integracion

*RF1, RF2 y RF3 activos a la vez: tramas/eventos por nodo, pérdidas, caídas, CPU del gateway y tiempos de quórum*

Unidades: duración s; cadencias s; pérdidas %; procesamiento y alerta_declarada en ms; CPU % de un núcleo; RSS MB

| Cifra | Valor |
|---|---|
| duracion_s | 600.1 |
| rf1.tramas_recibidas | 298 |
| rf1.cadencia_media_s | 2.014 |
| rf1.huecos_mayores_6s | 0 |
| rf1.hueco_max_s | 2.07 |
| rf1.tramas_perdidas_estimadas | 0 |
| rf1.conexiones_ble | 1 |
| rf1.sesiones_terminadas | 0 |
| rf1.caidas | 0 |
| rf1.tiempo_fuera_de_linea_s | 0.0 |
| rf2.eventos_pir | 7 |
| rf2.fotos_sin_descargar | 0 |
| rf2.fallos_de_sondeo | 1 |
| rf2.reinicios_detectados | 0 |
| rf2.caidas | 7 |
| rf2.tiempo_fuera_de_linea_s | 15.1 |
| rf3.uplinks_recibidos | 12 |
| rf3.uplinks_esperados | 10 |
| rf3.perdida_por_tiempo_pct | 0.0 |
| rf3.paquetes_perdidos_por_contador | 0 |
| rf3.eventos_pir_mov1 | 6 |
| rf3.rssi_medio_dbm | -57.167 |
| rf3.caidas | 0 |
| rf3.tiempo_fuera_de_linea_s | 0.0 |
| quorum.sospechas | 4 |
| quorum.alertas | 9 |
| quorum.fines_de_alerta | 2 |
| quorum.procesamiento_evento_ms.n | 13 |
| quorum.procesamiento_evento_ms.media | 915.482 |
| quorum.procesamiento_evento_ms.min | 0.231 |
| quorum.procesamiento_evento_ms.max | 3313.323 |
| quorum.procesamiento_evento_ms.desv | 1336.705 |
| quorum.alerta_declarada_ms.n | 9 |
| quorum.alerta_declarada_ms.media | 966.217 |
| quorum.alerta_declarada_ms.min | 0.508 |
| quorum.alerta_declarada_ms.max | 3313.323 |
| quorum.alerta_declarada_ms.desv | 1307.254 |
| cpu_gateway.medible | True |
| cpu_gateway.muestras | 118 |
| cpu_gateway.cpu_media_pct | 0.62 |
| cpu_gateway.cpu_max_pct | 0.9 |
| cpu_gateway.rss_max_mb | 68.2 |

**Avisos:** RF3: 12 uplinks > 10 esperados: hay envíos extra (probables eventos PIR); la pérdida por tiempo se acota a 0; RF2: 7 caída(s) a fuera de línea, 15.1 s en total

_Generado: 2026-11-26T00:55:58-05:00_
