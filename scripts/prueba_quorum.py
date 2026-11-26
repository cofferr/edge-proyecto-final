#!/usr/bin/env python3
"""Prueba de quórum con RF2 y RF3 reales (o simulados con --simular): tres escenarios en secuencia.

  1. sospecha   - solo un PIR (primero RF3, luego RF2, en ventanas separadas): se espera sospecha, sin alerta.
  2. alerta     - RF3 y RF2 dentro de W: se espera alerta; mide la declaración y el apagado tras W s quieto.
  3. nodo_caido - se apaga RF3 y se mueve la mano frente a RF2: se registra la reacción del gateway.

Cada escenario muestra instrucciones y una cuenta atrás (20 s) y arranca por tiempo, sin esperar al usuario.
Este script solo OBSERVA al gateway (eventos.csv, estado.json); no toca su lógica.

  uv run python scripts/prueba_quorum.py                  # hardware real (RF2 y RF3 encendidos)
  uv run python scripts/prueba_quorum.py --simular        # sin hardware, W y tiempos reducidos (data_sim/)
Salida: <datos>/quorum_resultados.json/.md y capturas del panel en figuras/gateway/.
"""

import argparse
import json
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

from parcialfinal import config as cfgmod
from parcialfinal import evaluacion_quorum as ev
from parcialfinal import informe
from parcialfinal.capturas import Capturador
from parcialfinal.procesos import RAIZ, Sesion

PUERTO_PANEL = 7861
TITULO = "Resultados de la prueba de quórum (RF2 + RF3)"


def decir(texto: str, simular: bool) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {texto}", flush=True)
    if not simular and shutil.which("say"):
        subprocess.Popen(["say", texto])


def cuenta_atras(titulo: str, instrucciones: str, n: int, simular: bool) -> None:
    print("\n" + "=" * 70 + f"\n{titulo}\n{instrucciones}\n" + "=" * 70, flush=True)
    decir(f"{titulo}. {instrucciones}", simular)
    for i in range(n, 0, -1):
        print(f"   empieza en {i:2d} s", flush=True)
        time.sleep(1)
    decir("Ya", simular)


