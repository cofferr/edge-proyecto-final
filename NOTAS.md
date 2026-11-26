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
