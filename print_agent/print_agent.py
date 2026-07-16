#!/usr/bin/env python3
"""
GHS Label Print Agent v1.0
═══════════════════════════
Lightweight local service that receives label images from the SGA web app
and prints them directly to a USB-connected printer, bypassing Chrome's
print dialog. Runs on the warehouse PC alongside the browser.

Architecture:
    Browser (warehouse PC) ──fetch──▶ Flask Server (generates images)
             │
             └──fetch──▶ localhost:5555 (this agent) ──USB──▶ EPSON printer

Usage:
    python print_agent.py              # Start with defaults
    python print_agent.py --port 5555  # Custom port
    python print_agent.py --printer "EPSON L4150 Series"

Endpoints:
    GET  /status     → Agent health + available printers
    POST /print      → Print one or more label images
    GET  /printers   → List available printers
    POST /configure  → Update runtime configuration
"""

import argparse
import base64
import io
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# ══════════════════════════════════════════════════════════════════════
# Optional imports — check at startup so user gets clear error messages
# ══════════════════════════════════════════════════════════════════════
_missing = []

try:
    from flask import Flask, request, jsonify
except ImportError:
    _missing.append("flask")

try:
    from PIL import Image, ImageWin
except ImportError:
    _missing.append("Pillow")

try:
    import numpy as np

    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

try:
    import win32print
    import win32ui
    import win32con
except ImportError:
    _missing.append("pywin32")

try:
    import requests as http_requests
except ImportError:
    http_requests = None  # Not critical — base64 mode still works

if _missing:
    print("╔══════════════════════════════════════════════════════════╗")
    print("║  Missing required packages:                             ║")
    for pkg in _missing:
        print(f"║    pip install {pkg:<42} ║")
    print("║                                                          ║")
    print("║  Or install all at once:                                 ║")
    print("║    pip install -r requirements.txt                       ║")
    print("╚══════════════════════════════════════════════════════════╝")
    sys.exit(1)

# ══════════════════════════════════════════════════════════════════════
# Configuration
# ══════════════════════════════════════════════════════════════════════
CONFIG_FILE = Path(__file__).parent / "print_agent_config.json"

DEFAULT_CONFIG = {
    # ── Flask agent ───────────────────────────────────────────────
    "port": 5555,
    "host": "0.0.0.0",  # Accept remote connections (for Print Tunnel)
    "allowed_origins": ["*"],  # CORS origins
    "log_level": "INFO",
    # ── Remote tunnel support ─────────────────────────────────────
    # API key that the Print Tunnel must send in X-Tunnel-Key header.
    # Local requests (127.0.0.1 / browser) are always allowed.
    "tunnel_api_key": "sga-print-tunnel-2026",
    # ── Print method ──────────────────────────────────────────────
    # "windows" → use installed Windows driver (GDI)
    # "tcp"     → send TSPL commands directly to printer IP:port
    "print_method": "tcp",
    # ── Windows GDI mode ─────────────────────────────────────────
    "printer_name": "",  # Empty = system default
    # ── TCP / network mode ────────────────────────────────────────
    # List of network printers (same model, different units)
    "tcp_printers": [
        {"name": "TTP2610MT", "ip": "192.168.2.179", "port": 9100},
        {"name": "TTP2610MT (Copia 2)", "ip": "192.168.2.179", "port": 9100},
    ],
    "active_printer_index": 0,  # Index into tcp_printers
    "printer_dpi": 203,  # Thermal printer DPI (203 or 300)
    # ── Label size ────────────────────────────────────────────────
    "default_width_mm": 200,  # Warehouse 02 label
    "default_height_mm": 150,
    # ── CALIBRATION: Label gap (brecha entre etiquetas) ────────
    # Physical gap between stickers on the roll, in millimetres.
    # Measure with a ruler from the bottom edge of one sticker
    # to the top edge of the next.  Common values:
    #   0   = continuous roll (no gap)
    #   2   = 2 mm gap
    #   3   = 3 mm gap  ← typical for 200×150 mm rolls
    #   5   = some industrial rolls
    # If prints drift DOWN after many labels  → increase this value.
    # If prints drift UP   after many labels  → decrease this value.
    # Fine-tune in 0.5 mm increments for best results.
    "label_gap_mm": 3,  # ★ Gap between stickers on roll (mm)
    "label_gap_offset_mm": 0,  # ★ Gap sensor offset (usually 0)
    "print_quality": "high",  # high / draft
    "auto_orient": True,  # Auto-detect landscape vs portrait
    # ── Bitmap polarity ────────────────────────────────────────────
    # TSC printers (TTP-2610MT, etc.) typically need INVERTED bitmap:
    #   0 = black (print/fire), 1 = white (no print/paper)
    # This contradicts the TSPL spec (1=black) but matches real hardware.
    # Set to False only if your print comes out as a negative image.
    "invert_bitmap": True,
}


def load_config() -> dict:
    """Load config from file, merging with defaults."""
    config = dict(DEFAULT_CONFIG)
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                user_config = json.load(f)
            config.update(user_config)
        except Exception as e:
            logging.warning(f"Could not load config: {e}")
    return config


def save_config(config: dict):
    """Persist configuration to JSON file."""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def get_printer_name(config: dict = None) -> str:
    """Return configured printer name or system default."""
    if config is None:
        config = load_config()
    name = config.get("printer_name", "")
    if name:
        return name
    try:
        return win32print.GetDefaultPrinter()
    except Exception:
        return ""


# ══════════════════════════════════════════════════════════════════════
# Windows GDI Printing
# ══════════════════════════════════════════════════════════════════════


def list_printers() -> list:
    """Return list of installed Windows printers with status info."""
    printers = []
    try:
        default = win32print.GetDefaultPrinter()
    except Exception:
        default = ""

    flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
    for _flags, _desc, name, _comment in win32print.EnumPrinters(flags):
        printers.append(
            {
                "name": name,
                "is_default": (name == default),
                "method": "windows",
            }
        )
    return printers


# ══════════════════════════════════════════════════════════════════════
# TCP / Network Direct Printing (TSPL — TSC Thermal Label Language)
# ══════════════════════════════════════════════════════════════════════


def test_tcp_connection(ip: str, port: int, timeout: float = 3.0) -> bool:
    """Return True if a TCP connection to ip:port succeeds."""
    import socket

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect((ip, port))
        return True
    except Exception:
        return False


def get_active_tcp_printer(config: dict) -> dict:
    """Return the currently selected TCP printer entry from config."""
    printers = config.get("tcp_printers", [])
    if not printers:
        return {}
    idx = config.get("active_printer_index", 0)
    idx = max(0, min(idx, len(printers) - 1))
    return printers[idx]