# ------------------------------------------------------------------ entorno real o simulado
class Entorno:
    """Gateway (real: subproceso; simulado: en proceso con nodos falsos) + panel + observación."""

    def __init__(self, a):
        self.a = a
        self.sim = a.simular
        self.accion_s = a.accion_s if a.accion_s else (10 if self.sim else 40)
        self.act = None

    def __enter__(self):
        a = self.a
        if self.sim:
            self.sesion = Sesion(True, a.periodo, ventana_s=5, timeout_rf3_s=12, nombre="quorum")
            self.sesion.carpeta.mkdir(parents=True, exist_ok=True)
            self._montar_sim()
        else:
            self.sesion = Sesion(False, a.periodo, a.puerto, sin=("rf1",))
            self.sesion.__enter__()
        self.carpeta, self.config = self.sesion.carpeta, self.sesion.config
        self.cfg = cfgmod.cargar(self.config)
        self.W = self.cfg.quorum.ventana_s
        self.salida = a.salida or self.sesion.salida
        figs = [RAIZ / "data_sim" / "figuras"] if self.sim else [
            Path.home() / "Edge" / "InformeFinal" / "figuras" / "gateway", RAIZ / "figuras" / "gateway"]
        self.sesion.lanzar_panel(PUERTO_PANEL)
        self.cap = Capturador(f"http://127.0.0.1:{PUERTO_PANEL}", figs)
        if not a.sin_capturas:
            self.cap.abrir()
            if not self.cap.ok:
                print(f"AVISO: sin capturas automáticas ({self.cap.error}); tómalas a mano")
        return self

    def _montar_sim(self):
        from parcialfinal.nodos.rf2_http import LectorCam
        from parcialfinal.nodos.rf3_lora import AdaptadorRf3
        from parcialfinal.nucleo import Nucleo
        from parcialfinal.simulador import CamFalsa, Simulador
        # reutiliza la config simulada que Sesion genera (W corto, carpeta data_sim/quorum)
        texto = (RAIZ / "config.toml").read_text().replace('carpeta = "data"', f'carpeta = "{self.sesion.carpeta}"')
        texto = texto.replace("ventana_s = 30", "ventana_s = 5").replace("timeout_en_linea_s = 150", "timeout_en_linea_s = 12")
        ruta = self.sesion.carpeta / "config.sim.toml"
        ruta.write_text(texto)
        self.sesion.config = str(ruta)
        cfg = cfgmod.cargar(str(ruta))
        for f in ("eventos.csv", "telemetria.csv", "rf2_fotos.csv", "rf3_uplinks.csv"):
            (self.sesion.carpeta / f).unlink(missing_ok=True)
        nucleo = Nucleo(cfg)
        cam = CamFalsa()
        lector, rf3 = LectorCam(nucleo, cam, cfg.rf2), AdaptadorRf3(nucleo, cfg.rf3)
        sim = Simulador(None, cam, cfg.rf3, self.a.periodo)
        self.act = type("Act", (), {"cam": cam, "sim": sim, "apagado": False})()
        for f in (nucleo.bucle_tick, lector.ejecutar, rf3.ejecutar):
            threading.Thread(target=f, daemon=True).start()
        time.sleep(0.5)

        def periodico():
            while not sim._parar.is_set():
                if not self.act.apagado:
                    sim._uplink(0)
                sim._parar.wait(self.a.periodo)
        threading.Thread(target=periodico, daemon=True).start()
        self._parar_sim = lambda: (sim.parar(), lector.parar(), rf3.parar(), nucleo.parar())

    def __exit__(self, *exc):
        self.cap.cerrar()
        if self.sim:
            self._parar_sim()
            detener = __import__("parcialfinal.procesos", fromlist=["detener"]).detener
            detener(self.sesion.panel)
        else:
            self.sesion.__exit__(*exc)
        return False

    # -- acciones simuladas (en real, las hace la persona)
    def pir(self, fuente: str):
        if self.act:
            self.act.sim._uplink(1) if fuente == "RF3" else self.act.cam.disparar(True)

    def apagar_rf3(self):
        if self.act:
            self.act.apagado = True

    # -- observación
    def estado(self) -> dict | None:
        try:
            return json.loads((self.carpeta / "estado.json").read_text())
        except (OSError, ValueError):
            return None

    def eventos(self, t0, t1=None):
        return ev.leer_eventos(self.carpeta, t0, t1 or time.time() + 5)

    def esperar_evento(self, t0, tipos, fuente=None, hasta=None) -> dict | None:
        """Espera (por tiempo, no por confirmación) a que aparezca un evento de esos tipos desde t0."""
        while time.time() < (hasta or time.time()):
            for e in self.eventos(t0):
                if e["tipo"] in tipos and (fuente is None or e["fuente"] == fuente):
                    return e
            time.sleep(0.25)
        return None

    def calma(self):
        """Espera a que pasen W + 5 s desde el último evento PIR, para que un escenario no contamine al siguiente."""
        pir = [e["t"] for e in self.eventos(0) if e["tipo"] in ev.PIR + ("fin_alerta",)]
        if pir:
            falta = max(pir) + self.W + 5 - time.time()
            if falta > 0:
                print(f"   (calma: {falta:.0f} s sin eventos para no mezclar escenarios)", flush=True)
                time.sleep(falta)


# ------------------------------------------------------------------ escenarios
def esc_sospecha(env: Entorno, a) -> dict:
    partes, filas, capturas = {}, [], []
    todo_ok = True
    for fuente, otra in (("RF3", "RF2"), ("RF2", "RF3")):
        env.calma()
        cuenta_atras(f"ESCENARIO 1 · SOSPECHA ({fuente})",
                     f"TAPA el PIR de {otra} con un vaso opaco o cartón y mueve la mano SOLO frente al PIR de {fuente} (una o dos veces). "
                     f"Mantente lejos de {otra}.", a.cuenta, env.sim)
        t0 = time.time()
        if env.sim:
            time.sleep(1.5)
            env.pir(fuente)
        fin = t0 + env.accion_s
        primero = env.esperar_evento(t0, ("sospecha", "alerta"), hasta=fin)
        if primero and fuente == "RF3" and env.cap.capturar("panel_sospecha", 1.5):
            capturas.append("panel_sospecha.png")
        while time.time() < fin:
            time.sleep(0.25)
        r = ev.evaluar_sospecha(env.eventos(t0, time.time()), fuente)
        partes[fuente] = r
        todo_ok &= r["coincide"]
        filas.append({"parte": f"solo {fuente}", "resultado": r["resultado"], "coincide": "sí" if r["coincide"] else "no",
                      "eventos": "; ".join(r["eventos"]) or "ninguno", "nota": r["nota"]})
        print(f"   -> solo {fuente}: {r['resultado']} (coincide: {'sí' if r['coincide'] else 'NO'}) {r['nota']}")
    avisos = [f"solo {f}: {p['nota']}" for f, p in partes.items() if p["nota"]]
    return {"que_mide": "Un solo PIR activo (RF3 y luego RF2, en ventanas separadas): el gateway debe registrar sospecha y no alerta",
            "unidades": "horas locales de recepción en el gateway",
            "resumen": {"esperado": "sospecha, sin alerta", "coincide": "sí" if todo_ok else "no",
                        "capturas": ", ".join(capturas) or "ninguna"},
            "filas": filas, "avisos": avisos}


