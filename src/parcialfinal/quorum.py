"""Quórum de movimiento entre las fuentes PIR (RF2 y RF3). Lógica pura, el tiempo se pasa explícito.

- Se guarda el instante del último evento por fuente (marca de recepción en el gateway).
- Evento de la fuente s: si la OTRA fuente tuvo un evento hace W o menos -> "alerta"
  confirmada; si no -> "sospecha" (se registra, no se notifica).
- La alerta sigue activa mientras alguna fuente tenga un evento a W o menos; se desactiva
  cuando ninguna fuente tiene eventos durante más de W (frontera inclusiva, igual que el
  criterio de confirmación).
"""

SOSPECHA = "sospecha"
ALERTA = "alerta"


class Quorum:
    def __init__(self, ventana_s: float, fuentes: tuple[str, ...] = ("RF2", "RF3")):
        self.ventana_s = ventana_s
        self.fuentes = fuentes
        self.ultimo: dict[str, float | None] = {f: None for f in fuentes}
        self.activa = False

    def evento(self, fuente: str, t: float) -> str:
        """Registra un evento PIR y devuelve SOSPECHA o ALERTA."""
        self.actualizar(t)  # una alerta caducada no debe sobrevivir a un evento tardío
        otras = [f for f in self.fuentes if f != fuente]
        confirmada = any(
            self.ultimo[o] is not None and t - self.ultimo[o] <= self.ventana_s for o in otras
        )
        self.ultimo[fuente] = t
        if confirmada:
            self.activa = True
            return ALERTA
        return SOSPECHA

    def actualizar(self, t: float) -> bool:
        """Evalúa la caducidad. Devuelve True si la alerta estaba activa y acaba de apagarse."""
        if not self.activa:
            return False
        recientes = [x for x in self.ultimo.values() if x is not None]
        if not recientes or t - max(recientes) > self.ventana_s:
            self.activa = False
            return True
        return False
