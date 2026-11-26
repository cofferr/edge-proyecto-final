# Resultados de la toma de datos (RF1 y RF2)

Generado por `scripts/toma_datos.py`. Cada tramo indica qué mide y en qué unidades; las marcas de tiempo son las de recepción en el gateway.

## rf1_ble

*2 min con solo RF1: tramas recibidas, cadencia y rango de cada magnitud*

Unidades: temperatura °C, humedad aire %, humedad suelo mV, cadencia s, r adimensional, ahorro %

| Cifra | Valor |
|---|---|
| duracion_s | 120.3 |
| tramas_recibidas | 58 |
| cadencia_media_s | 2.018 |
| cadencia_mediana_s | 2.01 |
| cadencia_max_s | 2.07 |
| tramas_suelo_sin_dato | 0 |
| tramas_invalidas | 0 |
| magnitudes.temperatura.recibidas | 58 |
| magnitudes.temperatura.aceptadas | 1 |
| magnitudes.temperatura.r | 0.0172 |
| magnitudes.temperatura.valores.n | 58 |
| magnitudes.temperatura.valores.min | 23.0 |
| magnitudes.temperatura.valores.media | 23.2259 |
| magnitudes.temperatura.valores.max | 23.3 |
| magnitudes.humedad_aire.recibidas | 58 |
| magnitudes.humedad_aire.aceptadas | 1 |
| magnitudes.humedad_aire.r | 0.0172 |
| magnitudes.humedad_aire.valores.n | 58 |
| magnitudes.humedad_aire.valores.min | 61.6 |
| magnitudes.humedad_aire.valores.media | 62.1897 |
| magnitudes.humedad_aire.valores.max | 63.3 |
| magnitudes.humedad_suelo_mv.recibidas | 58 |
| magnitudes.humedad_suelo_mv.aceptadas | 1 |
| magnitudes.humedad_suelo_mv.r | 0.0172 |
| magnitudes.humedad_suelo_mv.valores.n | 58 |
| magnitudes.humedad_suelo_mv.valores.min | 2668.0 |
| magnitudes.humedad_suelo_mv.valores.media | 2677.1379 |
| magnitudes.humedad_suelo_mv.valores.max | 2683.0 |
| global.recibidas | 174 |
| global.aceptadas | 3 |
| global.r | 0.0172 |
| global.ahorro_pct | 98.28 |

_Generado: 2026-11-25T21:32:19-05:00_

## filtrado_rf1

*12 min con solo RF1: lecturas recibidas/aceptadas por magnitud, r y ahorro (1 - r) del filtro por umbral*

Unidades: temperatura °C, humedad aire %, humedad suelo mV, cadencia s, r adimensional, ahorro %

| Cifra | Valor |
|---|---|
| duracion_s | 720.3 |
| tramas_recibidas | 356 |
| cadencia_media_s | 2.018 |
| cadencia_mediana_s | 2.01 |
| cadencia_max_s | 2.28 |
| tramas_suelo_sin_dato | 0 |
| tramas_invalidas | 0 |
| magnitudes.temperatura.recibidas | 356 |
| magnitudes.temperatura.aceptadas | 29 |
| magnitudes.temperatura.r | 0.0815 |
| magnitudes.temperatura.valores.n | 356 |
| magnitudes.temperatura.valores.min | 23.3 |
| magnitudes.temperatura.valores.media | 24.0478 |
| magnitudes.temperatura.valores.max | 29.9 |
| magnitudes.humedad_aire.recibidas | 356 |
| magnitudes.humedad_aire.aceptadas | 38 |
| magnitudes.humedad_aire.r | 0.1067 |
| magnitudes.humedad_aire.valores.n | 356 |
| magnitudes.humedad_aire.valores.min | 61.3 |
| magnitudes.humedad_aire.valores.media | 69.9132 |
| magnitudes.humedad_aire.valores.max | 99.9 |
| magnitudes.humedad_suelo_mv.recibidas | 356 |
| magnitudes.humedad_suelo_mv.aceptadas | 17 |
| magnitudes.humedad_suelo_mv.r | 0.0478 |
| magnitudes.humedad_suelo_mv.valores.n | 356 |
| magnitudes.humedad_suelo_mv.valores.min | 2671.0 |
| magnitudes.humedad_suelo_mv.valores.media | 2692.1685 |
| magnitudes.humedad_suelo_mv.valores.max | 3135.0 |
| global.recibidas | 1068 |
| global.aceptadas | 84 |
| global.r | 0.0787 |
| global.ahorro_pct | 92.13 |