def list_tcp_printers(config: dict) -> list:
    """Return TCP printers from config with live connectivity status."""
    result = []
    printers = config.get("tcp_printers", [])
    active_idx = config.get("active_printer_index", 0)
    for i, p in enumerate(printers):
        online = test_tcp_connection(p["ip"], p["port"], timeout=2.0)
        result.append(
            {
                "index": i,
                "name": p.get("name", f"Printer {i}"),
                "ip": p["ip"],
                "port": p["port"],
                "online": online,
                "active": (i == active_idx),
                "method": "tcp",
            }
        )
    return result


def tspl_print_image(
    img: Image.Image,
    ip: str,
    port: int,
    width_mm: float,
    height_mm: float,
    copies: int = 1,
    dpi: int = 203,
    invert: bool = True,
    gap_mm: float = 3.0,
    gap_offset_mm: float = 0.0,
) -> dict:
    """
    Print a PIL Image directly to a TSC thermal printer via raw TCP socket
    using TSPL (TSC Printer Language) commands.

    TSPL BITMAP format: 1 bit per pixel, MSB first, row-padded to byte boundary.

    Bit polarity note:
        The TSPL spec says 1=black, BUT real TSC hardware (TTP-2610MT, etc.)
        actually uses 0=black / 1=white.  The `invert` parameter (default True)
        flips the bitmap to match real printer behaviour.  If your print comes
        out as a negative, toggle this flag.

    Args:
        img            : PIL Image
        ip             : Printer IP address
        port           : Raw TCP port (typically 9100)
        width_mm       : Label width in mm (e.g. 200)
        height_mm      : Label height in mm (e.g. 150)
        copies         : Number of copies to print (default 1)
        dpi            : Printer dots-per-inch (203 or 300, default 203)
        invert         : Flip bitmap polarity (True = 0 is black, for real TSC HW)
        gap_mm         : ★ CALIBRATION — Distance (mm) between stickers on the
                         roll.  This is the physical gap/brecha.  The printer
                         uses this to compute the "pitch" = height_mm + gap_mm
                         and advance correctly after each label.
                         Default 3.0 mm for 200×150 mm rolls.
        gap_offset_mm  : ★ CALIBRATION — Offset of the gap sensor from the
                         label edge.  Almost always 0.  Only change this if
                         the sensor on your printer is physically shifted.

    Returns:
        dict with job details
    """
    import socket

    # ── Convert to grayscale ─────────────────────────────────────
    if img.mode == "RGBA":
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[3])
        img = bg
    if img.mode != "L":
        img = img.convert("L")

    # ── Auto-rotate to match label orientation ───────────────────
    target_landscape = width_mm >= height_mm
    img_landscape = img.size[0] >= img.size[1]
    if target_landscape != img_landscape:
        img = img.rotate(90, expand=True)
        logging.info(f"🔄 TCP: rotated image to {img.size[0]}x{img.size[1]}px")

    # ── Compute dot dimensions ───────────────────────────────────
    width_dots = int(round(width_mm / 25.4 * dpi))
    height_dots = int(round(height_mm / 25.4 * dpi))
    # Ensure width in dots is a multiple of 8 (byte boundary)
    width_dots_aligned = ((width_dots + 7) // 8) * 8
    bytes_per_row = width_dots_aligned // 8

    logging.info(
        f"🖨️  TCP TSPL: {ip}:{port} | {width_mm}x{height_mm}mm | "
        f"{width_dots}x{height_dots} dots | {dpi} DPI | {bytes_per_row}B/row"
    )

    # ── Resize to exact dot dimensions ───────────────────────────
    img = img.resize((width_dots, height_dots), Image.LANCZOS)

    # ── Convert to TSPL 1-bit bitmap ─────────────────────────────
    # We bypass PIL's mode "1" entirely and pack bits with numpy.
    #
    # Two conventions exist in the wild:
    #   Spec (invert=False):  bit 1 = black (print), bit 0 = white
    #   Real HW (invert=True): bit 0 = black (print), bit 1 = white
    #
    # With invert=True (default for TSC TTP-2610MT):
    #   dark pixel  → bit 0 (printer fires heating element)
    #   light pixel → bit 1 (paper stays white)
    threshold = 128
    polarity_label = "INVERTED (0=black)" if invert else "NORMAL (1=black)"
    logging.info(f"🎨 Bitmap polarity: {polarity_label}")

    if NUMPY_AVAILABLE:
        # ── Fast path: numpy packbits (unambiguous, MSB-first) ───
        arr = np.array(
            img, dtype=np.uint8
        )  # shape: (height, width), 0=black..255=white

        if invert:
            # 0=black (print), 1=white (no print) — for real TSC hardware
            # Light pixels (> threshold) → 1, Dark pixels (≤ threshold) → 0
            binary = np.zeros((height_dots, width_dots_aligned), dtype=np.uint8)
            binary[:, :width_dots] = (arr > threshold).astype(np.uint8)
        else:
            # 1=black (print), 0=white (no print) — per TSPL spec
            binary = np.zeros((height_dots, width_dots_aligned), dtype=np.uint8)
            binary[:, :width_dots] = (arr <= threshold).astype(np.uint8)

        raw_pixels = np.packbits(binary, axis=1).tobytes()
        logging.info(f"📊 Bitmap packed via numpy: {len(raw_pixels):,} bytes")
    else:
        # ── Fallback: pure-Python bit packing ────────────────────
        raw_gray = img.tobytes()  # Mode "L": 1 byte/pixel, 0=black, 255=white
        raw_pixels = bytearray(bytes_per_row * height_dots)
        for y in range(height_dots):
            row_base = y * width_dots
            out_base = y * bytes_per_row
            for x_byte in range(bytes_per_row):
                byte_val = 0
                for bit in range(8):
                    x = x_byte * 8 + bit
                    if x < width_dots:
                        pixel = raw_gray[row_base + x]
                        if invert:
                            # 0=black: set bit for LIGHT pixels
                            if pixel > threshold:
                                byte_val |= 0x80 >> bit
                        else:
                            # 1=black: set bit for DARK pixels
                            if pixel <= threshold:
                                byte_val |= 0x80 >> bit
                raw_pixels[out_base + x_byte] = byte_val
        raw_pixels = bytes(raw_pixels)
        logging.info(f"📊 Bitmap packed via Python: {len(raw_pixels):,} bytes")

    # ── Build TSPL command stream ─────────────────────────────────
    # ★ CALIBRATION NOTE: The GAP command defines the print "pitch".
    # TSPL syntax:  GAP <gap> mm, <offset> mm
    #   • gap    = physical distance between labels (brecha),
    #              i.e. the exposed liner between two stickers.
    #   • offset = gap-sensor offset (almost always 0).
    # The total advance per label ("pitch") is:  SIZE height + GAP.
    #   Example: SIZE 200×150 mm + GAP 3 mm → pitch = 153 mm.
    # If you see cumulative drift over 50+ labels, adjust gap_mm:
    #   • Prints drift DOWN  → increase gap_mm (e.g. 3.0 → 3.5)
    #   • Prints drift UP    → decrease gap_mm (e.g. 3.0 → 2.5)
    # You can also change this at runtime via the /configure endpoint:
    #   POST /configure {"label_gap_mm": 3.5}
    # Or via the print_agent_config.json file.
    tspl_header = (
        f"SIZE {width_mm:.1f} mm,{height_mm:.1f} mm\r\n"
        f"GAP {gap_mm:.1f} mm,{gap_offset_mm:.1f} mm\r\n"  # ← pitch = height + gap
        f"DIRECTION 0\r\n"
        f"SET PRINTSPEED 4\r\n"
        f"SET DENSITY 8\r\n"
        f"CLS\r\n"
        f"BITMAP 0,0,{bytes_per_row},{height_dots},0,"
    ).encode("ascii")

    tspl_footer = (f"\r\nPRINT {copies},1\r\n").encode("ascii")

    # Verify data size matches what BITMAP expects
    expected_bitmap_bytes = bytes_per_row * height_dots
    actual_bitmap_bytes = len(raw_pixels)
    if actual_bitmap_bytes != expected_bitmap_bytes:
        logging.error(
            f"❌ BITMAP data size mismatch! Expected {expected_bitmap_bytes} "
            f"({bytes_per_row}×{height_dots}), got {actual_bitmap_bytes}"
        )
        raise ValueError(
            f"Bitmap data size mismatch: {actual_bitmap_bytes} != {expected_bitmap_bytes}"
        )

    payload = tspl_header + raw_pixels + tspl_footer
    total_bytes = len(payload)

    logging.info(
        f"📡 Sending {total_bytes:,} bytes ({bytes_per_row * height_dots:,} bitmap + "
        f"{len(tspl_header) + len(tspl_footer)} TSPL) to {ip}:{port}"
    )

    # ── Send to printer ───────────────────────────────────────────
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(15)
        s.connect((ip, port))
        s.sendall(payload)

    logging.info(
        f"✅ TCP print complete: {copies} copy/copies sent to {ip}:{port} "
        f"| pitch = {height_mm:.1f} + {gap_mm:.1f} = {height_mm + gap_mm:.1f} mm"
    )

    return {
        "success": True,
        "method": "tcp",
        "printer_address": f"{ip}:{port}",
        "width_dots": width_dots,
        "height_dots": height_dots,
        "dpi": dpi,
        "bytes_per_row": bytes_per_row,
        "total_bytes": total_bytes,
        "copies": copies,
        "target_mm": f"{width_mm}x{height_mm}",
        "gap_mm": gap_mm,
        "pitch_mm": height_mm + gap_mm,  # Total advance per label
    }


def print_image(
    img: Image.Image,
    printer_name: str,
    width_mm: float,
    height_mm: float,
    orientation: str = "landscape",
    fit_mode: str = "fill",
) -> dict:
    """
    Print a PIL Image to a Windows printer at exact physical dimensions.

    Strategy: FULL-PAGE BLEED + SMART ORIENTATION
        1. Auto-rotate image so its aspect ratio matches the target dimensions
        2. Set DEVMODE: PORTRAIT always (avoids EPSON driver double-rotation bug)
           PaperWidth = desired width, PaperLength = desired height (direct)
        3. Create DC, read physical page dimensions + margin offsets
        4. If DC orientation doesn't match target, rotate image to compensate
        5. Draw image from (-offset_x, -offset_y) covering the FULL physical page

    Args:
        img:          PIL Image (will be converted to RGB)
        printer_name: Windows printer name
        width_mm:     Target label width in mm (e.g. 200)
        height_mm:    Target label height in mm (e.g. 150)
        orientation:  'landscape' or 'portrait' (informational, auto-detected)
        fit_mode:     'fill' (stretch to full page, default) or 'contain' (preserve aspect)

    Returns:
        dict with print job details
    """
    import win32gui

    # ── Ensure RGB ──────────────────────────────────────────────────
    if img.mode == "RGBA":
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[3])
        img = bg
    elif img.mode != "RGB":
        img = img.convert("RGB")

    logging.info(
        f"📐 Input image: {img.size[0]}x{img.size[1]}px, "
        f"target: {width_mm}x{height_mm}mm, fit: {fit_mode}"
    )

    # ── Step 1: Auto-rotate image to match target aspect ratio ──────
    # The PDF generator may produce a portrait image (via template
    # rotation) even when the target label is landscape.  Detect this
    # and rotate the image so it matches the target dimensions.
    target_landscape = width_mm >= height_mm
    img_landscape = img.size[0] >= img.size[1]

    if target_landscape != img_landscape:
        logging.info(
            f"🔄 Image orientation mismatch: image={'landscape' if img_landscape else 'portrait'}, "
            f"target={'landscape' if target_landscape else 'portrait'} → rotating image 90°"
        )
        img = img.rotate(90, expand=True)
        logging.info(f"   Rotated to {img.size[0]}x{img.size[1]}px")

    # ── Step 2: Configure DEVMODE ───────────────────────────────────
    # CRITICAL: NEVER use DMORIENT_LANDSCAPE.
    # The EPSON L4150 (and many drivers) applies an extra 90° rotation
    # that conflicts with content already generated in the correct
    # orientation.  Instead, set paper dimensions directly and use
    # PORTRAIT (= "don't rotate my content, driver").
    #
    # PaperWidth / PaperLength are set to the DESIRED physical
    # dimensions.  For landscape labels (200×150), PaperWidth=200mm,
    # PaperLength=150mm.  Some drivers accept Width > Length for
    # custom paper; if not, we detect the swap via DC caps and
    # rotate the image to compensate.

    hPrinter = win32print.OpenPrinter(printer_name)
    try:
        printer_info = win32print.GetPrinter(hPrinter, 2)
        devmode = printer_info["pDevMode"]

        devmode.PaperSize = 256  # DMPAPER_USER (custom)
        devmode.Orientation = win32con.DMORIENT_PORTRAIT  # ALWAYS portrait

        # Set dimensions exactly as requested
        devmode.PaperWidth = int(width_mm * 10)  # tenths of mm
        devmode.PaperLength = int(height_mm * 10)

        devmode.Fields |= (
            win32con.DM_PAPERSIZE
            | win32con.DM_PAPERWIDTH
            | win32con.DM_PAPERLENGTH
            | win32con.DM_ORIENTATION
        )

        logging.info(
            f"📋 DEVMODE: PaperWidth={devmode.PaperWidth/10:.0f}mm, "
            f"PaperLength={devmode.PaperLength/10:.0f}mm, "
            f"Orientation=PORTRAIT (always, no driver rotation)"
        )
    finally:
        win32print.ClosePrinter(hPrinter)

    # ── Step 3: Create Device Context ───────────────────────────────
    hDC_handle = win32gui.CreateDC("WINSPOOL", printer_name, devmode)
    hDC = win32ui.CreateDCFromHandle(hDC_handle)

    try:
        dpi_x = hDC.GetDeviceCaps(win32con.LOGPIXELSX)
        dpi_y = hDC.GetDeviceCaps(win32con.LOGPIXELSY)

        phys_w_px = hDC.GetDeviceCaps(110)  # PHYSICALWIDTH
        phys_h_px = hDC.GetDeviceCaps(111)  # PHYSICALHEIGHT
        printable_w = hDC.GetDeviceCaps(win32con.HORZRES)
        printable_h = hDC.GetDeviceCaps(win32con.VERTRES)
        off_x = hDC.GetDeviceCaps(112)  # PHYSICALOFFSETX
        off_y = hDC.GetDeviceCaps(113)  # PHYSICALOFFSETY

        phys_w_mm = phys_w_px / dpi_x * 25.4
        phys_h_mm = phys_h_px / dpi_y * 25.4
        printable_w_mm = printable_w / dpi_x * 25.4
        printable_h_mm = printable_h / dpi_y * 25.4
        off_x_mm = off_x / dpi_x * 25.4
        off_y_mm = off_y / dpi_y * 25.4

        logging.info(
            f"🖨️  DC caps: DPI={dpi_x}x{dpi_y}, "
            f"physical={phys_w_px}x{phys_h_px}px ({phys_w_mm:.1f}x{phys_h_mm:.1f}mm), "
            f"printable={printable_w}x{printable_h}px ({printable_w_mm:.1f}x{printable_h_mm:.1f}mm), "
            f"offset={off_x}x{off_y}px ({off_x_mm:.1f}x{off_y_mm:.1f}mm)"
        )

        # ── Step 4: Verify DC matches target orientation ────────────
        # If the driver rejected our PaperWidth > PaperLength and
        # swapped them, the DC will be portrait when we wanted landscape
        # (or vice versa).  Detect and rotate image to compensate.
        dc_landscape = phys_w_px > phys_h_px

        if target_landscape != dc_landscape:
            logging.warning(
                f"⚠️  DC orientation mismatch: target={'landscape' if target_landscape else 'portrait'}, "
                f"DC={'landscape' if dc_landscape else 'portrait'} → rotating image 90° to match DC"
            )
            img = img.rotate(90, expand=True)
            logging.info(f"   Image now {img.size[0]}x{img.size[1]}px")

        # ── Step 5: FULL-PAGE BLEED draw ────────────────────────────
        # GDI origin (0,0) = top-left of PRINTABLE area.
        # Physical page starts at (-off_x, -off_y).
        # Drawing from (-off, -off) to (phys-off, phys-off) covers the
        # entire physical sheet.  Hardware clips at margins but content
        # fills edge-to-edge.

        draw_x0 = -off_x
        draw_y0 = -off_y
        draw_x1 = phys_w_px - off_x
        draw_y1 = phys_h_px - off_y

        if fit_mode == "contain":
            # Preserve aspect ratio within the physical page
            img_ratio = img.size[0] / img.size[1]
            page_ratio = phys_w_px / phys_h_px

            if img_ratio > page_ratio:
                final_w = phys_w_px
                final_h = int(phys_w_px / img_ratio)
                pad = (phys_h_px - final_h) // 2
                draw_x0 = -off_x
                draw_y0 = -off_y + pad
                draw_x1 = phys_w_px - off_x
                draw_y1 = draw_y0 + final_h
            else:
                final_h = phys_h_px
                final_w = int(phys_h_px * img_ratio)
                pad = (phys_w_px - final_w) // 2
                draw_x0 = -off_x + pad
                draw_y0 = -off_y
                draw_x1 = draw_x0 + final_w
                draw_y1 = phys_h_px - off_y

        draw_w_mm = (draw_x1 - draw_x0) / dpi_x * 25.4
        draw_h_mm = (draw_y1 - draw_y0) / dpi_y * 25.4

        logging.info(
            f"📏 Drawing: ({draw_x0},{draw_y0})-({draw_x1},{draw_y1}) = "
            f"{draw_x1-draw_x0}x{draw_y1-draw_y0}px ({draw_w_mm:.1f}x{draw_h_mm:.1f}mm)"
        )

        # ── Print ───────────────────────────────────────────────────
        hDC.StartDoc("GHS Label")
        hDC.StartPage()

        dib = ImageWin.Dib(img)
        dib.draw(hDC.GetHandleOutput(), (draw_x0, draw_y0, draw_x1, draw_y1))

        hDC.EndPage()
        hDC.EndDoc()

        return {
            "success": True,
            "printer_dpi": f"{dpi_x}x{dpi_y}",
            "physical_page_mm": f"{phys_w_mm:.1f}x{phys_h_mm:.1f}",
            "printable_area_mm": f"{printable_w_mm:.1f}x{printable_h_mm:.1f}",
            "draw_area_mm": f"{draw_w_mm:.1f}x{draw_h_mm:.1f}",
            "margin_mm": f"{off_x_mm:.1f}x{off_y_mm:.1f}",
            "target_mm": f"{width_mm}x{height_mm}",
            "image_rotated": target_landscape != img_landscape,
        }

    finally:
        try:
            hDC.DeleteDC()
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════
# Flask Application
# ══════════════════════════════════════════════════════════════════════
app = Flask(__name__)