def esc_alerta(env: Entorno, a) -> dict:
    env.calma()
    cuenta_atras("ESCENARIO 2 · ALERTA",
                 f"Mueve la mano frente al PIR de RF3 y, en menos de {env.W:.0f} s, frente al de RF2. Después SAL del campo "
                 "de visión de RF2 y de su PIR, y NO muevas nada hasta que termine.",
                 a.cuenta, env.sim)
    t0 = time.time()
    if env.sim:
        time.sleep(1.5)
        env.pir("RF3")
        time.sleep(min(8, env.W / 3))
        env.pir("RF2")
    capturas = []
    alerta = env.esperar_evento(t0, ("alerta",), hasta=t0 + env.accion_s)
    if alerta and env.cap.capturar("panel_alerta", 1.5):
        capturas.append("panel_alerta.png")
    # el usuario se queda quieto; se espera el apagado (W s tras el último evento) con margen
    fin = env.esperar_evento(t0, ("fin_alerta",), hasta=time.time() + env.W + 25) if alerta else None
    t1 = time.time()
    r = ev.evaluar_alerta(env.eventos(t0, t1), env.W)
    print(f"   -> {r['resultado']} (coincide: {'sí' if r['coincide'] else 'NO'}) {r['nota']}")
    resumen = {"esperado": "alerta y apagado a W s del último evento", "coincide": "sí" if r["coincide"] else "no",
               "W_s": env.W, "capturas": ", ".join(capturas) or "ninguna"}
    for k in ("primer_pir", "segundo_pir", "separacion_pirs_s", "declaracion_alerta_ms", "apagado_s"):
        if k in r:
            resumen[k] = r[k]
    return {"que_mide": "RF2 y RF3 dentro de W: el gateway debe declarar la alerta; se mide el tiempo hasta declararla "
                        "(desde que el gateway recibe el segundo PIR) y hasta apagarla (desde el último evento)",
            "unidades": "declaracion_alerta_ms en ms; apagado_s y separacion_pirs_s en s; horas locales",
            "resumen": resumen,
            "filas": [{"evento": x} for x in r["eventos"]], "avisos": [r["nota"]] if r["nota"] else []}


