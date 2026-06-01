#!/usr/bin/env python3
"""
HC12 Hacker Dashboard — Nodo 3
================================
GUI completa in un singolo file Python.
Dipendenze: pip install customtkinter pyserial

Uso:
    python hacker_dashboard.py
"""

import threading
import time
import logging
import sys
from datetime import datetime

import serial
import serial.tools.list_ports
import customtkinter as ctk
from tkinter import messagebox

# ─── Tema dark ────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

# ─── Palette colori ───────────────────────────────────────────────────────────
C = {
    "bg":         "#0a0c0f",
    "panel":      "#111519",
    "panel2":     "#0e1217",
    "border":     "#1e2830",
    "accent":     "#00e5c8",
    "accent_dim": "#007a6e",
    "danger":     "#ff3b3b",
    "warn":       "#f59e0b",
    "success":    "#22c55e",
    "text":       "#c8d8e4",
    "text_mid":   "#7a9ab0",
    "text_dim":   "#4a6070",
    "btn_fg":     "#0a0c0f",
}

FONT_MONO    = ("Courier New", 11)
FONT_MONO_SM = ("Courier New", 10)
FONT_UI      = ("Segoe UI", 11)
FONT_UI_SM   = ("Segoe UI", 10)
FONT_UI_LG   = ("Segoe UI", 13, "bold")
FONT_TITLE   = ("Segoe UI", 9, "bold")

# ─── Logging ──────────────────────────────────────────────────────────────────
log_filename = f"hc12_dashboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("HC12-GUI")


# ─── Utility ──────────────────────────────────────────────────────────────────
def hex_str(raw: bytes) -> str:
    """Stringa HEX separata da spazi: '41 43 4B 20...'"""
    return " ".join(f"{b:02X}" for b in raw)


def ascii_str(raw: bytes) -> str:
    """
    Decodifica stile hex-editor:
      - byte stampabili (32-126) → carattere ASCII
      - null (0x00)              → · (padding visivo)
      - altri byte binari/ctrl  → [XX] (valore hex esplicito)
    Equivalente CLI: decodifica() + rstrip(b'\\x00')
    """
    result = []
    for b in raw:
        if 32 <= b < 127:
            result.append(chr(b))
        elif b == 0x00:
            result.append("·")
        else:
            result.append(f"[{b:02X}]")
    return "".join(result)


def testo_utile(raw: bytes) -> str:
    """
    Testo decodificato senza null di coda (come nel CLI).
    Usato per il campo 'Testo' nel pannello dettaglio.
    """
    return raw.rstrip(b"\x00").decode("ascii", errors="replace")


def ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def porta_attiva() -> str:
    porte = [p.device for p in serial.tools.list_ports.comports()]
    return porte[0] if porte else ""


