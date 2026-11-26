"""Carga de config.toml en dataclasses inmutables."""

import tomllib
from dataclasses import dataclass, fields
from pathlib import Path


@dataclass(frozen=True)
class Filtro:
    umbral_temperatura_c: float = 0.5
    umbral_humedad_aire_pct: float = 2.0
    umbral_humedad_suelo_mv: float = 50.0
    latido_s: float = 300.0


@dataclass(frozen=True)
class Quorum:
    ventana_s: float = 30.0


@dataclass(frozen=True)
class Rf1:
    nombre: str = "EstacionESP32"
    service_uuid: str = "7f3c1a10-5d2b-4e8a-9c41-2b6f0d3e8a01"
    char_uuid: str = "7f3c1a11-5d2b-4e8a-9c41-2b6f0d3e8a01"
    timeout_en_linea_s: float = 10.0


@dataclass(frozen=True)
class Rf2:
    url: str = "http://nodocam.local"
    ip_respaldo: str = ""
    periodo_s: float = 1.0
    timeout_http_s: float = 3.0
    timeout_en_linea_s: float = 5.0


@dataclass(frozen=True)
class Rf3:
    modo: str = "udp"
    udp_host: str = "127.0.0.1"
    udp_puerto: int = 9001
    archivo: str = "lorawan_uplinks.jsonl"
    timeout_en_linea_s: float = 150.0


@dataclass(frozen=True)
class Almacen:
    carpeta: str = "data"


@dataclass(frozen=True)
class Panel:
    puerto: int = 7860
    refresco_s: float = 1.0


@dataclass(frozen=True)
class Config:
    filtro: Filtro = Filtro()
    quorum: Quorum = Quorum()
    rf1: Rf1 = Rf1()
    rf2: Rf2 = Rf2()
    rf3: Rf3 = Rf3()
    almacen: Almacen = Almacen()
    panel: Panel = Panel()


def cargar(ruta: str | Path | None = "config.toml") -> Config:
    """Lee el TOML; las claves ausentes toman el valor por defecto."""
    datos = {}
    if ruta and Path(ruta).exists():
        with open(ruta, "rb") as f:
            datos = tomllib.load(f)
    partes = {}
    for campo in fields(Config):
        clase = type(getattr(Config(), campo.name))
        partes[campo.name] = clase(**datos.get(campo.name, {}))
    return Config(**partes)