# ── Remote tunnel authentication ──────────────────────────────────────
# Requests from localhost (the browser) are always allowed.
# Requests from remote IPs (the Print Tunnel) must include a valid
# X-Tunnel-Key header matching the configured tunnel_api_key.
@app.before_request
def validate_remote_request():
    """Block unauthenticated requests from non-local IPs."""
    # Allow OPTIONS (CORS preflight) from anywhere
    if request.method == "OPTIONS":
        return None

    remote_ip = request.remote_addr or ""
    # Local requests always allowed (browser on same PC)
    if remote_ip in ("127.0.0.1", "::1", "localhost"):
        return None

    # Remote request — validate tunnel API key
    config = load_config()
    expected_key = config.get("tunnel_api_key", "")
    if not expected_key:
        # No key configured = accept all (backwards compatible)
        return None

    provided_key = request.headers.get("X-Tunnel-Key", "")
    if provided_key == expected_key:
        return None

    # Reject unauthorized remote request
    logging.warning(
        f"🚫 Rejected remote request from {remote_ip} — invalid tunnel key"
    )
    return jsonify({"error": "Unauthorized — invalid tunnel key"}), 403


# CORS support for cross-origin requests from the web app
@app.after_request
def add_cors_headers(response):
    config = load_config()
    origins = config.get("allowed_origins", ["*"])
    origin = request.headers.get("Origin", "")

    if "*" in origins or origin in origins:
        response.headers["Access-Control-Allow-Origin"] = origin or "*"
    else:
        response.headers["Access-Control-Allow-Origin"] = origins[0] if origins else "*"

    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Tunnel-Key, X-Tunnel-Origin"
    response.headers["Access-Control-Max-Age"] = "3600"
    return response


