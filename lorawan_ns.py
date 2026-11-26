#!/usr/bin/env python3
# NOTA: la AppKey de este archivo (2B7E151628AED2A6ABF7158809CF4F3C) es la clave de ejemplo
# PÚBLICA de la especificación LoRaWAN, no un secreto. Para un despliegue real, cámbiala
# (igual en el sketch del nodo). Las claves de sesión (ns_state.json) NO se versionan.
"""
Servidor de red LoRaWAN minimo (1.0.x, OTAA, Clase A) para el proyecto Edge.

Hace lo que haria un Network Server + Application Server de juguete:
  * Join OTAA: valida MIC del Join-Request, genera Join-Accept, deriva NwkSKey/AppSKey.
  * Uplinks: reconstruye FCnt de 32 bits, valida MIC, descifra el payload con AppSKey.
  * Entrega cada lectura decodificada (JSONL + UDP local + callback) al gateway RF4.

Habla con el "front-end de radio" (ESP32 receptor) por USB serie con un protocolo de lineas:
  ESP32 -> Mac : RX <hex> <rssi> <snr> <ms_esp32>
  Mac -> ESP32 : TX <retardo_ms> <hex>     (retardo medido desde el fin de la ultima RX)

Uso:
  python3 lorawan_ns.py --port /dev/cu.usbserial-XXXX
  python3 lorawan_ns.py --selftest

Dependencias: pip install cryptography pyserial
"""
import argparse, json, os, socket, struct, sys, threading, time
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.cmac import CMAC

# ---------------------------------------------------------------- configuracion
# Credenciales de los nodos. DevEUI/JoinEUI se escriben en hex "como numero" (igual que
# el uint64_t del sketch: 0x70B3D57ED0000001 -> "70B3D57ED0000001").
DEVICES = {
    "70B3D57ED0000001": {
        "name": "rf3-lora",
        "join_eui": "0000000000000001",
        "app_key": "2B7E151628AED2A6ABF7158809CF4F3C",   # CAMBIAR (igual al del sketch)
    },
}
NET_ID = 0x000000
RX1_DELAY_JOIN_MS = 5000     # RadioLib: JOIN_ACCEPT_DELAY_1 = 5 s
RX1_DELAY_DATA_MS = 1000     # RxDelay=0 en el Join-Accept -> 1 s
STATE_FILE = "ns_state.json"
UPLINK_LOG = "lorawan_uplinks.jsonl"
UDP_PUBLISH = ("127.0.0.1", 9001)

# ---------------------------------------------------------------- criptografia
def aes_enc(key, block):
    e = Cipher(algorithms.AES(key), modes.ECB()).encryptor()
    return e.update(block) + e.finalize()

def aes_dec(key, block):
    d = Cipher(algorithms.AES(key), modes.ECB()).decryptor()
    return d.update(block) + d.finalize()

def cmac4(key, msg):
    c = CMAC(algorithms.AES(key)); c.update(msg)
    return c.finalize()[:4]

def le(n, size):  return n.to_bytes(size, "little")
def unle(b):      return int.from_bytes(b, "little")

