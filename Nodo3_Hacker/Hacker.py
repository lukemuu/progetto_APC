#!/usr/bin/env python3
"""
HC12 Relay – STM32 Fixed-Packet Edition (MANUAL REPLAY)
======================================================
  - Trasmettitore (Chiave)   → manda PACKET_SIZE=16 byte via DMA
  - Ricevitore    (Serratura) → attende esattamente 16 byte via DMA
"""

import serial
import serial.tools.list_ports
import argparse
import time
import sys
import signal
import logging
from datetime import datetime

# ─── COSTANTI ─────────────────────────────────────────────────────────────────
PACKET_SIZE = 32
READ_TIMEOUT = 2.0

# ─── Logging ──────────────────────────────────────────────────────────────────
# Il FileHandler salva tutto (DEBUG+), il terminale mostra solo WARNING ed errori
log_filename = f"hc12_stm32_manual_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

file_handler = logging.FileHandler(log_filename)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.WARNING)   # solo errori reali sul terminale
console_handler.setFormatter(logging.Formatter("⚠️  %(message)s"))

logging.basicConfig(level=logging.DEBUG, handlers=[file_handler, console_handler])
log = logging.getLogger("HC12-STM32")

stats = {"rx": 0, "tx": 0, "errori": 0}

# ─── Utilità ──────────────────────────────────────────────────────────────────
def decodifica(raw: bytes) -> str:
    return "".join(chr(b) if 32 <= b < 127 else f"[{b:02X}]" for b in raw)

def elenca_porte() -> list[str]:
    return [p.device for p in serial.tools.list_ports.comports()]

def scegli_porta() -> str:
    porte = elenca_porte()
    if not porte:
        print("✖  Nessuna porta seriale trovata. Verifica il cavo USB-UART.")
        sys.exit(1)
    print("\n📡 Porte disponibili:")
    for i, p in enumerate(porte):
        print(f"   [{i}] {p}")
    while True:
        try:
            idx = int(input("\nScegli numero porta: "))
            if 0 <= idx < len(porte):
                return porte[idx]
        except ValueError:
            pass
        print("   Indice non valido, riprova.")

def apri_seriale(porta: str, baud: int) -> serial.Serial:
    try:
        ser = serial.Serial(
            port=porta,
            baudrate=baud,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=READ_TIMEOUT,
        )
        log.debug(f"Porta aperta: {porta} @ {baud} baud")
        return ser
    except serial.SerialException as e:
        print(f"✖  Impossibile aprire {porta}: {e}")
        sys.exit(1)

# ─── Loop principale ──────────────────────────────────────────────────────────
def relay_loop(ser: serial.Serial):
    print("▶  In ascolto — premi il pulsante sulla CHIAVE hardware...\n")

    while True:
        try:
            raw = ser.read(PACKET_SIZE)
        except serial.SerialException as e:
            log.error(f"Errore lettura seriale: {e}")
            stats["errori"] += 1
            time.sleep(0.5)
            continue

        if len(raw) == 0:
            continue

        stats["rx"] += 1
        testo_utile = raw.rstrip(b"\x00").decode("ascii", errors="replace")
        hex_str     = raw.hex(" ").upper()

        # Log dettagliato solo su file
        log.debug(f"RX #{stats['rx']:04d} | testo={testo_utile!r} | hex={hex_str}")
        if len(raw) < PACKET_SIZE:
            log.warning(f"Pacchetto incompleto: {len(raw)}/{PACKET_SIZE} byte")

        # Output terminale: essenziale e pulito
        print(f"{'─'*50}")
        print(f"  📥  Pacchetto #{stats['rx']:04d} intercettato")
        print(f"  Testo : {testo_utile!r}")
        print(f"  HEX   : {hex_str}")
        if len(raw) < PACKET_SIZE:
            print(f"  ⚠️   Solo {len(raw)}/{PACKET_SIZE} byte ricevuti")
        print(f"{'─'*50}")
        print("  [INVIO]/R → Replay   |   N → Nuovo pacchetto   |   Q → Esci")

        # --- SOTTO-LOOP: replay multipli sullo stesso pacchetto ---
        while True:
            scelta = input("\n  Comando: ").strip().upper()

            if scelta == "Q":
                gestore_uscita(None, None)

            elif scelta == "N":
                print(f"\n▶  In ascolto — premi il pulsante sulla CHIAVE hardware...\n")
                log.debug("Operatore ha scelto: nuovo pacchetto")
                break

            else:
                try:
                    scritti = ser.write(raw)
                    ser.flush()
                    stats["tx"] += 1
                    log.debug(f"TX #{stats['tx']:04d} | {scritti} byte | hex={hex_str}")
                    print(f"  ✔  Replay #{stats['tx']:04d} inviato  ({scritti} byte)")
                except serial.SerialException as e:
                    log.error(f"Errore scrittura replay: {e}")
                    stats["errori"] += 1
                    print(f"  ✖  Errore invio: {e}")

def gestore_uscita(sig, frame):
    print(f"\n{'═'*45}")
    print(f"  Intercettati  : {stats['rx']}")
    print(f"  Replay inviati: {stats['tx']}")
    print(f"  Errori        : {stats['errori']}")
    print(f"  Log salvato   : {log_filename}")
    print(f"{'═'*45}\n")
    sys.exit(0)

# ─── Entry point ──────────────────────────────────────────────────────────────
def main():
    global PACKET_SIZE

    parser = argparse.ArgumentParser(
        description="HC12 Manual Relay per STM32",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--port", "-p", default=None, help="Porta seriale (es. COM3 o /dev/ttyUSB0)")
    parser.add_argument("--baud", "-b", default=9600, type=int, help="Baud rate")
    parser.add_argument("--packet-size", default=PACKET_SIZE, type=int, help="Dimensione pacchetto")
    args = parser.parse_args()

    PACKET_SIZE = args.packet_size
    porta = args.port or scegli_porta()
    signal.signal(signal.SIGINT, gestore_uscita)
    ser = apri_seriale(porta, args.baud)

    print(f"""
╔═══════════════════════════════════════════════╗
║    HC12 REPLAY TOOL – Modalità Manuale        ║
╠═══════════════════════════════════════════════╣
║  Porta       : {porta:<30}║
║  Baud rate   : {args.baud:<30}║
║  Packet size : {PACKET_SIZE:<28} B ║
║  Log file    : {log_filename:<30}║
╚═══════════════════════════════════════════════╝
""")

    try:
        relay_loop(ser)
    finally:
        ser.close()
        log.debug("Porta seriale chiusa.")

if __name__ == "__main__":
    main()