@app.route("/", methods=["GET"])
def home():
    """Landing page showing current method, printers and connectivity."""
    config = load_config()
    method = config.get("print_method", "windows")

    if method == "tcp":
        tcp_ps = list_tcp_printers(config)
        _active = get_active_tcp_printer(config)
        rows = ""
        for p in tcp_ps:
            status_color = "#10b981" if p["online"] else "#ef4444"
            status_text = "🟢 online" if p["online"] else "🔴 offline"
            active_mark = " ◀ active" if p["active"] else ""
            rows += (
                f"<tr style='background:{'#f0fdf4' if p['active'] else 'white'}'>"
                f"<td style='padding:8px;'>{p['index']}</td>"
                f"<td style='padding:8px;font-weight:600;'>{p['name']}{active_mark}</td>"
                f"<td style='padding:8px;'>{p['ip']}:{p['port']}</td>"
                f"<td style='padding:8px;color:{status_color};font-weight:600;'>{status_text}</td>"
                f"</tr>"
            )
        printer_section = f"""
            <h3 style='color:#374151;margin-top:20px;'>Network Printers</h3>
            <table style='width:100%;border-collapse:collapse;border:1px solid #e5e7eb;'>
              <thead><tr style='background:#f3f4f6;'>
                <th style='padding:8px;text-align:left;'>#</th>
                <th style='padding:8px;text-align:left;'>Name</th>
                <th style='padding:8px;text-align:left;'>Address</th>
                <th style='padding:8px;text-align:left;'>Status</th>
              </tr></thead>
              <tbody>{rows}</tbody>
            </table>
            <p style='font-size:0.8rem;color:#94a3b8;margin-top:8px;'>
              POST /select_printer {{"method":"tcp","index":0}} to switch printers
            </p>"""
    else:
        printer = get_printer_name(config)
        printer_section = f"""
            <p style='margin-top:12px;'><strong>Windows Printer:</strong> {printer}</p>"""

    badge_color = "#2563eb" if method == "tcp" else "#7c3aed"
    badge_label = "📡 TCP / Network" if method == "tcp" else "🖥️ Windows GDI"
    return (
        f"""
    <html>
    <head><title>GHS Print Agent</title></head>
    <body style="font-family: system-ui; padding: 40px; background: #f8fafc;">
        <div style="max-width: 700px; margin: 0 auto; background: white;
                    padding: 32px; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
            <h1 style="color: #2563eb;">🖨️ GHS Print Agent</h1>
            <p style="color: #10b981; font-weight: 600;">✅ Agent is running</p>
            <span style="background:{badge_color};color:white;padding:4px 12px;
                         border-radius:9999px;font-size:0.85rem;">{badge_label}</span>
            <table style="width: 100%; border-collapse: collapse; margin-top: 16px;">
                <tr><td style="padding: 8px; color: #64748b;">Agent port:</td>
                    <td style="padding: 8px;">{config.get('port', 5555)}</td></tr>
                <tr><td style="padding: 8px; color: #64748b;">Label size:</td>
                    <td style="padding: 8px;">{config.get('default_width_mm', 200)}×{config.get('default_height_mm', 150)} mm</td></tr>
                <tr><td style="padding: 8px; color: #64748b;">Label gap:</td>
                    <td style="padding: 8px;">{config.get('label_gap_mm', 3)} mm (pitch = {config.get('default_height_mm', 150) + config.get('label_gap_mm', 3)} mm)</td></tr>
            </table>
            {printer_section}
            <p style="margin-top: 20px; font-size: 0.85rem; color: #94a3b8;">
                API: <code>/status</code> · <code>/print</code> · <code>/printers</code>
                   · <code>/select_printer</code> · <code>/configure</code> · <code>/test</code>
            </p>
        </div>
    </body>
    </html>
    """,
        200,
    )