_Generado: 2026-11-25T21:45:36-05:00_

## rf2_trigger

*5 disparos con /trigger espaciados 10 s: foto, tiempos por etapa y decisión local de RF2*

Unidades: tiempos de etapa en µs (y ms), foto en bytes, latencia en ms, area_pct en %

| Cifra | Valor |
|---|---|
| eventos | 7 |
| fotos_guardadas | 7 |
| foto_bytes.n | 7 |
| foto_bytes.min | 8038 |
| foto_bytes.media | 8119.7143 |
| foto_bytes.max | 8164 |
| foto_bytes.mediana | 8127 |
| tiempos_us.captura.media | 115344.4 |
| tiempos_us.captura.max | 139929.0 |
| tiempos_us.gris.media | 15380.9 |
| tiempos_us.gris.max | 16026.0 |
| tiempos_us.diferencia.media | 32460.7 |
| tiempos_us.diferencia.max | 33276.0 |
| tiempos_us.morfologia.media | 157223.0 |
| tiempos_us.morfologia.max | 160500.0 |
| tiempos_us.metricas.media | 10318.1 |
| tiempos_us.metricas.max | 10510.0 |
| tiempos_us.jpeg.media | 71303.7 |
| tiempos_us.jpeg.max | 71532.0 |
| tiempos_us.total.media | 215382.7 |
| tiempos_us.total.max | 219055.0 |
| tiempos_ms.captura.media | 115.344 |
| tiempos_ms.captura.max | 139.929 |
| tiempos_ms.gris.media | 15.381 |
| tiempos_ms.gris.max | 16.026 |
| tiempos_ms.diferencia.media | 32.461 |
| tiempos_ms.diferencia.max | 33.276 |
| tiempos_ms.morfologia.media | 157.223 |
| tiempos_ms.morfologia.max | 160.5 |
| tiempos_ms.metricas.media | 10.318 |
| tiempos_ms.metricas.max | 10.51 |
| tiempos_ms.jpeg.media | 71.304 |
| tiempos_ms.jpeg.max | 71.532 |
| tiempos_ms.total.media | 215.383 |
| tiempos_ms.total.max | 219.055 |
| latencia_deteccion_a_foto_ms.n | 7 |
| latencia_deteccion_a_foto_ms.min | 709.468 |
| latencia_deteccion_a_foto_ms.media | 2497.627 |
| latencia_deteccion_a_foto_ms.max | 4556.282 |
| confirmados_por_el_nodo | 0 |

