"""Núcleo del gateway (Fog): filtrado, quórum, almacenamiento y estado compartido.

Es lo único que comparten los lectores de nodo. Cada lector (hilo propio) llama a
`lectura`, `evento_pir` y `actualizar_nodo`; un hilo de `tick` apaga la alerta caducada y
publica el estado en `<carpeta>/estado.json` (escritura atómica). El panel solo lee ese archivo.
"""

import json
import os
import threading
import time
from collections import deque

from parcialfinal.almacen import Almacen, iso
from parcialfinal.capas import MAPA_CAPAS
from parcialfinal.config import Config
from parcialfinal.filtro import BancoFiltros
from parcialfinal.quorum import ALERTA, Quorum

NODOS = ("RF1", "RF2", "RF3")


class Nucleo:
    def __init__(self, cfg: Config, reloj=time.time):
        self.cfg = cfg
        self.reloj = reloj
        self.almacen = Almacen(cfg.almacen.carpeta)
        f = cfg.filtro
        self.filtros = BancoFiltros(
            {
                "temperatura": f.umbral_temperatura_c,
                "humedad_aire": f.umbral_humedad_aire_pct,
                "humedad_suelo_mv": f.umbral_humedad_suelo_mv,
            },
            f.latido_s,
        )
        self.quorum = Quorum(cfg.quorum.ventana_s)
        self.lock = threading.Lock()
        self.timeouts = {
            "RF1": cfg.rf1.timeout_en_linea_s,
            "RF2": cfg.rf2.timeout_en_linea_s,
            "RF3": cfg.rf3.timeout_en_linea_s,
        }
        self.nodos = {n: {"t_ultimo_dato": None, "lecturas": {}, "extra": {}} for n in NODOS}
        self.eventos = deque(maxlen=20)
        self.contadores = {"sospechas": 0, "alertas": 0}
        self.alerta_desde: float | None = None
        self.ultima_sospecha: float | None = None
        self.ruta_estado = self.almacen.carpeta / "estado.json"
        self._parar = threading.Event()
        self._escritura = threading.Lock()  # serializa la escritura de estado.json

    # ------------------------------------------------------------ entradas de los lectores
    def lectura(self, nodo: str, magnitud: str, valor: float, t: float | None = None) -> bool:
        """Filtra y guarda una lectura de telemetría. Devuelve si fue aceptada."""
        t = self.reloj() if t is None else t
        with self.lock:
            aceptada = self.filtros.evaluar(nodo, magnitud, valor, t)
            self.nodos[nodo]["lecturas"][magnitud] = valor  # el panel muestra la última recibida
            self.almacen.escribir(
                "telemetria.csv",
                {"nodo": nodo, "magnitud": magnitud, "valor": valor,
                 "t_recepcion": iso(t), "aceptada": "si" if aceptada else "no"},
            )
        return aceptada

    def actualizar_nodo(self, nodo: str, t: float, **extra) -> None:
        """Marca actividad del nodo (para en línea/antigüedad) y guarda datos para el panel."""
        with self.lock:
            self.nodos[nodo]["t_ultimo_dato"] = t
            self.nodos[nodo]["extra"].update(extra)

    def evento_pir(self, fuente: str, t_recepcion: float, decision_local: str = "",
                   ruta_foto: str = "", tam_foto: int | str = "") -> str:
        """Registra un evento PIR y aplica el quórum. Devuelve 'sospecha' o 'alerta'."""
        with self.lock:
            tipo = self.quorum.evento(fuente, t_recepcion)
            if tipo == ALERTA:
                self.contadores["alertas"] += 1
                if self.alerta_desde is None:
                    self.alerta_desde = t_recepcion
            else:
                self.contadores["sospechas"] += 1
                self.ultima_sospecha = t_recepcion
            self._fila_evento(tipo, fuente, t_recepcion, decision_local, ruta_foto, tam_foto,
                              round((self.reloj() - t_recepcion) * 1000, 3))
        self.publicar()
        return tipo

    def _fila_evento(self, tipo, fuente, t, decision, foto, tam, t_proc_ms):
        self.almacen.escribir(
            "eventos.csv",
            {"t_recepcion": iso(t), "tipo": tipo, "fuente": fuente, "decision_local_rf2": decision,
             "ruta_foto": foto, "tam_foto_bytes": tam, "t_proc_ms": t_proc_ms},
        )
        self.eventos.appendleft(
            {"t": iso(t), "tipo": tipo, "fuente": fuente, "decision_local": decision, "foto": foto}
        )

    # ------------------------------------------------------------ mantenimiento y estado
    def tick(self) -> None:
        """Apaga la alerta caducada y publica el estado."""
        ahora = self.reloj()
        with self.lock:
            if self.quorum.actualizar(ahora):
                self.alerta_desde = None
                self._fila_evento("fin_alerta", "", ahora, "", "", "", 0)
        self.publicar()

    def estado(self) -> dict:
        ahora = self.reloj()
        with self.lock:
            nodos = {}
            for n, d in self.nodos.items():
                t = d["t_ultimo_dato"]
                edad = None if t is None else ahora - t
                nodos[n] = {
                    "lecturas": dict(d["lecturas"]),
                    "extra": dict(d["extra"]),
                    "t_ultimo_dato": t,
                    "edad_s": edad,
                    "en_linea": edad is not None and edad <= self.timeouts[n],
                    "timeout_s": self.timeouts[n],
                }
            return {
                "t_estado": ahora,
                "alerta_activa": self.quorum.activa,
                "alerta_desde": self.alerta_desde,
                "ultima_sospecha": self.ultima_sospecha,
                "ventana_s": self.quorum.ventana_s,
                "contadores": dict(self.contadores),
                "nodos": nodos,
                "filtros": self.filtros.estadisticas(),
                "eventos": list(self.eventos),
                "mapa_capas": [list(x) for x in MAPA_CAPAS],
            }

    def publicar(self) -> None:
        """Escribe estado.json de forma atómica (el panel nunca ve un archivo a medias)."""
        datos = json.dumps(self.estado(), ensure_ascii=False)
        tmp = self.ruta_estado.with_suffix(".tmp")
        with self._escritura:
            tmp.write_text(datos, encoding="utf-8")
            os.replace(tmp, self.ruta_estado)

    def bucle_tick(self, periodo_s: float = 1.0) -> None:
        while not self._parar.wait(periodo_s):
            self.tick()

    def parar(self) -> None:
        self._parar.set()