@app.route("/status", methods=["GET", "OPTIONS"])
def status():
    """Health check — web app calls this to detect if the agent is available."""
    if request.method == "OPTIONS":
        return "", 204

    config = load_config()
    method = config.get("print_method", "windows")

    if method == "tcp":
        tcp_p = get_active_tcp_printer(config)
        printer_info = {
            "method": "tcp",
            "name": tcp_p.get("name", ""),
            "address": f"{tcp_p.get('ip','')}:{tcp_p.get('port', 9100)}",
            "online": test_tcp_connection(tcp_p.get("ip", ""), tcp_p.get("port", 9100)),
            "index": config.get("active_printer_index", 0),
        }
    else:
        win_printer = get_printer_name(config)
        printer_info = {
            "method": "windows",
            "name": win_printer,
            "address": "local",
            "online": True,
        }

    return jsonify(
        {
            "status": "online",
            "version": "2.0",
            "print_method": method,
            "printer": printer_info,
            "default_size": {
                "width_mm": config.get("default_width_mm", 200),
                "height_mm": config.get("default_height_mm", 150),
            },
            # ★ CALIBRATION: gap and pitch info (visible in /status response)
            "label_gap_mm": config.get("label_gap_mm", 3),
            "label_gap_offset_mm": config.get("label_gap_offset_mm", 0),
            "pitch_mm": config.get("default_height_mm", 150)
            + config.get("label_gap_mm", 3),
            "timestamp": datetime.now().isoformat(),
        }
    )


@app.route("/printers", methods=["GET", "OPTIONS"])
def printers():
    """List available printers: both Windows drivers and TCP network printers."""
    if request.method == "OPTIONS":
        return "", 204
    config = load_config()
    windows_printers = list_printers()
    tcp_printers = list_tcp_printers(config)
    return jsonify(
        {
            "print_method": config.get("print_method", "windows"),
            "windows_printers": windows_printers,
            "tcp_printers": tcp_printers,
            "active_printer_index": config.get("active_printer_index", 0),
        }
    )


# --- CANCELLATION ---
cancel_requested = False