| n | hora | foto_bytes | confirmed | reason | area_pct | captura_us | captura_ms | gris_us | gris_ms | diferencia_us | diferencia_ms | morfologia_us | morfologia_ms | metricas_us | metricas_ms | jpeg_us | jpeg_ms | total_us | total_ms | latencia_deteccion_a_foto_ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 21:57:59.451 | 8095 | False | area_low | 0.0 | 88096.0 | 88.096 | 15036.0 | 15.036 | 33276.0 | 33.276 | 160500.0 | 160.5 | 10243.0 | 10.243 | 71204.0 | 71.204 | 219055.0 | 219.055 | 2467.219 |
| 2 | 21:58:10.314 | 8127 | False | area_low | 0.0 | 91566.0 | 91.566 | 15245.0 | 15.245 | 32773.0 | 32.773 | 154821.0 | 154.821 | 10392.0 | 10.392 | 71199.0 | 71.199 | 213231.0 | 213.231 | 1087.326 |
| 3 | 21:58:22.623 | 8154 | False | area_low | 0.0 | 109933.0 | 109.933 | 16026.0 | 16.026 | 32137.0 | 32.137 | 158112.0 | 158.112 | 10271.0 | 10.271 | 71260.0 | 71.26 | 216546.0 | 216.546 | 3361.279 |
| 4 | 21:58:26.498 | 8038 | False | area_low | 0.0 | 123465.0 | 123.465 | 15667.0 | 15.667 | 32598.0 | 32.598 | 157210.0 | 157.21 | 10279.0 | 10.279 | 71271.0 | 71.271 | 215754.0 | 215.754 | 709.468 |
| 5 | 21:58:33.357 | 8121 | False | area_low | 0.0 | 139929.0 | 139.929 | 15235.0 | 15.235 | 31973.0 | 31.973 | 155894.0 | 155.894 | 10268.0 | 10.268 | 71374.0 | 71.374 | 213370.0 | 213.37 | 2652.225 |
| 6 | 21:58:44.201 | 8164 | False | area_low | 0.0 | 117410.0 | 117.41 | 15275.0 | 15.275 | 31988.0 | 31.988 | 158212.0 | 158.212 | 10264.0 | 10.264 | 71532.0 | 71.532 | 215739.0 | 215.739 | 2649.59 |
| 7 | 21:58:48.331 | 8139 | False | area_low | 0.0 | 137012.0 | 137.012 | 15182.0 | 15.182 | 32480.0 | 32.48 | 155812.0 | 155.812 | 10510.0 | 10.51 | 71286.0 | 71.286 | 213984.0 | 213.984 | 4556.282 |

_Generado: 2026-11-25T21:58:57-05:00_

## rf2_pir

*Eventos reales del PIR de RF2 (hasta 5 o 4 min): foto, tiempos, decisión local y latencia de detección a foto guardada*

Unidades: tiempos de etapa en µs (y ms), foto en bytes, latencia en ms, area_pct en %

| Cifra | Valor |
|---|---|
| eventos | 5 |
| fotos_guardadas | 5 |
| foto_bytes.n | 5 |
| foto_bytes.min | 4946 |
| foto_bytes.media | 7325.2 |
| foto_bytes.max | 8548 |
| foto_bytes.mediana | 7846 |
| tiempos_us.captura.media | 99929.2 |
| tiempos_us.captura.max | 136105.0 |
| tiempos_us.gris.media | 15589.6 |
| tiempos_us.gris.max | 16495.0 |
| tiempos_us.diferencia.media | 33762.4 |
| tiempos_us.diferencia.max | 34765.0 |
| tiempos_us.morfologia.media | 155706.2 |
| tiempos_us.morfologia.max | 158263.0 |
| tiempos_us.metricas.media | 16733.2 |
| tiempos_us.metricas.max | 18593.0 |
| tiempos_us.jpeg.media | 78354.2 |
| tiempos_us.jpeg.max | 80250.0 |
| tiempos_us.total.media | 221791.4 |
| tiempos_us.total.max | 224340.0 |
| tiempos_ms.captura.media | 99.929 |
| tiempos_ms.captura.max | 136.105 |
| tiempos_ms.gris.media | 15.59 |
| tiempos_ms.gris.max | 16.495 |
| tiempos_ms.diferencia.media | 33.762 |
| tiempos_ms.diferencia.max | 34.765 |
| tiempos_ms.morfologia.media | 155.706 |
| tiempos_ms.morfologia.max | 158.263 |
| tiempos_ms.metricas.media | 16.733 |
| tiempos_ms.metricas.max | 18.593 |
| tiempos_ms.jpeg.media | 78.354 |
| tiempos_ms.jpeg.max | 80.25 |
| tiempos_ms.total.media | 221.791 |
| tiempos_ms.total.max | 224.34 |
| latencia_deteccion_a_foto_ms.n | 5 |
| latencia_deteccion_a_foto_ms.min | 263.829 |
| latencia_deteccion_a_foto_ms.media | 3037.101 |
| latencia_deteccion_a_foto_ms.max | 8622.425 |
| confirmados_por_el_nodo | 2 |
| duracion_s | 82.7 |