def crypt_payload(app_skey, devaddr, fcnt, uplink, data):
    """FRMPayload: XOR con keystream AES (simetrico: sirve cifrar y descifrar)."""
    out = bytearray()
    for i in range((len(data) + 15) // 16):
        a = bytes([0x01, 0, 0, 0, 0, 0 if uplink else 1]) + le(devaddr, 4) + le(fcnt, 4) + bytes([0, i + 1])
        ks = aes_enc(app_skey, a)
        chunk = data[i * 16:(i + 1) * 16]
        out += bytes(x ^ y for x, y in zip(chunk, ks))
    return bytes(out)

def data_mic(nwk_skey, devaddr, fcnt, uplink, msg):
    b0 = bytes([0x49, 0, 0, 0, 0, 0 if uplink else 1]) + le(devaddr, 4) + le(fcnt, 4) + bytes([0, len(msg)])
    return cmac4(nwk_skey, b0 + msg)

# ---------------------------------------------------------------- decodificacion de aplicacion
def decode_payload(p):
    """Payload de 7 bytes del nodo RF3 (little-endian)."""
    if len(p) < 7:
        return {"raw": p.hex(), "error": "payload corto"}
    t, h, mov, cnt = struct.unpack("<hHBH", p[:7])
    return {
        "temp_c": None if t == 0x7FFF else t / 100.0,
        "hum_pct": None if h == 0xFFFF else h / 100.0,
        "mov": mov,
        "cnt": cnt,
    }

# ---------------------------------------------------------------- servidor
class NetworkServer:
    def __init__(self, send_cb, state_file=STATE_FILE, log_file=UPLINK_LOG, on_uplink=None, quiet=False):
        self.send_cb = send_cb            # send_cb(delay_ms, frame_bytes)
        self.state_file, self.log_file = state_file, log_file
        self.on_uplink = on_uplink
        self.quiet = quiet
        self.lock = threading.Lock()
        self.state = {"join_nonce": 0, "next_addr": 1, "sessions": {}}
        if os.path.exists(state_file):
            with open(state_file) as f:
                self.state = json.load(f)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def log(self, *a):
        if not self.quiet:
            print(time.strftime("%H:%M:%S"), *a, flush=True)

    def save(self):
        tmp = self.state_file + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.state, f, indent=1)
        os.replace(tmp, self.state_file)

    # -- entrada principal
    def handle_frame(self, frame, rssi=None, snr=None):
        with self.lock:
            if len(frame) < 12:
                return
            mtype = frame[0] >> 5
            if mtype == 0b000:
                self.handle_join(frame, rssi, snr)
            elif mtype in (0b010, 0b100):
                self.handle_data(frame, rssi, snr)
            else:
                self.log("trama ignorada, MType", mtype)

    # -- Join
    def handle_join(self, f, rssi, snr):
        if len(f) != 23:
            self.log("join-request con longitud rara", len(f)); return
        join_eui = unle(f[1:9]); dev_eui = unle(f[9:17]); dev_nonce = unle(f[17:19])
        dev_key = "%016X" % dev_eui
        dev = DEVICES.get(dev_key)
        if not dev:
            self.log("join de DevEUI desconocido", dev_key); return
        app_key = bytes.fromhex(dev["app_key"])
        if cmac4(app_key, f[:19]) != f[19:23]:
            self.log("join MIC invalido (AppKey distinta?)", dev_key); return
        old = self.state["sessions"].get(dev_key)
        if old and dev_nonce in old.get("seen_nonces", []):
            self.log("AVISO: DevNonce %d repetido (nodo reinicio sin persistir?); se acepta en modo laboratorio" % dev_nonce)
        self.state["join_nonce"] += 1
        jn = self.state["join_nonce"]
        addr = 0x01000000 | self.state["next_addr"]
        self.state["next_addr"] += 1

        def derive(tag):
            blk = bytes([tag]) + le(jn, 3) + le(NET_ID, 3) + le(dev_nonce, 2)
            return aes_enc(app_key, blk.ljust(16, b"\0"))
        nwk, app = derive(0x01), derive(0x02)

        # Join-Accept: DLSettings=0 (RX1 offset 0, RX2 DR0), RxDelay=0 (1 s), sin CFList
        body = le(jn, 3) + le(NET_ID, 3) + le(addr, 4) + bytes([0x00, 0x00])
        mic = cmac4(app_key, bytes([0x20]) + body)
        ja = bytes([0x20]) + aes_dec(app_key, (body + mic))   # el servidor "descifra"; el nodo "cifra"
        sess = {"name": dev["name"], "devaddr": addr, "nwkskey": nwk.hex(), "appskey": app.hex(),
                "fcnt_up": -1, "seen_nonces": (old or {}).get("seen_nonces", [])[-50:] + [dev_nonce]}
        self.state["sessions"][dev_key] = sess
        self.save()
        self.log("JOIN ok", dev["name"], "DevAddr=%08X" % addr, "DevNonce=%d" % dev_nonce, "rssi=%s snr=%s" % (rssi, snr))
        self.send_cb(RX1_DELAY_JOIN_MS, ja)

    # -- Datos
    def handle_data(self, f, rssi, snr):
        devaddr = unle(f[1:5]); fctrl = f[5]; fcnt16 = unle(f[6:8]); optlen = fctrl & 0x0F
        sess_key = next((k for k, s in self.state["sessions"].items() if s["devaddr"] == devaddr), None)
        if not sess_key:
            self.log("uplink de DevAddr desconocido %08X" % devaddr); return
        s = self.state["sessions"][sess_key]
        # reconstruir FCnt de 32 bits
        last = s["fcnt_up"] if s["fcnt_up"] >= 0 else 0
        fcnt = (last & 0xFFFF0000) | fcnt16
        if fcnt < last: fcnt += 0x10000
        nwk = bytes.fromhex(s["nwkskey"]); app = bytes.fromhex(s["appskey"])
        if data_mic(nwk, devaddr, fcnt, True, f[:-4]) != f[-4:]:
            self.log("MIC de datos invalido (FCnt=%d)" % fcnt); return
        if fcnt <= s["fcnt_up"]:
            self.log("FCnt repetido/atrasado %d <= %d: descartado (replay)" % (fcnt, s["fcnt_up"])); return
        s["fcnt_up"] = fcnt
        pos = 8 + optlen
        rec = {"ts": time.time(), "node": s["name"], "devaddr": "%08X" % devaddr, "fcnt": fcnt,
               "rssi": rssi, "snr": snr, "confirmed": (f[0] >> 5) == 0b100}
        if len(f) - 4 > pos:
            port = f[pos]; frm = f[pos + 1:-4]
            if port > 0:
                plain = crypt_payload(app, devaddr, fcnt, True, frm)
                rec.update({"fport": port, "payload_hex": plain.hex(), **decode_payload(plain)})
        self.save()
        self.log("UPLINK", json.dumps(rec))
        with open(self.log_file, "a") as lf:
            lf.write(json.dumps(rec) + "\n")
        try:
            self.sock.sendto(json.dumps(rec).encode(), UDP_PUBLISH)
        except OSError:
            pass
        if self.on_uplink:
            self.on_uplink(rec)
        if rec["confirmed"]:
            self.log("(uplink confirmado: este servidor minimo no envia ACK; usa sin confirmar)")