@app.route("/cancel", methods=["POST", "OPTIONS"])
def cancel_print_endpoint():
    """Immediately stops ongoing print batch loops."""
    if request.method == "OPTIONS":
        return "", 204
    global cancel_requested
    cancel_requested = True
    logging.warning(
        "🛑 EMERGENCIA: Cancelación de impresión solicitada por el usuario."
    )
    return (
        jsonify({"message": "Cancelación solicitada al agente local", "success": True}),
        200,
    )


@app.route("/print", methods=["POST", "OPTIONS"])
def print_label():
    global cancel_requested
    cancel_requested = False
    """
    Print one or more label images.

    Request JSON:
    {
        "images": [
            {
                "data": "<base64 image data>",   // required
                "width_mm": 200,                  // optional (default from config)
                "height_mm": 150,                 // optional
                "copies": 1,                      // optional
                "orientation": "landscape",       // optional
                "rotation": 0                     // optional: 0, 90, 180, 270 (degrees)
            }
        ],
        "printer": "EPSON L4150 Series"           // optional (default from config)
    }

    OR single-image shorthand:
    {
        "image_base64": "<base64>",
        "width_mm": 200,
        "height_mm": 150,
        "rotation": 90,
        ...
    }
    """
    if request.method == "OPTIONS":
        return "", 204

    data = request.json
    if not data:
        return jsonify({"error": "No JSON body provided"}), 400

    config = load_config()
    # Allow per-request method override: {"method": "tcp"} or {"method": "windows"}
    method = data.get("method", config.get("print_method", "windows"))
    default_w = config.get("default_width_mm", 200)
    default_h = config.get("default_height_mm", 150)

    # Determine which printer to use
    if method == "tcp":
        # Allow per-request TCP printer index override
        tcp_idx = data.get("tcp_printer_index", config.get("active_printer_index", 0))
        tcp_ps = config.get("tcp_printers", [])
        if not tcp_ps:
            return (
                jsonify(
                    {"error": "No TCP printers configured. Add tcp_printers to config."}
                ),
                500,
            )
        tcp_idx = max(0, min(tcp_idx, len(tcp_ps) - 1))
        tcp_p = tcp_ps[tcp_idx]
        printer_label = f"{tcp_p.get('name', 'TCP')} ({tcp_p['ip']}:{tcp_p['port']})"
        # Verify connectivity
        if not test_tcp_connection(tcp_p["ip"], tcp_p["port"]):
            return (
                jsonify(
                    {
                        "error": f"Cannot connect to printer at {tcp_p['ip']}:{tcp_p['port']}",
                        "tip": "Check printer is powered on and IP is correct.",
                    }
                ),
                503,
            )
    else:
        printer_name = data.get("printer", get_printer_name(config))
        printer_label = printer_name
        available = [p["name"] for p in list_printers()]
        if printer_name not in available:
            return (
                jsonify(
                    {
                        "error": f"Printer '{printer_name}' not found",
                        "available_printers": available,
                    }
                ),
                404,
            )

    # Normalize to list of images
    images = data.get("images", [])
    if not images and "image_base64" in data:
        images = [
            {
                "data": data["image_base64"],
                "width_mm": data.get("width_mm", default_w),
                "height_mm": data.get("height_mm", default_h),
                "copies": data.get("copies", 1),
                "orientation": data.get("orientation", "landscape"),
                "rotation": data.get(
                    "rotation", 0
                ),  # Optional manual rotation: 0, 90, 180, 270
            }
        ]

    if not images:
        return (
            jsonify(
                {"error": "No images provided. Send 'images' array or 'image_base64'."}
            ),
            400,
        )

    results = []
    total_printed = 0
    errors = []

    for idx, img_spec in enumerate(images):
        if cancel_requested:
            msg = f"⚠ Cancelado en imagen {idx + 1}"
            logging.warning(msg)
            errors.append(msg)
            break

        try:
            img_data = img_spec.get("data", "")
            if not img_data:
                errors.append(f"Image {idx + 1}: no 'data' field")
                continue

            if "," in img_data and img_data.startswith("data:"):
                img_data = img_data.split(",", 1)[1]

            raw_bytes = base64.b64decode(img_data)
            img = Image.open(io.BytesIO(raw_bytes))

            width_mm = float(img_spec.get("width_mm", default_w))
            height_mm = float(img_spec.get("height_mm", default_h))
            copies = int(img_spec.get("copies", 1))
            orientation = img_spec.get("orientation", "landscape")
            rotation = int(img_spec.get("rotation", 0))  # Manual rotation override

            # ── Apply manual rotation if specified ───────────────────
            if rotation in [90, 180, 270]:
                img = img.rotate(
                    -rotation, expand=True
                )  # PIL rotates counter-clockwise
                logging.info(
                    f"🔄 Applied manual rotation: {rotation}° → image now {img.size[0]}x{img.size[1]}px"
                )
                # Swap dimensions for 90/270 degree rotations
                if rotation in [90, 270]:
                    width_mm, height_mm = height_mm, width_mm
                    logging.info(f"   Swapped dimensions to {width_mm}x{height_mm}mm")

            logging.info(
                f"📥 Image {idx+1}: {img.size[0]}x{img.size[1]}px "
                f"mode={img.mode}, requested={width_mm}x{height_mm}mm, "
                f"copies={copies}, method={method}"
            )

            # ── Print via selected method ──────────────────────────
            if method == "tcp":
                dpi = config.get("printer_dpi", 203)
                invert = config.get("invert_bitmap", True)
                # ★ CALIBRATION: Read gap from request body, then config, then default.
                # Per-request override:  POST /print {"label_gap_mm": 3.5}
                # Config-level default:  print_agent_config.json → "label_gap_mm": 3
                gap_mm = float(
                    img_spec.get(
                        "label_gap_mm",
                        data.get("label_gap_mm", config.get("label_gap_mm", 3)),
                    )
                )
                gap_offset_mm = float(
                    img_spec.get(
                        "label_gap_offset_mm",
                        data.get(
                            "label_gap_offset_mm", config.get("label_gap_offset_mm", 0)
                        ),
                    )
                )
                # Split TCP into smaller batches (e.g. 10) so we can abort sooner
                remaining = copies
                batch_size = 10
                while remaining > 0:
                    if cancel_requested:
                        logging.warning(
                            f"🛑 Cancelado en TCP antes de completar todas las copias. Faltaron: {remaining}"
                        )
                        break

                    current_batch = min(remaining, batch_size)
                    result = tspl_print_image(
                        img,
                        tcp_p["ip"],
                        tcp_p["port"],
                        width_mm,
                        height_mm,
                        copies=current_batch,
                        dpi=dpi,
                        invert=invert,
                        gap_mm=gap_mm,
                        gap_offset_mm=gap_offset_mm,
                    )
                    total_printed += current_batch
                    remaining -= current_batch

                logging.info(
                    f"✅ TCP printed image {idx + 1} ({total_printed} copies sent) "
                    f"→ {tcp_p['ip']}:{tcp_p['port']}"
                )
            else:
                if config.get("auto_orient", True):
                    orientation = "landscape" if width_mm > height_mm else "portrait"
                for copy_n in range(copies):
                    if cancel_requested:
                        logging.warning(
                            f"🛑 Cancelado en Windows. Copias completadas: {copy_n}/{copies}"
                        )
                        break

                    result = print_image(
                        img, printer_name, width_mm, height_mm, orientation
                    )
                    total_printed += 1
                    logging.info(
                        f"✅ Windows printed image {idx + 1} copy {copy_n + 1}/{copies} "
                        f"to {printer_name}"
                    )

            results.append(
                {
                    "index": idx + 1,
                    "status": "printed",
                    "method": method,
                    "copies": copies,
                    "size_mm": f"{width_mm}×{height_mm}",
                    "details": result,
                }
            )

        except Exception as e:
            error_msg = f"Image {idx + 1}: {str(e)}"
            logging.error(f"❌ {error_msg}")
            errors.append(error_msg)
            results.append(
                {
                    "index": idx + 1,
                    "status": "error",
                    "error": str(e),
                }
            )

    status_code = 200 if not errors else (207 if total_printed > 0 else 500)
    return (
        jsonify(
            {
                "success": total_printed > 0,
                "total_printed": total_printed,
                "printer": printer_label,
                "method": method,
                "results": results,
                "errors": errors,
            }
        ),
        status_code,
    )


