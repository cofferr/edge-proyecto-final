#!/usr/bin/env python3
"""Métricas del informe para un rango de tiempo.

Uso: uv run python scripts/metricas.py [--datos data] [--desde 2026-11-25T10:00] [--hasta 2026-11-25T12:00]
Las fechas sin zona se interpretan en hora local. Sin rango = todo.
"""

import argparse
from datetime import UTC, datetime

from parcialfinal.metricas import calcular, formatear


def fecha(s: str) -> datetime:
    d = datetime.fromisoformat(s)
    return d if d.tzinfo else d.astimezone()


ap = argparse.ArgumentParser()
ap.add_argument("--datos", default="data")
ap.add_argument("--desde", type=fecha, default=datetime(2000, 1, 1, tzinfo=UTC))
ap.add_argument("--hasta", type=fecha, default=datetime(2100, 1, 1, tzinfo=UTC))
a = ap.parse_args()
print(formatear(calcular(a.datos, a.desde, a.hasta)))
