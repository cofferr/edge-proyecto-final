# NOTAS de decisiones

Registro de decisiones menores tomadas de forma autónoma (qué y por qué).

## Entorno y repositorio
- **Carpeta**: se trabaja en `~/Edge/ParcialFinal` (ya era repo git con `uv init` y `lorawan_ns.py`), no en `~/Edge/gateway-final`, que no existía; evita duplicar el proyecto.
- **Python 3.14** se mantiene: `gradio 6`, `bleak 3` y `httpx` importan sin problemas.
- **Reutilización del parcial** (`~/Edge/edge-parcial`): su gateway BLE (`ble/gateway.py`) sirvió de patrón (búsqueda por UUID de servicio, reconexión con backoff, bleak importado de forma diferida). El resto es de otro dominio (cámaras, reconocimiento facial, SQL) y se reescribió con lo mínimo.
- **No versionados** (credenciales/claves): `lorawan_ns.py` (AppKey), `ns_state.json` (claves de sesión), `lorawan_uplinks.jsonl`, `data/`. `lorawan_ns.py` no se modifica.

## Lógica
- Frontera de la ventana W del quórum **inclusiva** en confirmación (`<= W`, como pide el enunciado "hace W o menos") y en caducidad de la alerta (activa mientras `t - último <= W`).
- Umbral exacto acepta; comparación con tolerancia 1e-9 para evitar falsos descartes por coma flotante (23.12 − 22.62 = 0.49999…).
- Lecturas "sin dato" (0xFFFF suelo/humedad, 0x7FFF temperatura) **no** cuentan como recibidas: no son una lectura.

## Arquitectura
- Un proceso gateway (hilos: un lector por nodo + `tick`) y un proceso panel aparte. Comunicación: `data/estado.json`, escrito de forma atómica (`os.replace`) por el núcleo cada 1 s y en cada evento. El panel nunca escribe ni arranca nada.
- Un lector que lanza una excepción se reinicia a los 5 s sin afectar a los otros; RF1 reconecta con backoff 1→30 s; RF2 reintenta cada ciclo.
- **RF3**: esquema confirmado leyendo `lorawan_ns.py` (`decode_payload`) y `lorawan_uplinks.jsonl`: `ts, node, devaddr, fcnt, rssi, snr, confirmed, fport, payload_hex, temp_c, hum_pct, mov, cnt`; `None` = sin dato. Se usa UDP; `modo = "archivo"` sigue el JSONL desde el final. Pérdidas = huecos en `cnt` (módulo 65536; un salto atrás = reinicio del nodo, no cuenta).
- **RF2**: un aumento de `events` mayor que 1 entre sondeos (se perdió alguno) cuenta como **un** evento y una foto (solo hay "última foto"). Primer sondeo y reinicio del nodo (`events` baja) solo fijan la línea base. La marca del evento es la de recepción de `/status`, antes de descargar la foto. Si la foto falla, el evento se registra igual con ruta vacía.
- **Estado en línea**: sin datos más de 10 s (RF1), 5 s (RF2, cuenta cualquier `/status` correcto), 150 s (RF3); configurable.
- **Tiempo de procesamiento** de eventos.csv = recepción → fila escrita (ms). Para RF3, `rf3_uplinks.csv` guarda `t_ns` (marca del servidor de red) y `t_gw` (entrada al gateway); ambas del mismo reloj del Mac.
- RF1 envía `movimiento` siempre 0: se ignora; RF1 no es fuente de quórum.
- `eventos.csv` también incluye filas `fin_alerta` (útiles para el panel); `metricas.py` solo cuenta `sospecha` y `alerta`. Cada evento durante una alerta ya activa cuenta como `alerta` solo si la otra fuente está dentro de W; si no, queda como `sospecha` aunque la alerta siga activa (la alerta se extiende igualmente).
- El simulador usa un ciclo fijo de 90 s; RF1 simulado se inyecta en `LectorBle.al_recibir` (sin Bluetooth); RF3 simulado pasa por UDP real.

## Verificado
- `uv run pytest`: 37 pruebas pasan. Prueba de punta a punta en modo simulado: gateway + panel arrancados, sospecha → alerta por quórum, fotos y CSV generados, panel responde y renderiza (vía gradio_client). No se miró el aspecto visual en un navegador.