@app.route("/configure", methods=["GET", "POST", "OPTIONS"])
def configure():
    """Get or update agent configuration."""
    if request.method == "OPTIONS":
        return "", 204

    if request.method == "GET":
        return jsonify(load_config())

    data = request.json
    if not data:
        return jsonify({"error": "No JSON body"}), 400

    config = load_config()
    # Only allow updating known keys
    allowed_keys = set(DEFAULT_CONFIG.keys())
    for key, value in data.items():
        if key in allowed_keys:
            config[key] = value

    save_config(config)
    return jsonify({"success": True, "config": config})


# ══════════════════════════════════════════════════════════════════════
# Printer Selection Endpoint
# ══════════════════════════════════════════════════════════════════════


@app.route("/select_printer", methods=["GET", "POST", "OPTIONS"])
def select_printer():
    """
    GET  /select_printer          → current selection + all options
    POST /select_printer          → switch active printer

    POST body — TCP mode:
        {"method": "tcp",     "index": 0}
    POST body — Windows mode:
        {"method": "windows", "printer_name": "TSC TTP-2610MT"}
    POST body — Add/update TCP printer:
        {"action": "add_tcp", "name": "Printer B", "ip": "192.168.2.180", "port": 9100}
    """
    if request.method == "OPTIONS":
        return "", 204

    config = load_config()

    if request.method == "GET":
        tcp_ps = list_tcp_printers(config)
        win_ps = list_printers()
        return jsonify(
            {
                "current_method": config.get("print_method", "windows"),
                "active_printer_index": config.get("active_printer_index", 0),
                "tcp_printers": tcp_ps,
                "windows_printers": win_ps,
            }
        )

    # ── POST: modify selection ─────────────────────────────────────
    data = request.json or {}
    action = data.get("action", "select")

    if action == "add_tcp":
        # Add a new TCP printer entry
        ip = data.get("ip")
        port = int(data.get("port", 9100))
        name = data.get("name", f"Printer {ip}")
        if not ip:
            return jsonify({"error": "'ip' is required"}), 400
        tcp_ps = config.get("tcp_printers", [])
        tcp_ps.append({"name": name, "ip": ip, "port": port})
        config["tcp_printers"] = tcp_ps
        save_config(config)
        online = test_tcp_connection(ip, port)
        return jsonify(
            {
                "success": True,
                "message": f"Added printer '{name}' at {ip}:{port}",
                "online": online,
                "index": len(tcp_ps) - 1,
            }
        )

    # Default action: select
    method = data.get("method", config.get("print_method", "windows"))
    config["print_method"] = method

    if method == "tcp":
        idx = int(data.get("index", 0))
        tcp_ps = config.get("tcp_printers", [])
        if idx < 0 or idx >= len(tcp_ps):
            return (
                jsonify(
                    {
                        "error": f"Index {idx} out of range (0–{len(tcp_ps)-1})",
                        "tcp_printers": tcp_ps,
                    }
                ),
                400,
            )
        config["active_printer_index"] = idx
        selected = tcp_ps[idx]
        online = test_tcp_connection(selected["ip"], selected["port"])
        save_config(config)
        return jsonify(
            {
                "success": True,
                "method": "tcp",
                "active_index": idx,
                "printer": selected,
                "online": online,
            }
        )
    else:
        win_name = data.get("printer_name", "")
        if win_name:
            config["printer_name"] = win_name
        save_config(config)
        return jsonify(
            {
                "success": True,
                "method": "windows",
                "printer_name": config.get("printer_name", get_printer_name(config)),
            }
        )


