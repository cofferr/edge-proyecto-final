# Resultados de la prueba de quórum (RF2 + RF3)

Cada sección indica qué mide y en qué unidades; marcas de tiempo = recepción en el gateway.

## sospecha

*Un solo PIR activo (RF3 y luego RF2, en ventanas separadas): el gateway debe registrar sospecha y no alerta*

Unidades: horas locales de recepción en el gateway

| Cifra | Valor |
|---|---|
| esperado | sospecha, sin alerta |
| coincide | no |
| capturas | panel_sospecha.png |

| parte | resultado | coincide | eventos | nota |
|---|---|---|---|---|
| solo RF3 | alerta | no | 00:27:42.575 RF3 sospecha; 00:27:56.996 RF2 alerta | se activó también la otra fuente (movimiento no aislado) |
| solo RF2 | alerta | no | 00:28:57.114 RF2 alerta; 00:29:07.988 RF2 alerta; 00:29:22.597 RF2 sospecha | se activó también la otra fuente (movimiento no aislado) |

**Avisos:** solo RF3: se activó también la otra fuente (movimiento no aislado); solo RF2: se activó también la otra fuente (movimiento no aislado)

_Generado: 2026-11-26T00:34:14-05:00_

## alerta

*RF2 y RF3 dentro de W: el gateway debe declarar la alerta; se mide el tiempo hasta declararla (desde que el gateway recibe el segundo PIR) y hasta apagarla (desde el último evento)*

Unidades: declaracion_alerta_ms en ms; apagado_s y separacion_pirs_s en s; horas locales

| Cifra | Valor |
|---|---|
| esperado | alerta y apagado a W s del último evento |
| coincide | no |
| W_s | 30 |
| capturas | panel_alerta.png |
| primer_pir |  |
| segundo_pir | RF3 00:30:19.140 |
| separacion_pirs_s | None |
| declaracion_alerta_ms | 0.796 |
| apagado_s | None |

| evento |
|---|
| 00:30:19.140 RF3 alerta |
| 00:30:25.476 RF2 alerta |
| 00:30:39.427 RF2 alerta |
| 00:30:42.601 RF3 alerta |
| 00:30:53.143 RF2 alerta |
| 00:31:04.156 RF2 alerta |

**Avisos:** la alerta no se apagó durante la observación (¿siguieron los movimientos?)

_Generado: 2026-11-26T00:34:14-05:00_

## nodo_caido

*Con RF3 apagado, evento de RF2: el gateway debe dar sospecha (no alerta) y marcar RF3 fuera de línea; se mide el tiempo hasta detectar la caída desde el último dato de RF3*

Unidades: tiempos en s; horas locales; timeout configurado en s

| Cifra | Valor |
|---|---|
| timeout_configurado_s | 150 |
| ultimo_dato_nodo_caido | 00:31:42.614 |
| fuera_de_linea_a_las | 00:34:12.906 |
| tiempo_hasta_detectar_caida_s | 150.29 |
| esperado | sospecha de RF2 sin alerta; RF3 pasa a fuera de línea |
| resultado | alerta |
| coincide | no |
| capturas | panel_nodo_caido.png |

| evento |
|---|
| 00:32:04.931 RF2 alerta |
| 00:32:16.125 RF2 sospecha |

**Avisos:** hubo alerta con un nodo caído (inesperado); el gateway no emite un aviso aparte: la caída solo se ve como estado 'fuera de línea' en estado.json y en el panel

_Generado: 2026-11-26T00:34:14-05:00_