# ══════════════════════════════════════════════════════════════════════════════
#  APPLICAZIONE PRINCIPALE
# ══════════════════════════════════════════════════════════════════════════════
class HackerDashboard(ctk.CTk):

    PACKET_SIZE_DEFAULT = 32

    def __init__(self):
        super().__init__()

        self.title("HC-12 Hacker Dashboard — Nodo 3")
        self.geometry("1280x780")
        self.minsize(1100, 680)
        self.configure(fg_color=C["bg"])

        # ── stato ──
        self._ser: serial.Serial | None = None
        self._connected = False
        self._rx_thread: threading.Thread | None = None
        self._stop_rx = threading.Event()

        self._packets: list[dict] = []   # {id, raw, hex, ascii, testo, time, replayed, replay_count}
        self._selected_idx: int | None = None
        self._stats = {"rx": 0, "tx": 0, "err": 0}
        self._session_start: float | None = None

        self._build_ui()
        self._refresh_ports()
        self._tick()

    # ──────────────────────────────────────────────────────────────────────────
    #  COSTRUZIONE UI
    # ──────────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        self.grid_columnconfigure(0, weight=0)   # sidebar
        self.grid_columnconfigure(1, weight=1)   # lista pacchetti
        self.grid_columnconfigure(2, weight=0)   # pannello dettaglio
        self.grid_rowconfigure(0, weight=0)      # header
        self.grid_rowconfigure(1, weight=1)      # contenuto
        self.grid_rowconfigure(2, weight=0)      # status bar

        self._build_header()
        self._build_sidebar()
        self._build_packet_list()
        self._build_right_panel()
        self._build_statusbar()

    # ── HEADER ────────────────────────────────────────────────────────────────
    def _build_header(self):
        hdr = ctk.CTkFrame(self, fg_color=C["panel"], corner_radius=0, height=60)
        hdr.grid(row=0, column=0, columnspan=3, sticky="ew")
        hdr.grid_propagate(False)
        hdr.grid_columnconfigure(1, weight=1)

        title_f = ctk.CTkFrame(hdr, fg_color="transparent")
        title_f.grid(row=0, column=0, padx=20, pady=10, sticky="w")
        ctk.CTkLabel(title_f, text="HC-12 DASHBOARD",
                     font=("Segoe UI", 16, "bold"), text_color=C["accent"]).pack(anchor="w")
        ctk.CTkLabel(title_f, text="Nodo 3 — Hacker Interface",
                     font=FONT_UI_SM, text_color=C["text_mid"]).pack(anchor="w")

        sep = ctk.CTkFrame(hdr, fg_color=C["border"], width=1)
        sep.grid(row=0, column=1, padx=(0, 20), pady=12, sticky="ns")

        stats_f = ctk.CTkFrame(hdr, fg_color="transparent")
        stats_f.grid(row=0, column=1, padx=20, pady=10, sticky="w")

        self._lbl_conn    = self._stat_chip(stats_f, "●",   C["text_dim"], "Disconnesso", 0)
        self._lbl_rx_val  = self._stat_chip(stats_f, "RX",  C["accent"],   "0", 1)
        self._lbl_tx_val  = self._stat_chip(stats_f, "TX",  C["warn"],     "0", 2)
        self._lbl_err_val = self._stat_chip(stats_f, "ERR", C["danger"],   "0", 3)

        self._lbl_clock = ctk.CTkLabel(hdr, text="", font=FONT_UI_SM,
                                        text_color=C["text_dim"])
        self._lbl_clock.grid(row=0, column=2, padx=20, pady=10, sticky="e")

    def _stat_chip(self, parent, label, color, init_val, col):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.grid(row=0, column=col, padx=14, pady=0)
        ctk.CTkLabel(f, text=label, font=FONT_UI_SM, text_color=color).pack(side="left", padx=(0, 4))
        lbl = ctk.CTkLabel(f, text=init_val, font=("Segoe UI", 14, "bold"),
                           text_color=C["text"])
        lbl.pack(side="left")
        return lbl

    # ── SIDEBAR ───────────────────────────────────────────────────────────────
    def _build_sidebar(self):
        sb = ctk.CTkFrame(self, fg_color=C["panel"], corner_radius=0, width=260)
        sb.grid(row=1, column=0, sticky="nsew")
        sb.grid_propagate(False)
        sb.grid_rowconfigure(5, weight=1)

        self._section(sb, "CONFIGURAZIONE PORTA", row=0)

        cfg = ctk.CTkFrame(sb, fg_color="transparent")
        cfg.grid(row=1, column=0, padx=12, pady=(4, 8), sticky="ew")
        cfg.grid_columnconfigure(0, weight=1)

        self._lbl_field(cfg, "Porta seriale", 0)
        port_row = ctk.CTkFrame(cfg, fg_color="transparent")
        port_row.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        port_row.grid_columnconfigure(0, weight=1)
        self._cmb_port = ctk.CTkComboBox(port_row, values=[], width=160,
                                          fg_color=C["bg"], border_color=C["border"],
                                          button_color=C["border"], text_color=C["accent"],
                                          font=FONT_MONO_SM, dropdown_fg_color=C["panel"])
        self._cmb_port.grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(port_row, text="↺", width=30, fg_color=C["border"],
                      hover_color=C["border"], text_color=C["text_mid"],
                      command=self._refresh_ports).grid(row=0, column=1, padx=(4, 0))

        self._lbl_field(cfg, "Baud rate", 2)
        self._cmb_baud = ctk.CTkComboBox(cfg, values=["9600", "19200", "38400", "57600", "115200"],
                                          fg_color=C["bg"], border_color=C["border"],
                                          button_color=C["border"], text_color=C["accent"],
                                          font=FONT_MONO_SM, dropdown_fg_color=C["panel"])
        self._cmb_baud.set("9600")
        self._cmb_baud.grid(row=3, column=0, sticky="ew", pady=(0, 8))

        self._lbl_field(cfg, "Packet size (byte)", 4)
        self._ent_psize = ctk.CTkEntry(cfg, fg_color=C["bg"], border_color=C["border"],
                                        text_color=C["accent"], font=FONT_MONO_SM)
        self._ent_psize.insert(0, str(self.PACKET_SIZE_DEFAULT))
        self._ent_psize.grid(row=5, column=0, sticky="ew", pady=(0, 10))

        self._btn_conn = ctk.CTkButton(cfg, text="CONNETTI",
                                        fg_color="transparent",
                                        border_width=1, border_color=C["accent"],
                                        text_color=C["accent"], hover_color=C["panel2"],
                                        font=("Segoe UI", 12, "bold"),
                                        command=self._toggle_connect)
        self._btn_conn.grid(row=6, column=0, sticky="ew")

        sep = ctk.CTkFrame(sb, fg_color=C["border"], height=1)
        sep.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        self._section(sb, "STATO SISTEMA", row=3)

        sys_f = ctk.CTkFrame(sb, fg_color="transparent")
        sys_f.grid(row=4, column=0, padx=12, pady=(4, 0), sticky="ew")
        sys_f.grid_columnconfigure(1, weight=1)

        self._sys_labels = {}
        fields = [("Porta", "—"), ("Baud", "—"), ("Packet size", "—"),
                  ("Selezionato", "Nessuno"), ("Ultimo replay", "—"), ("Sessione", "—")]
        for i, (k, v) in enumerate(fields):
            ctk.CTkLabel(sys_f, text=k, font=FONT_UI_SM,
                         text_color=C["text_dim"]).grid(row=i, column=0, sticky="w", pady=3)
            lbl = ctk.CTkLabel(sys_f, text=v, font=FONT_MONO_SM, text_color=C["text_mid"])
            lbl.grid(row=i, column=1, sticky="e", pady=3)
            self._sys_labels[k] = lbl

        ctk.CTkFrame(sb, fg_color="transparent").grid(row=5, column=0, sticky="nsew")

    def _section(self, parent, text, row):
        ctk.CTkFrame(parent, fg_color=C["border"], height=1).grid(row=row, column=0, sticky="ew")
        ctk.CTkLabel(parent, text=text, font=FONT_TITLE,
                     text_color=C["text_dim"]).grid(row=row, column=0, padx=12, pady=(10, 2), sticky="w")

    def _lbl_field(self, parent, text, row):
        ctk.CTkLabel(parent, text=text, font=FONT_UI_SM,
                     text_color=C["text_dim"]).grid(row=row, column=0, sticky="w", pady=(0, 3))

    # ── LISTA PACCHETTI ───────────────────────────────────────────────────────
    def _build_packet_list(self):
        container = ctk.CTkFrame(self, fg_color=C["bg"], corner_radius=0)
        container.grid(row=1, column=1, sticky="nsew")
        container.grid_rowconfigure(1, weight=1)
        container.grid_columnconfigure(0, weight=1)

        bar = ctk.CTkFrame(container, fg_color=C["panel"], corner_radius=0, height=40)
        bar.grid(row=0, column=0, sticky="ew")
        bar.grid_propagate(False)
        bar.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(bar, text="PACCHETTI INTERCETTATI", font=FONT_TITLE,
                     text_color=C["text_dim"]).grid(row=0, column=0, padx=16, pady=10, sticky="w")
        self._lbl_pkt_count = ctk.CTkLabel(bar, text="0 pacchetti",
                                            font=FONT_UI_SM, text_color=C["accent"])
        self._lbl_pkt_count.grid(row=0, column=1, padx=8, sticky="w")
        ctk.CTkButton(bar, text="Pulisci", width=70,
                      fg_color=C["border"], hover_color=C["panel2"],
                      text_color=C["text_mid"], font=FONT_UI_SM,
                      command=self._clear_packets).grid(row=0, column=2, padx=12, pady=6)

        self._pkt_frame = ctk.CTkScrollableFrame(
            container, fg_color=C["bg"],
            scrollbar_button_color=C["border"],
            scrollbar_button_hover_color=C["border"])
        self._pkt_frame.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        self._pkt_frame.grid_columnconfigure(0, weight=1)

        self._empty_lbl = ctk.CTkLabel(
            self._pkt_frame,
            text="📡  In ascolto sul canale 433 MHz\n\nConnetti la porta seriale e premi\nil pulsante sulla CHIAVE hardware",
            font=FONT_UI, text_color=C["text_dim"],
            justify="center")
        self._empty_lbl.grid(row=0, column=0, pady=80)

    def _add_packet_card(self, packet: dict):
        """Aggiunge una card nella lista. Chiamato dal thread RX via after()."""
        if self._empty_lbl.winfo_exists():
            self._empty_lbl.grid_forget()

        idx = packet["id"]
        row_n = len(self._pkt_frame.winfo_children())

        card = ctk.CTkFrame(self._pkt_frame, fg_color=C["panel"],
                             border_width=1, border_color=C["border"],
                             corner_radius=4)
        card.grid(row=row_n, column=0, sticky="ew", pady=(0, 6), padx=4)
        card.grid_columnconfigure(1, weight=1)
        packet["card"] = card

        # accent strip laterale
        strip = ctk.CTkFrame(card, fg_color=C["border"], width=3, corner_radius=0)
        strip.grid(row=0, column=0, rowspan=4, sticky="ns", padx=(0, 8))
        packet["strip"] = strip

        # header: id + replay tag + timestamp
        hdr = ctk.CTkFrame(card, fg_color="transparent")
        hdr.grid(row=0, column=1, sticky="ew", pady=(6, 2))
        hdr.grid_columnconfigure(1, weight=1)

        id_lbl = ctk.CTkLabel(hdr, text="PKT  ", font=FONT_UI_SM, text_color=C["text_dim"])
        id_lbl.grid(row=0, column=0, sticky="w")
        id_num = ctk.CTkLabel(hdr, text=f"#{idx+1:04d}", font=FONT_UI_SM, text_color=C["accent"])
        id_num.grid(row=0, column=1, sticky="w")
        packet["replay_tag_lbl"] = ctk.CTkLabel(hdr, text="", font=FONT_UI_SM, text_color=C["warn"])
        packet["replay_tag_lbl"].grid(row=0, column=2, padx=(8, 0))
        ctk.CTkLabel(hdr, text=packet["time"], font=FONT_MONO_SM,
                     text_color=C["text_dim"]).grid(row=0, column=3, padx=8)

        # riga HEX
        hex_lbl = ctk.CTkLabel(card, text=packet["hex"], font=FONT_MONO_SM,
                                text_color=C["text_mid"], anchor="w", justify="left",
                                wraplength=580)
        hex_lbl.grid(row=1, column=1, sticky="ew", pady=(0, 2))

        # riga ASCII (con decodifica arricchita: [XX] per byte non-ASCII)
        ascii_lbl = ctk.CTkLabel(card, text=packet["ascii"], font=FONT_MONO_SM,
                                  text_color=C["accent_dim"], anchor="w", justify="left",
                                  wraplength=580)
        ascii_lbl.grid(row=2, column=1, sticky="ew", pady=(0, 2))

        # riga TESTO (payload pulito, senza null di coda)
        testo_lbl = ctk.CTkLabel(card, text=f"» {packet['testo']}", font=FONT_MONO_SM,
                                  text_color=C["accent"], anchor="w", justify="left",
                                  wraplength=580)
        testo_lbl.grid(row=3, column=1, sticky="ew", pady=(0, 6))

        # click → seleziona
        for w in [card, strip, hex_lbl, ascii_lbl, testo_lbl, hdr, id_lbl, id_num]:
            w.bind("<Button-1>", lambda e, i=idx: self._select_packet(i))

        self._lbl_pkt_count.configure(text=f"{len(self._packets)} pacchetti")

    def _select_packet(self, idx: int):
        # deseleziona precedente
        if self._selected_idx is not None and self._selected_idx < len(self._packets):
            prev = self._packets[self._selected_idx]
            if "strip" in prev:
                color = C["warn"] if prev["replayed"] else C["border"]
                prev["strip"].configure(fg_color=color)
            if "card" in prev:
                prev["card"].configure(border_color=C["border"])

        self._selected_idx = idx
        p = self._packets[idx]
        if "strip" in p:
            p["strip"].configure(fg_color=C["accent"])
        if "card" in p:
            p["card"].configure(border_color=C["accent"])

        self._render_detail(p)
        self._btn_replay.configure(state="normal")
        self._sys_labels["Selezionato"].configure(text=f"#{idx+1:04d}", text_color=C["accent"])

    def _refresh_card(self, packet: dict):
        if "replay_tag_lbl" in packet:
            packet["replay_tag_lbl"].configure(
                text=f"REPLAY ×{packet['replay_count']}" if packet["replayed"] else "")
        if "strip" in packet and packet["id"] != self._selected_idx:
            packet["strip"].configure(fg_color=C["warn"] if packet["replayed"] else C["border"])
        if "card" in packet and packet["id"] != self._selected_idx:
            packet["card"].configure(
                border_color="rgba(245,158,11,0.3)" if packet["replayed"] else C["border"])

    # ── PANNELLO DESTRO ───────────────────────────────────────────────────────
    def _build_right_panel(self):
        rp = ctk.CTkFrame(self, fg_color=C["panel"], corner_radius=0, width=320)
        rp.grid(row=1, column=2, sticky="nsew")
        rp.grid_propagate(False)
        rp.grid_rowconfigure(3, weight=1)
        rp.grid_columnconfigure(0, weight=1)

        self._section(rp, "PACCHETTO SELEZIONATO", row=0)

        self._detail_frame = ctk.CTkScrollableFrame(
            rp, fg_color="transparent", height=280,
            scrollbar_button_color=C["border"])
        self._detail_frame.grid(row=1, column=0, sticky="ew", padx=8, pady=(4, 0))
        self._detail_frame.grid_columnconfigure(0, weight=1)

        self._detail_placeholder = ctk.CTkLabel(
            self._detail_frame, text="— Seleziona un pacchetto —",
            font=FONT_UI_SM, text_color=C["text_dim"])
        self._detail_placeholder.grid(row=0, column=0, pady=20)

        sep = ctk.CTkFrame(rp, fg_color=C["border"], height=1)
        sep.grid(row=2, column=0, sticky="ew", pady=(8, 0))

        self._section(rp, "REPLAY ATTACK", row=2)

        atk = ctk.CTkFrame(rp, fg_color="transparent")
        atk.grid(row=2, column=0, padx=12, pady=(28, 0), sticky="ew")
        atk.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(atk, text="Ripetizioni:", font=FONT_UI_SM,
                     text_color=C["text_dim"]).grid(row=0, column=0, sticky="w", padx=(0, 8))
        self._ent_repeat = ctk.CTkEntry(atk, width=60, fg_color=C["bg"],
                                         border_color=C["border"],
                                         text_color=C["text"], font=FONT_MONO_SM)
        self._ent_repeat.insert(0, "1")
        self._ent_repeat.grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(atk, text="× invii", font=FONT_UI_SM,
                     text_color=C["text_dim"]).grid(row=0, column=2, padx=(6, 0))

        self._btn_replay = ctk.CTkButton(
            rp, text="⚡  REPLAY ATTACK",
            fg_color="transparent", border_width=1, border_color=C["danger"],
            text_color=C["danger"], hover_color="#2a0a0a",
            font=("Segoe UI", 13, "bold"),
            state="disabled",
            command=self._confirm_replay)
        self._btn_replay.grid(row=3, column=0, padx=12, pady=(10, 0), sticky="ew")

        sep2 = ctk.CTkFrame(rp, fg_color=C["border"], height=1)
        sep2.grid(row=4, column=0, sticky="ew", pady=(12, 0))

        self._section(rp, "CONSOLE LOG", row=4)

        self._log_box = ctk.CTkTextbox(
            rp, fg_color=C["bg"], text_color=C["text_mid"],
            font=FONT_MONO_SM, border_width=0, corner_radius=0,
            state="disabled", wrap="word")
        self._log_box.grid(row=5, column=0, sticky="nsew", padx=0, pady=0)
        rp.grid_rowconfigure(5, weight=1)

        self._log_box._textbox.tag_configure("info",    foreground=C["accent"])
        self._log_box._textbox.tag_configure("warn",    foreground=C["warn"])
        self._log_box._textbox.tag_configure("ok",      foreground=C["success"])
        self._log_box._textbox.tag_configure("err",     foreground=C["danger"])
        self._log_box._textbox.tag_configure("dim",     foreground=C["text_dim"])
        self._log_box._textbox.tag_configure("default", foreground=C["text_mid"])

    def _render_detail(self, p: dict):
        """
        Pannello dettaglio con tre sezioni:
          1. Metadati (id, dimensione, testo decodificato)
          2. Hex dump + ASCII per riga (8 byte/riga, stile hex editor)
          3. Info replay se già ritrasmesso
        """
        for w in self._detail_frame.winfo_children():
            w.destroy()

        df = self._detail_frame

        def field(label, value, color=C["text"], row=0):
            ctk.CTkLabel(df, text=label, font=FONT_TITLE,
                         text_color=C["text_dim"]).grid(
                row=row * 2, column=0, sticky="w", pady=(8, 2))
            ctk.CTkLabel(df, text=value, font=FONT_MONO_SM, text_color=color,
                         anchor="w", justify="left", wraplength=270).grid(
                row=row * 2 + 1, column=0, sticky="ew", padx=4)

        field("ID PACCHETTO",  f"#{p['id']+1:04d}  —  {p['time']}", C["accent"], 0)
        field("DIMENSIONE",    f"{len(p['raw'])} byte", C["text"], 1)

        # TESTO — payload utile senza null di coda (da CLI: testo_utile)
        field("TESTO DECODIFICATO", p["testo"] if p["testo"] else "—", C["accent"], 2)

        # separatore prima del dump
        ctk.CTkFrame(df, fg_color=C["border"], height=1).grid(
            row=6, column=0, sticky="ew", pady=(10, 4))

        # intestazione colonne hex dump
        hdr_f = ctk.CTkFrame(df, fg_color="transparent")
        hdr_f.grid(row=7, column=0, sticky="ew")
        ctk.CTkLabel(hdr_f, text="OFF ", font=FONT_MONO_SM,
                     text_color=C["text_dim"], width=36, anchor="w").pack(side="left")
        ctk.CTkLabel(hdr_f, text="HEX                     ",
                     font=FONT_MONO_SM, text_color=C["text_dim"], anchor="w").pack(side="left", padx=(4, 8))
        ctk.CTkLabel(hdr_f, text="ASCII", font=FONT_MONO_SM,
                     text_color=C["text_dim"], anchor="w").pack(side="left")

        ctk.CTkFrame(df, fg_color=C["border"], height=1).grid(
            row=8, column=0, sticky="ew", pady=(0, 4))

        # righe hex + ASCII  (8 byte per riga)
        raw = p["raw"]
        for row_i in range(0, len(raw), 8):
            chunk = raw[row_i:row_i + 8]

            row_f = ctk.CTkFrame(df, fg_color="transparent")
            row_f.grid(row=9 + row_i // 8, column=0, sticky="ew")

            # offset
            ctk.CTkLabel(row_f, text=f"{row_i:04X}",
                         font=FONT_MONO_SM, text_color=C["text_dim"],
                         width=36, anchor="w").pack(side="left")

            # hex bytes (padding a 8 byte fissi per allineamento colonne)
            hex_part = " ".join(f"{b:02X}" for b in chunk)
            hex_part = f"{hex_part:<23}"
            ctk.CTkLabel(row_f, text=hex_part, font=FONT_MONO_SM,
                         text_color=C["text_mid"], anchor="w").pack(side="left", padx=(4, 8))

            # ASCII con colorazione per tipo di byte:
            #   stampabile → accent, null → text_dim, binario → warn
            for b in chunk:
                if 32 <= b < 127:
                    ch, col = chr(b), C["accent"]
                elif b == 0x00:
                    ch, col = "·", C["text_dim"]
                else:
                    ch, col = f"[{b:02X}]", C["warn"]
                ctk.CTkLabel(row_f, text=ch, font=FONT_MONO_SM,
                             text_color=col, anchor="w").pack(side="left")

        # info replay (se già ritrasmesso)
        if p["replayed"]:
            ctk.CTkFrame(df, fg_color=C["border"], height=1).grid(
                row=9 + (len(raw) + 7) // 8, column=0, sticky="ew", pady=(8, 4))
            field("RITRASMISSIONI", f"{p['replay_count']}×", C["warn"],
                  row=5 + (len(raw) + 7) // 8)

    # ── STATUS BAR ────────────────────────────────────────────────────────────
    def _build_statusbar(self):
        sb = ctk.CTkFrame(self, fg_color=C["panel"], corner_radius=0, height=30)
        sb.grid(row=2, column=0, columnspan=3, sticky="ew")
        sb.grid_propagate(False)
        sb.grid_columnconfigure(1, weight=1)

        self._lbl_sb_left = ctk.CTkLabel(sb, text="Porta non connessa",
                                          font=FONT_UI_SM, text_color=C["text_dim"])
        self._lbl_sb_left.grid(row=0, column=0, padx=16, pady=6, sticky="w")

        self._lbl_sb_right = ctk.CTkLabel(sb, text=f"Log: {log_filename}",
                                           font=FONT_UI_SM, text_color=C["text_dim"])
        self._lbl_sb_right.grid(row=0, column=2, padx=16, pady=6, sticky="e")

    # ──────────────────────────────────────────────────────────────────────────
    #  LOGICA CONNESSIONE
    # ──────────────────────────────────────────────────────────────────────────
    def _refresh_ports(self):
        porte = [p.device for p in serial.tools.list_ports.comports()]
        if not porte:
            porte = ["Nessuna porta trovata"]
        self._cmb_port.configure(values=porte)
        self._cmb_port.set(porte[0])

    def _toggle_connect(self):
        if not self._connected:
            self._connect()
        else:
            self._disconnect()

    def _connect(self):
        porta = self._cmb_port.get()
        baud  = int(self._cmb_baud.get())
        try:
            psize = int(self._ent_psize.get())
        except ValueError:
            psize = self.PACKET_SIZE_DEFAULT

        try:
            self._ser = serial.Serial(
                port=porta, baudrate=baud,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=2.0,
            )
        except serial.SerialException as e:
            messagebox.showerror("Errore connessione", str(e))
            return

        self._connected = True
        self._session_start = time.time()
        self._stop_rx.clear()

        self._rx_thread = threading.Thread(
            target=self._rx_loop, args=(psize,), daemon=True)
        self._rx_thread.start()

        self._btn_conn.configure(text="DISCONNETTI",
                                  border_color=C["danger"], text_color=C["danger"])
        self._lbl_conn.configure(text="Connesso", text_color=C["success"])
        self._lbl_sb_left.configure(text=f"In ascolto — {porta} @ {baud} baud")
        self._sys_labels["Porta"].configure(text=porta, text_color=C["accent"])
        self._sys_labels["Baud"].configure(text=str(baud), text_color=C["text_mid"])
        self._sys_labels["Packet size"].configure(text=f"{psize} B", text_color=C["text_mid"])

        log.info(f"Connesso: {porta} @ {baud}")
        self._log(f"Porta aperta: {porta} @ {baud} baud", "info")
        self._log("DMA RX attivo — attesa pacchetti...", "info")

    def _disconnect(self):
        self._stop_rx.set()
        self._connected = False
        if self._ser and self._ser.is_open:
            self._ser.close()
        self._ser = None

        self._btn_conn.configure(text="CONNETTI",
                                  border_color=C["accent"], text_color=C["accent"])
        self._lbl_conn.configure(text="Disconnesso", text_color=C["text_dim"])
        self._lbl_sb_left.configure(text="Porta disconnessa")
        self._sys_labels["Porta"].configure(text="—", text_color=C["text_mid"])
        self._sys_labels["Baud"].configure(text="—", text_color=C["text_mid"])
        self._sys_labels["Packet size"].configure(text="—", text_color=C["text_mid"])

        log.info("Disconnesso.")
        self._log("Connessione chiusa.", "warn")

    # ──────────────────────────────────────────────────────────────────────────
    #  THREAD RX
    # ──────────────────────────────────────────────────────────────────────────
    def _rx_loop(self, psize: int):
        """Gira in un thread separato. Legge pacchetti dalla seriale."""
        while not self._stop_rx.is_set():
            try:
                raw = self._ser.read(psize)
            except serial.SerialException as e:
                log.error(f"Errore lettura: {e}")
                self.after(0, lambda: self._log(f"Errore lettura: {e}", "err"))
                self._stats["err"] += 1
                time.sleep(0.5)
                continue

            if not raw:
                continue

            if len(raw) < psize:
                self.after(0, lambda n=len(raw): self._log(
                    f"Pacchetto incompleto: {n}/{psize} byte", "warn"))

            packet = {
                "id":           len(self._packets),
                "raw":          raw,
                "hex":          hex_str(raw),
                "ascii":        ascii_str(raw),           # decodifica arricchita con [XX]
                "testo":        testo_utile(raw),         # payload utile senza null di coda
                "time":         ts(),
                "replayed":     False,
                "replay_count": 0,
            }
            self._packets.append(packet)
            self._stats["rx"] += 1
            log.debug(
                f"RX #{packet['id']+1:04d} | "
                f"testo={packet['testo']!r} | "
                f"hex={packet['hex']}"
            )

            self.after(0, lambda p=packet: self._on_packet_received(p))

    def _on_packet_received(self, packet: dict):
        self._add_packet_card(packet)
        self._update_stats()
        self._log(
            f"RX #{packet['id']+1:04d} — {len(packet['raw'])} B  "
            f"| {packet['testo']!r}"
        )

    # ──────────────────────────────────────────────────────────────────────────
    #  REPLAY
    # ──────────────────────────────────────────────────────────────────────────
    def _confirm_replay(self):
        if self._selected_idx is None:
            return
        p = self._packets[self._selected_idx]
        try:
            n = int(self._ent_repeat.get())
        except ValueError:
            n = 1
        n = max(1, min(n, 99))

        risposta = messagebox.askyesno(
            "⚡ Replay Attack",
            f"Stai per ritrasmettere il pacchetto #{p['id']+1:04d} "
            f"({len(p['raw'])} byte) alla serratura.\n\n"
            f"Testo: {p['testo']!r}\n\n"
            f"Il payload verrà inviato {n}× sul canale radio 433 MHz.\n\n"
            "Procedere?"
        )
        if risposta:
            self._execute_replay(p, n)

    def _execute_replay(self, packet: dict, n: int):
        if not self._connected or not self._ser:
            messagebox.showwarning("Non connesso", "Connetti prima la porta seriale.")
            return

        for i in range(n):
            try:
                scritti = self._ser.write(packet["raw"])
                self._ser.flush()
                self._stats["tx"] += 1
                log.debug(
                    f"TX #{self._stats['tx']:04d} | {scritti} byte "
                    f"| replay #{packet['id']+1:04d} | testo={packet['testo']!r}"
                )
                self._log(
                    f"TX #{self._stats['tx']:04d} → replay #{packet['id']+1:04d} "
                    f"({scritti} B)  | {packet['testo']!r}",
                    "warn"
                )
            except serial.SerialException as e:
                self._stats["err"] += 1
                log.error(f"Errore scrittura: {e}")
                self._log(f"Errore invio: {e}", "err")

        packet["replayed"] = True
        packet["replay_count"] += n
        self._refresh_card(packet)
        self._render_detail(packet)
        self._update_stats()
        self._sys_labels["Ultimo replay"].configure(
            text=f"#{packet['id']+1:04d} ×{packet['replay_count']}",
            text_color=C["warn"])

    # ──────────────────────────────────────────────────────────────────────────
    #  CLEAR
    # ──────────────────────────────────────────────────────────────────────────
    def _clear_packets(self):
        self._packets.clear()
        self._selected_idx = None
        self._stats["rx"] = self._stats["tx"] = self._stats["err"] = 0

        for w in self._pkt_frame.winfo_children():
            w.destroy()
        self._empty_lbl = ctk.CTkLabel(
            self._pkt_frame,
            text="📡  In ascolto sul canale 433 MHz\n\nConnetti la porta seriale e premi\nil pulsante sulla CHIAVE hardware",
            font=FONT_UI, text_color=C["text_dim"], justify="center")
        self._empty_lbl.grid(row=0, column=0, pady=80)

        for w in self._detail_frame.winfo_children():
            w.destroy()
        self._detail_placeholder = ctk.CTkLabel(
            self._detail_frame, text="— Seleziona un pacchetto —",
            font=FONT_UI_SM, text_color=C["text_dim"])
        self._detail_placeholder.grid(row=0, column=0, pady=20)

        self._btn_replay.configure(state="disabled")
        self._lbl_pkt_count.configure(text="0 pacchetti")
        self._update_stats()
        self._sys_labels["Selezionato"].configure(text="Nessuno", text_color=C["text_mid"])
        self._log("Buffer pacchetti svuotato.", "warn")

    # ──────────────────────────────────────────────────────────────────────────
    #  LOG
    # ──────────────────────────────────────────────────────────────────────────
    def _log(self, msg: str, level: str = "default"):
        tb = self._log_box._textbox
        self._log_box.configure(state="normal")
        tb.insert("end", f"[{ts()}] ", "dim")
        tb.insert("end", msg + "\n", level)
        self._log_box.configure(state="disabled")
        self._log_box.see("end")

        # limita a 500 righe
        lines = int(tb.index("end-1c").split(".")[0])
        if lines > 500:
            tb.configure(state="normal")
            tb.delete("1.0", f"{lines-500}.0")
            tb.configure(state="disabled")

    # ──────────────────────────────────────────────────────────────────────────
    #  AGGIORNAMENTI PERIODICI
    # ──────────────────────────────────────────────────────────────────────────
    def _update_stats(self):
        self._lbl_rx_val.configure(text=str(self._stats["rx"]))
        self._lbl_tx_val.configure(text=str(self._stats["tx"]))
        self._lbl_err_val.configure(text=str(self._stats["err"]))
        self._lbl_pkt_count.configure(text=f"{len(self._packets)} pacchetti")

    def _tick(self):
        now = datetime.now().strftime("%d/%m/%Y  %H:%M:%S")
        self._lbl_clock.configure(text=now)

        if self._session_start:
            s = int(time.time() - self._session_start)
            self._sys_labels["Sessione"].configure(
                text=f"{s//60}:{s%60:02d}", text_color=C["text_mid"])

        self.after(1000, self._tick)

    # ──────────────────────────────────────────────────────────────────────────
    #  CHIUSURA
    # ──────────────────────────────────────────────────────────────────────────
    def on_close(self):
        self._stop_rx.set()
        if self._ser and self._ser.is_open:
            self._ser.close()
        log.info(
            f"Chiusura — RX:{self._stats['rx']} "
            f"TX:{self._stats['tx']} ERR:{self._stats['err']}"
        )
        self.destroy()


# ─── Entry point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = HackerDashboard()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