def esc_caido(env: Entorno, a) -> dict:
    env.calma()
    timeout = env.cfg.rf3.timeout_en_linea_s
    cuenta_atras("ESCENARIO 3 · NODO CAÍDO (RF3)",
                 "APAGA RF3 (quita su alimentación) al terminar la cuenta atrás y ALÉJATE de él (tu mano frente a su PIR "
                 "cuenta como evento). Espera unos 40 s sin moverte, luego mueve la mano UNA vez frente al PIR de RF2 "
                 "y no toques nada más.", a.cuenta, env.sim)
    t0 = time.time()
    ultimo_dato, fuera = None, None
    if env.sim:
        env.apagar_rf3()
    moved = False
    limite = t0 + timeout + a.periodo + 40
    capturas = []
    while time.time() < limite:
        e = env.estado()
        if e:
            rf3 = e["nodos"]["RF3"]
            if rf3["t_ultimo_dato"]:
                ultimo_dato = rf3["t_ultimo_dato"]
            if not rf3["en_linea"] and ultimo_dato and ultimo_dato < e["t_estado"] - 1:
                fuera = e["t_estado"]
                break
        if env.sim and not moved and time.time() > t0 + 3:
            env.pir("RF2")
            moved = True
        time.sleep(0.5)
    if fuera and env.cap.capturar("panel_nodo_caido", 1.5):
        capturas.append("panel_nodo_caido.png")
    r = ev.evaluar_nodo_caido(env.eventos(t0, time.time()), "RF2", ultimo_dato, fuera, timeout)
    print(f"   -> {r['resultado']} (coincide: {'sí' if r['coincide'] else 'NO'}) {r['nota']}")
    resumen = {k: v for k, v in r.items() if k not in ("eventos", "nota", "resultado", "coincide") and v is not None}
    resumen.update({"esperado": "sospecha de RF2 sin alerta; RF3 pasa a fuera de línea", "resultado": r["resultado"],
                    "coincide": "sí" if r["coincide"] else "no", "capturas": ", ".join(capturas) or "ninguna"})
    return {"que_mide": "Con RF3 apagado, evento de RF2: el gateway debe dar sospecha (no alerta) y marcar RF3 fuera de línea; "
                        "se mide el tiempo hasta detectar la caída desde el último dato de RF3",
            "unidades": "tiempos en s; horas locales; timeout configurado en s",
            "resumen": resumen, "filas": [{"evento": x} for x in r["eventos"]], "avisos": [r["nota"]]}


# ------------------------------------------------------------------ principal
def esperar_nodos(env: Entorno, a) -> None:
    """Comprobación previa: RF2 en línea y primer uplink de RF3 (hasta 1,3 períodos)."""
    limite = time.time() + a.periodo * 1.3 + 15
    print(f"Comprobando que RF2 y RF3 aportan datos (hasta {limite - time.time():.0f} s)...", flush=True)
    while time.time() < limite:
        e = env.estado()
        if e and e["nodos"]["RF2"]["en_linea"] and e["nodos"]["RF3"]["en_linea"]:
            print("   RF2 y RF3 en línea.")
            return
        time.sleep(1)
    e = env.estado() or {"nodos": {}}
    raise SystemExit("ERROR: no llegan datos de " + ", ".join(
        n for n in ("RF2", "RF3") if not e["nodos"].get(n, {}).get("en_linea")) + ". Revisa los nodos y repite.")


def main(argv=None):
    signal.signal(signal.SIGINT, signal.default_int_handler)
    ap = argparse.ArgumentParser()
    ap.add_argument("--simular", action="store_true")
    ap.add_argument("--cuenta", type=int, default=20, help="segundos de cuenta atrás antes de cada escenario")
    ap.add_argument("--accion-s", type=float, help="segundos para actuar en cada escenario (40 real, 10 simulado)")
    ap.add_argument("--periodo", type=float, default=60, help="período de envío de RF3 (s)")
    ap.add_argument("--escenarios", nargs="+", default=["sospecha", "alerta", "nodo_caido"],
                    choices=["sospecha", "alerta", "nodo_caido"])
    ap.add_argument("--puerto")
    ap.add_argument("--salida", type=Path)
    ap.add_argument("--sin-capturas", action="store_true")
    a = ap.parse_args(argv)
    if a.simular:
        a.periodo = 3 if a.periodo == 60 else a.periodo
        a.cuenta = 2 if a.cuenta == 20 else a.cuenta
    funciones = {"sospecha": esc_sospecha, "alerta": esc_alerta, "nodo_caido": esc_caido}
    resultados = {}
    with Entorno(a) as env:
        try:
            esperar_nodos(env, a)
            time.sleep(3)
            if not a.sin_capturas and env.cap.capturar("panel_reposo", 2.5):
                print("   captura panel_reposo.png")
            for nombre in a.escenarios:
                resultados[nombre] = funciones[nombre](env, a)
        except KeyboardInterrupt:
            print("\nCtrl+C: se guardan los escenarios ya terminados")
        for nombre, d in resultados.items():
            informe.guardar_resultado(env.salida, "quorum_resultados", nombre, d, TITULO)
        if env.cap.guardadas:
            print("Capturas:", ", ".join(env.cap.guardadas))
    print("\nRESUMEN")
    for n, d in resultados.items():
        print(f"  {n}: coincide con lo esperado = {d['resumen']['coincide']}")
    print(f"Resultados en {env.salida / 'quorum_resultados.md'}")
    return 0 if resultados else 1


if __name__ == "__main__":
    sys.exit(main())