@app.route("/test", methods=["POST", "OPTIONS"])
def test_print():
    """Print a test page to verify printer connectivity."""
    if request.method == "OPTIONS":
        return "", 204

    config = load_config()
    req_data = request.json or {}
    method = req_data.get("method", config.get("print_method", "windows"))
    width_mm = float(req_data.get("width_mm", config.get("default_width_mm", 200)))
    height_mm = float(req_data.get("height_mm", config.get("default_height_mm", 150)))

    try:
        from PIL import ImageDraw, ImageFont

        # Build test image at label resolution
        dpi = config.get("printer_dpi", 203) if method == "tcp" else 200
        test_w = int(width_mm / 25.4 * dpi)
        test_h = int(height_mm / 25.4 * dpi)
        test_img = Image.new("RGB", (test_w, test_h), (255, 255, 255))
        draw = ImageDraw.Draw(test_img)

        # Draw test pattern
        draw.rectangle([4, 4, test_w - 4, test_h - 4], outline=(0, 0, 0), width=3)
        draw.line([4, 4, test_w - 4, test_h - 4], fill=(220, 220, 220), width=1)
        draw.line([test_w - 4, 4, 4, test_h - 4], fill=(220, 220, 220), width=1)

        try:
            font = ImageFont.truetype("arial.ttf", max(12, test_h // 12))
            font_sm = ImageFont.truetype("arial.ttf", max(8, test_h // 20))
        except Exception:
            font = ImageFont.load_default()
            font_sm = font

        tx = test_w // 8
        ty = test_h // 4
        draw.text((tx, ty), "GHS Print Agent", fill=(37, 99, 235), font=font)
        draw.text(
            (tx, ty + test_h // 10), "Test Page — OK", fill=(16, 185, 129), font=font
        )
        draw.text(
            (tx, ty + test_h // 5), f"Method: {method}", fill=(0, 0, 0), font=font_sm
        )
        draw.text(
            (tx, ty + 3 * test_h // 10),
            f"Size: {width_mm:.0f}×{height_mm:.0f} mm | {dpi} DPI",
            fill=(0, 0, 0),
            font=font_sm,
        )
        draw.text(
            (tx, ty + 2 * test_h // 5),
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            fill=(100, 116, 139),
            font=font_sm,
        )

        if method == "tcp":
            idx = int(
                req_data.get("tcp_printer_index", config.get("active_printer_index", 0))
            )
            tcp_ps = config.get("tcp_printers", [])
            if not tcp_ps:
                return jsonify({"error": "No TCP printers configured"}), 500
            idx = max(0, min(idx, len(tcp_ps) - 1))
            tcp_p = tcp_ps[idx]
            if not test_tcp_connection(tcp_p["ip"], tcp_p["port"]):
                return (
                    jsonify({"error": f"Cannot reach {tcp_p['ip']}:{tcp_p['port']}"}),
                    503,
                )
            result = tspl_print_image(
                test_img,
                tcp_p["ip"],
                tcp_p["port"],
                width_mm,
                height_mm,
                copies=1,
                dpi=dpi,
                invert=config.get("invert_bitmap", True),
            )
            msg = f"Test page sent to {tcp_p['name']} ({tcp_p['ip']}:{tcp_p['port']})"
        else:
            printer_name = req_data.get("printer", get_printer_name(config))
            result = print_image(test_img, printer_name, width_mm, height_mm)
            msg = f"Test page sent to {printer_name}"

        return jsonify({"success": True, "message": msg, "details": result})

    except Exception as e:
        logging.error(f"Test print failed: {e}")
        return jsonify({"error": str(e)}), 500


# ══════════════════════════════════════════════════════════════════════
# Entry Point
# ══════════════════════════════════════════════════════════════════════


def main():
    parser = argparse.ArgumentParser(description="GHS Label Print Agent v2")
    parser.add_argument("--port", type=int, help="Agent HTTP port (default: 5555)")
    parser.add_argument(
        "--printer", type=str, help="Windows printer name (method=windows)"
    )
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Bind address")
    parser.add_argument(
        "--method",
        type=str,
        choices=["tcp", "windows"],
        help="Print method: tcp (network) or windows (driver)",
    )
    parser.add_argument("--tcp-ip", type=str, help="TCP printer IP address")
    parser.add_argument(
        "--tcp-port", type=int, default=9100, help="TCP printer port (default: 9100)"
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument(
        "--list-printers", action="store_true", help="List printers and exit"
    )
    args = parser.parse_args()

    # Load / create config
    config = load_config()

    # Apply CLI overrides
    if args.port:
        config["port"] = args.port
    if args.host:
        config["host"] = args.host
    if args.printer:
        config["printer_name"] = args.printer
    if args.method:
        config["print_method"] = args.method
    if args.tcp_ip:
        tcp_ps = config.get("tcp_printers", [])
        if tcp_ps:
            tcp_ps[config.get("active_printer_index", 0)]["ip"] = args.tcp_ip
            tcp_ps[config.get("active_printer_index", 0)]["port"] = args.tcp_port
        else:
            tcp_ps = [{"name": "CLI Printer", "ip": args.tcp_ip, "port": args.tcp_port}]
        config["tcp_printers"] = tcp_ps

    # List printers mode
    if args.list_printers:
        method = config.get("print_method", "windows")
        print(f"\n Print method: {method.upper()}")
        print("\n Windows printers:")
        for p in list_printers():
            mark = " ← DEFAULT" if p["is_default"] else ""
            print(f"   • {p['name']}{mark}")
        print("\n TCP printers:")
        for p in list_tcp_printers(config):
            online = "🟢 online" if p["online"] else "🔴 offline"
            active = " ← ACTIVE" if p["active"] else ""
            print(
                f"   [{p['index']}] {p['name']} — {p['ip']}:{p['port']} {online}{active}"
            )
        sys.exit(0)

    # Save config if it doesn't exist yet
    if not CONFIG_FILE.exists():
        save_config(config)

    # Setup logging
    log_level = (
        logging.DEBUG
        if args.debug
        else getattr(logging, config.get("log_level", "INFO"))
    )
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    port = config.get("port", 5555)
    host = config.get("host", "127.0.0.1")
    method = config.get("print_method", "windows")

    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║         🖨️  GHS Label Print Agent  v2.0                 ║")
    print("╠══════════════════════════════════════════════════════════╣")
    print(f"║  Agent URL : http://{host}:{port:<26} ║")
    print(
        f"║  Method    : {'TCP / Network  (TSPL)' if method == 'tcp' else 'Windows GDI (driver)':<36} ║"
    )
    print(
        f"║  Label     : {config.get('default_width_mm', 200)}×{config.get('default_height_mm', 150)} mm{'':>31} ║"
    )

    if method == "tcp":
        tcp_ps = config.get("tcp_printers", [])
        active_idx = config.get("active_printer_index", 0)
        print("╠══════════════════════════════════════════════════════════╣")
        print(f"║  TCP Printers ({len(tcp_ps)} configured):{'':>28} ║")
        for i, tp in enumerate(tcp_ps):
            online = test_tcp_connection(tp["ip"], tp["port"], timeout=2)
            status = "🟢" if online else "🔴"
            active = " ◀" if i == active_idx else "  "
            line = f"  [{i}]{active} {tp.get('name','?')[:18]:18} {tp['ip']}:{tp['port']} {status}"
            print(f"║  {line:<54} ║")
    else:
        printer = get_printer_name(config)
        print(f"║  Printer   : {printer[:43]:<43} ║")

    print("╠══════════════════════════════════════════════════════════╣")
    print("║  Endpoints:                                             ║")
    print("║    GET/POST /status          — Health + printer info    ║")
    print("║    POST     /print           — Print label images       ║")
    print("║    GET      /printers        — List all printers        ║")
    print("║    GET/POST /select_printer  — Switch active printer    ║")
    print("║    POST     /test            — Print test page          ║")
    print("║    GET/POST /configure       — Read/write config        ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()

    app.run(host=host, port=port, debug=args.debug)


if __name__ == "__main__":
    main()
