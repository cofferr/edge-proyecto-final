"""Mapa estático dato -> capa donde se detiene (no hay Cloud).

Convención del informe: los nodos son Edge (procesan cerca de la fuente) y el gateway es Fog.
Los datos de telemetría, las fotos y los eventos PIR se detienen en el gateway (Fog);
no se envía nada a la nube.
"""

EDGE = "Edge"
FOG = "Fog"

# (dato, capa donde se detiene, quién lo produce / dónde se procesa)
MAPA_CAPAS: list[tuple[str, str, str]] = [
    ("RF1 temperatura / humedad aire / humedad suelo (mV)", FOG, "Medido en nodo Edge; filtrado y guardado en gateway"),
    ("RF2 decisión local (confirmed, reason, métricas)", EDGE, "Calculada en el ESP32-CAM; el gateway solo la registra"),
    ("RF2 foto JPEG del evento", FOG, "Capturada en el nodo; descargada y guardada en gateway"),
    ("RF2 evento PIR", FOG, "Detectado en el nodo; el quórum se decide en gateway"),
    ("RF3 temperatura / humedad aire", FOG, "Medido en nodo Edge; filtrado y guardado en gateway"),
    ("RF3 uplink (RSSI, SNR, contador)", FOG, "Metadatos del servidor de red; guardados en gateway"),
    ("RF3 evento PIR", FOG, "Detectado en el nodo; el quórum se decide en gateway"),
    ("Quórum PIR (sospecha / alerta)", FOG, "Decisión del gateway con RF2 + RF3"),
    ("Nada hacia la nube", "—", "No hay capa Cloud"),
]
