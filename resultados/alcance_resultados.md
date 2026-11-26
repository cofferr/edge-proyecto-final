# Resultados de la prueba de alcance de RF3

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
