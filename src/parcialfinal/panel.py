"""Panel RF5 (Gradio, solo lectura). Arranque: `uv run python -m parcialfinal.panel`.

No arranca ni reinicia nada del gateway: lee <carpeta>/estado.json (que escribe el núcleo)
cada `refresco_s` con gr.Timer. La antigüedad y el estado en línea se recalculan aquí con la
hora actual, así que un núcleo detenido se nota (las lecturas envejecen y aparece el aviso).
"""

import argparse
import html
import json
import time
from pathlib import Path

import gradio as gr

from parcialfinal import config as cfgmod

NUCLEO_CAIDO_S = 5.0  # sin republicar el estado en este tiempo: núcleo detenido

ETIQUETAS = {
    "temperatura": ("Temperatura", "{:.2f} °C"),
    "humedad_aire": ("Humedad aire", "{:.2f} %"),
    "humedad_suelo_mv": ("Humedad suelo", "{:.0f} mV"),
}
TITULOS = {"RF1": "RF1 · BLE · EstacionESP32", "RF2": "RF2 · ESP32-CAM · HTTP", "RF3": "RF3 · LoRaWAN"}

CSS = """
.tarjeta{border:1px solid #8884;border-radius:10px;padding:12px;min-height:170px}
.tarjeta h3{margin:0 0 6px 0}
.pill{display:inline-block;padding:2px 10px;border-radius:12px;font-weight:600;color:#fff}
.on{background:#2e9e4f}.off{background:#c0392b}
.alerta{background:#c0392b;color:#fff;font-size:1.4em;font-weight:700;padding:14px;border-radius:10px;text-align:center}
.sospecha{background:#e0a800;color:#000;font-size:1.1em;font-weight:600;padding:10px;border-radius:10px;text-align:center}
.normal{background:#2e9e4f33;padding:10px;border-radius:10px;text-align:center}
.caido{background:#555;color:#fff;padding:10px;border-radius:10px;text-align:center}
"""


def leer_estado(ruta: Path) -> dict | None:
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _edad(s: float | None) -> str:
    if s is None:
        return "sin datos"
    return f"hace {s:.0f} s" if s < 120 else f"hace {s / 60:.1f} min"


def _extra_html(nodo: str, ex: dict) -> str:
    if nodo == "RF2":
        if not ex:
            return ""
        dec = ex.get("last_reason")
        txt = "" if dec is None else f"{'confirmada' if ex.get('last_confirmed') else 'descartada'} ({html.escape(str(dec))})"
        return (f"<div>Eventos: {ex.get('events', '—')} · confirmados {ex.get('confirmed', '—')} · "
                f"descartados {ex.get('discarded', '—')}</div><div>Última decisión local: {txt or '—'}</div>")
    if nodo == "RF3" and ex:
        return (f"<div>RSSI {ex.get('rssi', '—')} dBm · SNR {ex.get('snr', '—')} dB · "
                f"contador {ex.get('cnt', '—')}</div>")
    return ""


def tarjeta(nodo: str, d: dict, ahora: float) -> str:
    t = d["t_ultimo_dato"]
    edad = None if t is None else ahora - t
    en_linea = edad is not None and edad <= d["timeout_s"]
    filas = "".join(
        f"<div>{ETIQUETAS[m][0]}: <b>{ETIQUETAS[m][1].format(v)}</b></div>" for m, v in d["lecturas"].items()
    ) or ("" if nodo == "RF2" else "<div>Sin lecturas</div>")
    return (
        f"<div class='tarjeta'><h3>{TITULOS[nodo]}</h3>"
        f"<span class='pill {'on' if en_linea else 'off'}'>{'EN LÍNEA' if en_linea else 'FUERA DE LÍNEA'}</span>"
        f" <small>último dato {_edad(edad)}</small>{filas}{_extra_html(nodo, d['extra'])}</div>"
    )


def banner(e: dict | None, ahora: float) -> str:
    if e is None or ahora - e["t_estado"] > NUCLEO_CAIDO_S:
        return "<div class='caido'>Núcleo del gateway sin publicar estado (¿no está en marcha?)</div>"
    if e["alerta_activa"]:
        desde = time.strftime("%H:%M:%S", time.localtime(e["alerta_desde"])) if e["alerta_desde"] else "—"
        return f"<div class='alerta'>🚨 ALERTA ACTIVA (quórum RF2 + RF3) desde {desde}</div>"
    sosp = e["ultima_sospecha"]
    if sosp and ahora - sosp <= e["ventana_s"]:
        return "<div class='sospecha'>⚠ Sospecha: un solo PIR dentro de la ventana (sin notificar)</div>"
    return "<div class='normal'>Sin alerta</div>"


def construir_panel(cfg: cfgmod.Config) -> gr.Blocks:
    ruta = Path(cfg.almacen.carpeta) / "estado.json"
    ultima_foto = {"ruta": None}

    def refrescar():
        ahora = time.time()
        e = leer_estado(ruta)
        if e is None:
            vacio = "<div class='tarjeta'>Sin estado todavía</div>"
            return banner(None, ahora), vacio, vacio, vacio, gr.skip(), [], []
        foto = e["nodos"]["RF2"]["extra"].get("ultima_foto")
        img = gr.skip()
        if foto and foto != ultima_foto["ruta"] and Path(foto).exists():
            ultima_foto["ruta"], img = foto, foto
        eventos = [[v["t"][11:23], v["tipo"], v["fuente"], v["decision_local"], Path(v["foto"]).name if v["foto"] else ""]
                   for v in e["eventos"][:10]]
        return (banner(e, ahora), *(tarjeta(n, e["nodos"][n], ahora) for n in ("RF1", "RF2", "RF3")),
                img, eventos, e["mapa_capas"])

    with gr.Blocks(title="Gateway Fog · Panel") as demo:
        gr.Markdown("# Gateway Fog (RF4) · Panel RF5 — solo lectura")
        alerta = gr.HTML()
        with gr.Row():
            with gr.Column():
                c1 = gr.HTML()
            with gr.Column():
                c2 = gr.HTML()
                foto = gr.Image(label="Última foto de RF2", type="filepath", interactive=False, height=240)
            with gr.Column():
                c3 = gr.HTML()
        gr.Markdown("### Últimos eventos")
        tabla = gr.Dataframe(headers=["Hora", "Tipo", "Fuente", "Decisión local RF2", "Foto"], interactive=False)
        gr.Markdown("### Mapa dato → capa")
        mapa = gr.Dataframe(headers=["Dato", "Capa donde se detiene", "Detalle"], interactive=False)
        timer = gr.Timer(cfg.panel.refresco_s)
        timer.tick(refrescar, outputs=[alerta, c1, c2, c3, foto, tabla, mapa])
        demo.load(refrescar, outputs=[alerta, c1, c2, c3, foto, tabla, mapa])
    return demo


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="Panel RF5 (solo lectura)")
    ap.add_argument("--config", default="config.toml")
    ap.add_argument("--puerto", type=int)
    a = ap.parse_args(argv)
    cfg = cfgmod.cargar(a.config)
    demo = construir_panel(cfg)
    demo.queue().launch(server_name="127.0.0.1", server_port=a.puerto or cfg.panel.puerto,
                        allowed_paths=[str(Path(cfg.almacen.carpeta).resolve())], css=CSS)


if __name__ == "__main__":
    main()
