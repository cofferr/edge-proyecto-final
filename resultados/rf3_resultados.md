# Resultados de RF3 (LoRaWAN)

Cada sección indica qué mide y en qué unidades; marcas de tiempo = recepción en el gateway.

## alcance

*Alcance LoRaWAN de RF3: uplinks recibidos frente a esperados, pérdida y RSSI/SNR por distancia*

Unidades: distancia m; pérdida % (por tiempo y período); rssi dBm; snr dB


| distancia_m | estado | duracion_s | recibidos | esperados | perdida_pct | perdidos_contador | rssi_media | rssi_min | rssi_max | snr_media | snr_min | snr_max |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 5.0 | completa | 180.0 | 3 | 3 | 0.0 | 0 | -95.0 | -97.0 | -94.0 | 8.433 | 7.8 | 9.0 |
| 10.0 | completa | 180.0 | 3 | 3 | 0.0 | 0 | -93.667 | -94.0 | -93.0 | 8.867 | 8.8 | 9.0 |
| 20.0 | completa | 180.0 | 1 | 3 | 66.67 | 0 | -99.0 | -99.0 | -99.0 | 6.5 | 6.5 | 6.5 |

**Avisos:** 20.0 m: pérdida por tiempo 66.67 % (1 de 3); el contador solo detecta huecos entre uplinks recibidos, no los perdidos al final de la ventana

_Generado: 2026-11-25T23:46:15-05:00_

## rf3_enlace

*Enlace LoRaWAN de RF3: pérdida, RSSI/SNR, tiempos, filtro del gateway y ancho de banda*

Unidades: pérdida %, rssi dBm, snr dB, latencias ms, bytes por hora, r adimensional, ahorro %

| Cifra | Valor |
|---|---|
| duracion_s | 300.5 |
| periodo_nominal_s | 60.0 |
| uplinks_recibidos | 5 |
| uplinks_esperados | 5 |
| perdida_por_tiempo_pct | 0.0 |
| paquetes_perdidos_por_contador | 0 |
| perdida_por_contador_pct | 0.0 |
| cadencia_mediana_s | 59.806 |
| rssi_dbm.n | 5 |
| rssi_dbm.media | -92.6 |
| rssi_dbm.min | -94.0 |
| rssi_dbm.max | -90.0 |
| rssi_dbm.desv | 1.517 |
| snr_db.n | 5 |
| snr_db.media | 8.92 |
| snr_db.min | 8.5 |
| snr_db.max | 9.5 |
| snr_db.desv | 0.37 |
| latencia_servidor_red_a_gateway_ms.n | 5 |
| latencia_servidor_red_a_gateway_ms.media | 2.2 |
| latencia_servidor_red_a_gateway_ms.min | 1.0 |
| latencia_servidor_red_a_gateway_ms.max | 3.0 |
| latencia_servidor_red_a_gateway_ms.desv | 0.837 |
| eventos_pir_mov1 | 0 |
| filtro_gateway.magnitudes.temperatura.recibidas | 5 |
| filtro_gateway.magnitudes.temperatura.aceptadas | 1 |
| filtro_gateway.magnitudes.temperatura.r | 0.2 |
| filtro_gateway.magnitudes.humedad_aire.recibidas | 5 |
| filtro_gateway.magnitudes.humedad_aire.aceptadas | 1 |
| filtro_gateway.magnitudes.humedad_aire.r | 0.2 |
| filtro_gateway.recibidas | 10 |
| filtro_gateway.aceptadas | 2 |
| filtro_gateway.r | 0.2 |
| ancho_de_banda.uplinks_por_hora | 60.2 |
| ancho_de_banda.bytes_por_hora_sin_filtro_payload | 421 |
| ancho_de_banda.bytes_por_hora_con_filtro_payload | 84 |
| ancho_de_banda.bytes_por_hora_aire_lorawan | 1204 |
| ancho_de_banda.ahorro_pct | 80.0 |
| latencia_extremo_a_extremo.medible | False |
| latencia_extremo_a_extremo.motivo | el payload de RF3 (temp, hum, mov, cnt) no lleva marca de tiempo del nodo y el servidor de red no registra la hora de recepción en el receptor (ts se genera al validar el uplink). |
| latencia_extremo_a_extremo.aproximacion | latencia ≈ tiempo en el aire del nodo (ToA, que el firmware imprime por serie; ~57 ms teóricos para SF7/BW125 con 20 B) + receptor→servidor de red por USB (no medido) + servidor de red→gateway (t_gw − t_ns, medido). Contrastar con cronómetro/vídeo moviendo la mano frente al PIR de RF3 y viendo la alerta en el panel. |
| servidor_red_procesamiento_ms_sintetico.n | 200 |
| servidor_red_procesamiento_ms_sintetico.media | 0.179 |
| servidor_red_procesamiento_ms_sintetico.min | 0.148 |
| servidor_red_procesamiento_ms_sintetico.max | 0.443 |
| servidor_red_procesamiento_ms_sintetico.desv | 0.038 |
| servidor_red_procesamiento_ms_sintetico.mediana | 0.172 |
| servidor_red_procesamiento_ms_sintetico.n_tramas_sinteticas | 200 |

_Generado: 2026-11-25T23:30:24-05:00_

## rf3_pir

*Eventos PIR de RF3 (uplink con mov=1) en la ventana, con el uplink asociado*

Unidades: hora local de recepción en el gateway; rssi dBm; snr dB

| Cifra | Valor |
|---|---|
| duracion_s | 60.4 |
| eventos_pir | 2 |

| hora | tipo_quorum | fcnt | cnt | rssi | snr |
|---|---|---|---|---|---|
| 23:39:56.987 | sospecha | 22 | 22 | -90 | 9.5 |
| 23:40:20.039 | sospecha | 23 | 23 | -96 | 8.8 |

_Generado: 2026-11-25T23:40:56-05:00_
