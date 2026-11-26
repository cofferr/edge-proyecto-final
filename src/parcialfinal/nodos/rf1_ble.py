"""RF1 (BLE): central bleak para el periférico "EstacionESP32" con reconexión automática.

Trama de 7 bytes little-endian (notificación cada 2 s):
  0-1 int16  temperatura x100 (°C)    2-3 uint16 humedad aire x100 (%)
  4-5 uint16 humedad suelo en mV (0xFFFF = sin dato; NO se convierte a %)
  6   uint8  movimiento (siempre 0: sin PIR; se ignora)
"""

import asyncio
import logging
import struct
import time

from parcialfinal.config import Rf1
from parcialfinal.nucleo import Nucleo

log = logging.getLogger("rf1")


def decodificar(datos: bytes) -> dict:
    """Devuelve {magnitud: valor}; omite las magnitudes 'sin dato'. ValueError si la trama es inválida."""
    if len(datos) != 7:
        raise ValueError(f"trama de {len(datos)} bytes (se esperaban 7)")
    t, h, suelo, _mov = struct.unpack("<hHHB", datos)
    out = {"temperatura": t / 100.0, "humedad_aire": h / 100.0}
    if suelo != 0xFFFF:
        out["humedad_suelo_mv"] = float(suelo)
    return out


class LectorBle:
    def __init__(self, nucleo: Nucleo, cfg: Rf1):
        self.nucleo, self.cfg = nucleo, cfg
        self._parar = False

    def al_recibir(self, datos: bytes) -> None:
        """Callback de cada notificación (también lo usa el modo simulado)."""
        t = time.time()
        try:
            lecturas = decodificar(bytes(datos))
        except ValueError as e:
            log.warning("RF1 trama inválida: %s", e)
            return
        for magnitud, valor in lecturas.items():
            self.nucleo.lectura("RF1", magnitud, valor, t)
        self.nucleo.actualizar_nodo("RF1", t, conectado=True)

    async def _sesion(self) -> None:
        from bleak import BleakClient, BleakScanner  # diferido: no hace falta en modo simulado

        c = self.cfg
        dispositivo = await BleakScanner.find_device_by_filter(
            lambda d, adv: c.service_uuid in [u.lower() for u in adv.service_uuids] or d.name == c.nombre,
            timeout=20.0,
        )
        if dispositivo is None:
            raise ConnectionError(f"no se encontró {c.nombre}")
        perdido = asyncio.Event()
        async with BleakClient(dispositivo, disconnected_callback=lambda _: perdido.set()) as cli:
            log.info("RF1 conectado a %s", dispositivo.address)
            await cli.start_notify(c.char_uuid, lambda _, d: self.al_recibir(bytes(d)))
            while not perdido.is_set() and not self._parar:
                await asyncio.sleep(0.5)

    async def _bucle(self) -> None:
        espera = 1.0
        while not self._parar:
            try:
                await self._sesion()
                espera = 1.0
            except Exception as e:  # reconexión con backoff acotado
                log.warning("RF1 sesión terminada: %s (reintento en %.0f s)", e, espera)
                await asyncio.sleep(espera)
                espera = min(espera * 2, 30.0)

    def ejecutar(self) -> None:
        asyncio.run(self._bucle())

    def parar(self) -> None:
        self._parar = True