| n | hora | foto_bytes | confirmed | reason | area_pct | captura_us | captura_ms | gris_us | gris_ms | diferencia_us | diferencia_ms | morfologia_us | morfologia_ms | metricas_us | metricas_ms | jpeg_us | jpeg_ms | total_us | total_ms | latencia_deteccion_a_foto_ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 22:01:44.954 | 8519 | True | ok | 49.68 | 81685.0 | 81.685 | 16495.0 | 16.495 | 33315.0 | 33.315 | 155583.0 | 155.583 | 15778.0 | 15.778 | 78639.0 | 78.639 | 221171.0 | 221.171 | 4359.307 |
| 2 | 22:01:50.809 | 8548 | True | ok | 30.28 | 83811.0 | 83.811 | 16066.0 | 16.066 | 33296.0 | 33.296 | 154885.0 | 154.885 | 13932.0 | 13.932 | 78492.0 | 78.492 | 218179.0 | 218.179 | 1547.072 |
| 3 | 22:02:21.964 | 6767 | False | global_light_change | 72.15 | 121325.0 | 121.325 | 15312.0 | 15.312 | 33730.0 | 33.73 | 158263.0 | 158.263 | 17035.0 | 17.035 | 79234.0 | 79.234 | 224340.0 | 224.34 | 8622.425 |
| 4 | 22:02:38.946 | 4946 | False | global_light_change | 81.99 | 76720.0 | 76.72 | 14814.0 | 14.814 | 33706.0 | 33.706 | 154976.0 | 154.976 | 18593.0 | 18.593 | 75156.0 | 75.156 | 222089.0 | 222.089 | 392.872 |
| 5 | 22:02:49.927 | 7846 | False | global_light_change | 84.52 | 136105.0 | 136.105 | 15261.0 | 15.261 | 34765.0 | 34.765 | 154824.0 | 154.824 | 18328.0 | 18.328 | 80250.0 | 80.25 | 223178.0 | 223.178 | 263.829 |

_Generado: 2026-11-25T22:02:52-05:00_

## calculos

*Calc 3 (ancho de banda) y cifras de RF2 derivadas de los tramos; fuentes: {"rf1": "cadencia y r de filtrado_rf1 (12 min); trama BLE de 7 bytes", "rf2": "fotos de rf2_trigger + rf2_pir"}*

Unidades: bytes por hora, % de ahorro, ms

| Cifra | Valor |
|---|---|
| rf1.cadencia_usada_s | 2.018 |
| rf1.tramas_por_hora | 1783.9 |
| rf1.bytes_por_hora_sin_filtro | 12488 |
| rf1.r_global | 0.0787 |
| rf1.bytes_por_hora_con_filtro | 983 |
| rf1.ahorro_pct | 92.13 |
| rf2.fotos_usadas | 12 |
| rf2.tam_medio_foto_bytes | 7789 |
| rf2.tam_mediano_foto_bytes | 8124.0 |
| rf2.bytes_por_hora_1_foto_por_s | 28039200 |
| rf2.bytes_por_hora_fotos_por_evento.N=0.bytes_por_hora | 0 |
| rf2.bytes_por_hora_fotos_por_evento.N=0.ahorro_vs_1_foto_por_s_pct | 100.0 |
| rf2.bytes_por_hora_fotos_por_evento.N=5.bytes_por_hora | 38943 |
| rf2.bytes_por_hora_fotos_por_evento.N=5.ahorro_vs_1_foto_por_s_pct | 99.861 |
| rf2.bytes_por_hora_fotos_por_evento.N=30.bytes_por_hora | 233660 |
| rf2.bytes_por_hora_fotos_por_evento.N=30.ahorro_vs_1_foto_por_s_pct | 99.167 |
| rf2.tiempo_procesamiento_ms.media | 218.587 |
| rf2.tiempo_procesamiento_ms.max | 224.34 |
| rf2.latencia_deteccion_a_foto_ms.media | 2767.4 |
| rf2.latencia_deteccion_a_foto_ms.max | 8622.425 |

**Avisos:** el filtro actúa en el gateway: la radio BLE ya recibió la trama; el ahorro es de lo que se guarda/reenvía aguas arriba, con r por lectura (3 lecturas por trama)

_Generado: 2026-11-25T22:03:00-05:00_
