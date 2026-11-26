"""Filtrado por umbral (banda muerta) por nodo y magnitud. Funciones puras, sin E/S.

Regla acordada: se acepta una lectura si
  - no hay valor aceptado previo, o
  - |x - x_ultimo| >= U (el umbral exacto SÍ acepta), o
  - han pasado T_lat o más desde la última aceptada (latido).
En cualquier otro caso se descarta.
"""

from dataclasses import dataclass

# Tolerancia numérica: 23.12 - 22.62 en coma flotante da 0.49999999999999645.
_EPS = 1e-9


@dataclass
class FiltroUmbral:
    umbral: float
    latido_s: float
    ultimo_valor: float | None = None
    ultimo_t: float | None = None
    recibidas: int = 0
    aceptadas: int = 0

    def evaluar(self, valor: float, t: float) -> bool:
        """Decide si la lectura se acepta y, en ese caso, actualiza la referencia."""
        self.recibidas += 1
        acepta = (
            self.ultimo_valor is None
            or abs(valor - self.ultimo_valor) >= self.umbral - _EPS
            or t - self.ultimo_t >= self.latido_s
        )
        if acepta:
            self.ultimo_valor, self.ultimo_t = valor, t
            self.aceptadas += 1
        return acepta

    @property
    def fraccion(self) -> float:
        """r = aceptadas / recibidas (0 si aún no hay lecturas)."""
        return self.aceptadas / self.recibidas if self.recibidas else 0.0


class BancoFiltros:
    """Un FiltroUmbral por (nodo, magnitud), creado al primer uso."""

    def __init__(self, umbrales: dict[str, float], latido_s: float):
        self.umbrales = umbrales  # magnitud -> U
        self.latido_s = latido_s
        self.filtros: dict[tuple[str, str], FiltroUmbral] = {}

    def evaluar(self, nodo: str, magnitud: str, valor: float, t: float) -> bool:
        clave = (nodo, magnitud)
        if clave not in self.filtros:
            self.filtros[clave] = FiltroUmbral(self.umbrales[magnitud], self.latido_s)
        return self.filtros[clave].evaluar(valor, t)

    def estadisticas(self) -> dict[str, dict[str, int]]:
        return {
            f"{n}/{m}": {"recibidas": f.recibidas, "aceptadas": f.aceptadas}
            for (n, m), f in sorted(self.filtros.items())
        }
