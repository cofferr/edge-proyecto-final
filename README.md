# Gateway Fog (RF4) y panel (RF5)

Proyecto final de Edge Computing. El gateway lee tres nodos (RF1 BLE, RF2 ESP32-CAM por HTTP, RF3 LoRaWAN vía `lorawan_ns.py`), filtra por umbral, decide la alerta por quórum de PIR (RF2 + RF3) y guarda CSV. El panel (Gradio) solo lee el estado que publica el gateway.

Requisitos: [uv](https://docs.astral.sh/uv/). `uv sync` instala todo (Python 3.14).

Todos los umbrales, la ventana W y las direcciones de los nodos están en `config.toml`.

## Estructura del repositorio

```
firmware/rf1_ble/         sketch del nodo RF1 (BLE, EstacionESP32)
firmware/rf2_camara/      sketch del nodo RF2 (ESP32-CAM, HTTP)
firmware/rf3_lorawan/     sketch del nodo RF3 (LoRaWAN, OTAA)
firmware/receptor_lora/   sketch del receptor LoRa (ESP32 conectado por USB al Mac)
src/parcialfinal/         gateway (núcleo, nodos, simulador) y panel
scripts/                  scripts del informe (metricas.py)
lorawan_ns.py             servidor de red LoRaWAN (usa el receptor por USB)
```

**Arduino IDE**: abrir el `.ino` de cada carpeta (Archivo → Abrir); el nombre de la carpeta coincide con el del sketch, como exige el IDE. Elegir la placa y el puerto de cada ESP32 antes de cargar.

**Credenciales**: en `firmware/rf2_camara/rf2_camara.ino` están `WIFI_SSID = "NETWORK"` y `WIFI_PASS = "PASSWORD"` como valores genéricos; hay que cambiarlos por los de tu propia red (sin subirlos al repositorio). La AppKey de RF3 y de `lorawan_ns.py` es la clave de ejemplo pública de la especificación LoRaWAN.

## Modo simulado (sin hardware ni Bluetooth)

```
uv run python -m parcialfinal.gateway --simular          # terminal 1
uv run python -m parcialfinal.panel                      # terminal 2 → http://127.0.0.1:7860
```
Cada 90 s el simulador dispara un PIR aislado de RF2 (sospecha) y luego RF2 + RF3 con 6 s de diferencia (alerta). `--periodo-rf3 N` cambia los segundos entre uplinks simulados (10 por defecto).

## Gateway real

1. Servidor de red LoRaWAN (en el Mac, con el receptor ESP32 por USB): `python3 lorawan_ns.py --port /dev/cu.usbserial-XXXX`. Publica en UDP 127.0.0.1:9001.
2. Gateway: `uv run python -m parcialfinal.gateway`. Opciones: `--sin rf1 rf3` omite nodos; `--config otro.toml`.
   - RF1 necesita permiso de Bluetooth para la terminal (Ajustes del Sistema → Privacidad y seguridad → Bluetooth).
   - RF2: `http://nodocam.local`; si falla mDNS, poner `ip_respaldo` en `[rf2]`.
3. Panel: `uv run python -m parcialfinal.panel` (`--puerto` opcional). Puede abrirse o cerrarse sin afectar al gateway.

## Datos generados (`data/`, no versionado)

`telemetria.csv`, `eventos.csv`, `rf2_fotos.csv` (decisión y tiempos por etapa de RF2), `rf3_uplinks.csv` (RSSI, SNR, marcas del servidor de red y del gateway), `fotos/`, `estado.json` (lo que lee el panel).

## Métricas para el informe

```
uv run python scripts/metricas.py --desde 2026-11-26T10:00 --hasta 2026-11-26T11:00
```

## Pruebas

`uv run pytest` (filtrado, quórum, adaptadores, núcleo, métricas). Decisiones y checklist con hardware: `NOTAS.md`.

## Pruebas de RF3 y de alcance (para el informe)

```
uv run python scripts/prueba_rf3.py --duracion 300 --periodo 60   # enlace, filtro, ancho de banda
uv run python scripts/prueba_rf3.py --pir                         # 60 s, lista los eventos PIR de RF3
uv run python scripts/prueba_alcance.py                           # 5, 10 y 20 m, 3 min cada una
uv run python scripts/prueba_alcance.py --solo 10                 # una sola distancia (se fusiona con las demás)
```
`--simular` ejercita ambos sin hardware (datos en `data_sim/`). `--periodo` debe coincidir con `PERIODO_S` del firmware de RF3. Los scripts lanzan el gateway y, si no está en marcha, `lorawan_ns.py`. Resultados en `~/Edge/InformeFinal/datos/` (`rf3_resultados`, `alcance_resultados`, `alcance_log.csv`).