## Checklist con hardware real (pendiente)
- [ ] macOS concede Bluetooth a la terminal; RF1 se encuentra por nombre/UUID y llegan tramas cada 2 s; suelo en mV razonable, 0xFFFF no genera lecturas.
- [ ] Apagar/alejar RF1: panel pasa a FUERA DE LÍNEA a los 10 s y el gateway reconecta solo al volver.
- [ ] `http://nodocam.local` resuelve desde el Mac; si no, configurar `ip_respaldo`. Revisar `/status` real: ¿los campos coinciden con los esperados (`events`, `last.*`)?
- [ ] `/trigger` en RF2 → sube `events`, aparece foto JPEG 320x240 válida en `data/fotos/` y en el panel, con decisión local.
- [ ] Un evento RF2 descartado por el nodo también guarda foto.
- [ ] `lorawan_ns.py` en marcha: llegan uplinks por UDP 9001 al gateway (¿puerto ocupado si otro proceso escucha?); RSSI/SNR y `cnt` correctos en `rf3_uplinks.csv`.
- [ ] Uplink con `mov=1` genera evento RF3; PIR en RF2 y RF3 con menos de 30 s de diferencia → alerta; con más → dos sospechas; la alerta se apaga 30 s después del último evento.
- [ ] Un nodo apagado no afecta a los demás ni al panel.
- [ ] Comprobar umbrales con datos reales (0,5 °C / 2 % / 50 mV) mirando `r` en `scripts/metricas.py`.
- [ ] Verificar visualmente el panel en el navegador.

## Toma de datos RF1 y RF2 (2026-11-25)
Script `scripts/toma_datos.py`; resultados en `resultados/` (copia de `~/Edge/InformeFinal/datos/`). RF3 y quórum quedan para otra tanda (necesitan ambos nodos).
- **mDNS lento**: desde Python en macOS `nodocam.local` tarda ~5 s por petición (resuelve, pero tarde), así que el cliente nunca cae a `ip_respaldo` y cada `/status` y `/photo` pagaba ~5 s. La toma se hizo con la IP como `url` en `config.local.toml` (ignorado por git). Pendiente de decidir: resolver una vez y reutilizar la IP en `ClienteCam`.
- **rf2_trigger**: se conserva la 3.ª toma (PIR reubicado, nodo recalibrado). El nodo contó 7 eventos para 5 `/trigger`; causa probable: reintento de mi script tras timeout (ya corregido, 1 intento por disparo), no comprobada. Decisión local `area_low` (escena quieta, esperable).
- **rf2_pir**: eventos 1 y 2 separados solo 5,9 s (se pedía >10 s). Eventos 3-5 descartados por el nodo como `global_light_change` (área 72-85 %), probablemente la mano muy cerca del objetivo.
- **Latencia detección→foto** (0,3–8,6 s) irregular: depende de la descarga de `/photo` (el nodo la sirve lento mientras procesa). No es del filtrado ni del quórum.

## Prueba de quórum con hardware (2026-11-26): primera toma, no concluyente
Los tres escenarios salieron "no coincide" (ver `resultados/quorum_resultados.md`). Causa probable (indicada por quien hizo la prueba): ambos nodos estaban en el mismo escritorio; el PIR de RF2 se disparó por el movimiento de su cable (todo el circuito se movió) y RF3 por el codo en su campo de visión. No es un fallo del quórum: la alerta se declaró correctamente cuando RF2 y RF3 dispararon con menos de W = 30 s de diferencia.
- **Válido**: detección de nodo caído (RF3 marcado fuera de línea a 150,3 s de su último dato, timeout configurado 150 s); declaración de alerta (~0,8 ms con RF3, 0,2–5,7 s con RF2 por la descarga de la foto previa al quórum).
- **A repetir con el protocolo corregido**: cable de RF2 fijo, nodos separados, PIR del otro nodo tapado en sospecha, salir del campo de visión tras el segundo movimiento, y en nodo caído esperar ~40 s tras apagar RF3.
- **Hallazgo**: el gateway no emite aviso aparte cuando un nodo cae; solo el estado "fuera de línea" en `estado.json` y en el panel.

## Prueba de integración RF1+RF2+RF3 (2026-11-26, 10 min, hardware real)
`resultados/integracion_resultados.md`; capturas `figuras/gateway/panel_integracion_*.png`.
- RF1: 298 tramas, cadencia 2,014 s, sin huecos, 1 conexión BLE, 0 caídas. RF3: 12 uplinks (10 esperados; 2 extra por PIR), 0 perdidos, RSSI medio −57 dBm. RF2: 7 eventos con foto (7/7 descargadas).
- Gateway: CPU media 0,62 % (máx 0,9 %) de un núcleo, RSS máx 68 MB (psutil, 118 muestras).
- Quórum: 9 alertas y 4 sospechas; fin de alerta a 30,6 s del último evento en las dos alertas (W = 30 s + resolución del tick de 1 s). Alerta declarada en <1 ms con RF3 y de 0,3 a 3,3 s con RF2 (descarga de foto previa al quórum).
- RF2: 7 "caídas" a fuera de línea (15,1 s en total), una por evento PIR: probable efecto del umbral de 5 s mientras el sondeo está ocupado descargando la foto, no del nodo (no verificado). 1 fallo de sondeo.
- Los uplinks periódicos de RF3 llevan `mov=1` si el PIR está en alto en ese instante: generan sospechas tras un movimiento (00:50:59, 00:54:59).