# ---------------------------------------------------------------- serie
def run_serial(port, baud):
    import serial
    ser = serial.Serial(port, baud, timeout=0.2)
    wlock = threading.Lock()
    def send(delay_ms, frame):
        with wlock:
            ser.write(("TX %d %s\n" % (delay_ms, frame.hex())).encode())
    ns = NetworkServer(send)
    ns.log("escuchando en", port)
    while True:
        line = ser.readline().decode(errors="replace").strip()
        if not line:
            continue
        p = line.split()
        if p[0] == "RX" and len(p) >= 4:
            try:
                ns.handle_frame(bytes.fromhex(p[1]), int(p[2]), float(p[3]))
            except Exception as e:                      # nunca tumbar el servidor por una trama rara
                ns.log("error procesando trama:", repr(e))
        else:
            ns.log("[fe]", line)

# ---------------------------------------------------------------- autoprueba (simulador de nodo)
def selftest():
    """Simula un nodo siguiendo las formulas de RadioLib/LoRaWAN 1.0.x. NO es una prueba independiente
    del firmware: valida la logica del servidor contra la especificacion que implementa el simulador."""
    import tempfile
    d = tempfile.mkdtemp()
    sent = []
    ns = NetworkServer(lambda dl, fr: sent.append((dl, fr)), os.path.join(d, "s.json"), os.path.join(d, "l.jsonl"), quiet=True)
    dev_eui, key_hex = "70B3D57ED0000001", DEVICES["70B3D57ED0000001"]["app_key"]
    key = bytes.fromhex(key_hex)
    jr = bytes([0x00]) + le(1, 8) + le(int(dev_eui, 16), 8) + le(0, 2)
    jr += cmac4(key, jr)
    ns.handle_frame(jr)
    assert sent and sent[0][0] == 5000, "no hubo join-accept"
    ja = sent.pop()[1]
    dec = aes_enc(key, ja[1:])                        # el nodo "cifra" para descifrar
    body, mic = dec[:-4], dec[-4:]
    assert cmac4(key, bytes([0x20]) + body) == mic, "MIC del join-accept"
    jn, devaddr = unle(body[0:3]), unle(body[6:10])
    def derive(tag): return aes_enc(key, (bytes([tag]) + le(jn, 3) + le(NET_ID, 3) + le(0, 2)).ljust(16, b"\0"))
    nwk, app = derive(1), derive(2)
    got = []
    ns.on_uplink = got.append
    for cnt, (t, h, mov) in enumerate([(2312, 5540, 0), (-150, 9999, 1), (0x7FFF, 0xFFFF, 0)]):
        plain = struct.pack("<hHBH", t, h, mov, cnt)
        fcnt = cnt
        frm = crypt_payload(app, devaddr, fcnt, True, plain)
        msg = bytes([0x40]) + le(devaddr, 4) + bytes([0]) + le(fcnt, 2) + bytes([1]) + frm
        ns.handle_frame(msg + data_mic(nwk, devaddr, fcnt, True, msg))
    assert len(got) == 3, got
    assert got[0]["temp_c"] == 23.12 and got[0]["hum_pct"] == 55.4 and got[0]["mov"] == 0
    assert got[1]["temp_c"] == -1.5 and got[1]["mov"] == 1
    assert got[2]["temp_c"] is None and got[2]["hum_pct"] is None
    # replay y MIC corrupto deben descartarse
    ns.handle_frame(msg + data_mic(nwk, devaddr, 2, True, msg)); assert len(got) == 3
    bad = bytearray(msg + data_mic(nwk, devaddr, 2, True, msg)); bad[-1] ^= 1
    ns.handle_frame(bytes(bad)); assert len(got) == 3
    # FCnt con rollover de 16 bits
    ns.state["sessions"][dev_eui]["fcnt_up"] = 65535
    plain = struct.pack("<hHBH", 2000, 5000, 0, 9)
    frm = crypt_payload(app, devaddr, 65536, True, plain)
    msg = bytes([0x40]) + le(devaddr, 4) + bytes([0]) + le(65536 & 0xFFFF, 2) + bytes([1]) + frm
    ns.handle_frame(msg + data_mic(nwk, devaddr, 65536, True, msg)); assert len(got) == 4 and got[3]["fcnt"] == 65536
    # join con AppKey equivocada -> sin respuesta
    jr2 = bytes([0x00]) + le(1, 8) + le(int(dev_eui, 16), 8) + le(1, 2)
    jr2 += cmac4(bytes(16), jr2); ns.handle_frame(jr2); assert not sent
    print("selftest OK: join, MIC, descifrado, replay, rollover FCnt")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port"); ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest: selftest()
    elif a.port: run_serial(a.port, a.baud)
    else: ap.error("indica --port o --selftest")
