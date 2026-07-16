from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.graphics.barcode import code128
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth
from typing import Optional
from smart_label import SmartLabelManager
import os
import datetime
import tempfile
import logging
from resource_path import get_base_dir, get_poppler_path

# Version for label tracking — reads from git tags automatically
try:
    from sga_web.version import get_version_display

    SGA_VERSION = get_version_display()
except ImportError:
    SGA_VERSION = "SGA v2.0.0"

try:
    from PIL import Image as PILImage

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


class GHSLabelGenerator:
    """
    Generates GHS/NOM-018-STPS-2015 compliant labels.
    """

    def __init__(self, data_dir, manager=None):
        self.manager = manager if manager else SmartLabelManager(data_dir)
        self.styles = getSampleStyleSheet()
        self._init_styles()
        self._pictogram_cache = {}  # Cache loaded pictogram images

    def _get_pil_image_cached(self, path):
        if not PIL_AVAILABLE:
            return None
        if not hasattr(self, "_pictogram_cache"):
            self._pictogram_cache = {}
        if path in self._pictogram_cache:
            return self._pictogram_cache[path]
        try:
            img = PILImage.open(path).convert("RGBA")
            self._pictogram_cache[path] = img
            return img
        except Exception:
            return None

    def _draw_na_diamond(self, c_pdf, cx, cy, size):
        """Draw a bold 'N/A' label centred at (cx, cy) within a diamond-sized area.

        Used to fill empty pictogram slots in locked-layout templates so
        every slot has content (either the real pictogram or N/A).
        """
        na_fs = max(8, size * 0.30)  # ~30% of diamond size
        c_pdf.saveState()
        c_pdf.setFont("Helvetica-Bold", na_fs)
        c_pdf.setFillColor(colors.Color(0.45, 0.45, 0.45))
        c_pdf.drawCentredString(cx, cy - na_fs / 3, "N/A")
        c_pdf.restoreState()

    def _init_styles(self):
        self.style_title = ParagraphStyle(
            "GHSTitle",
            parent=self.styles["Heading1"],
            fontSize=16,
            leading=20,
            alignment=1,  # Center
            textColor=colors.black,
            fontName="Helvetica-Bold",
        )

        self.style_signal = ParagraphStyle(
            "GHSSignal",
            parent=self.styles["Heading2"],
            fontSize=14,
            leading=16,
            alignment=1,  # Center
            textColor=colors.red,  # NOM-018 doesn't mandate text color, but Red is standard for emphasis
            fontName="Helvetica-Bold",
            spaceBefore=5,
            spaceAfter=5,
        )

        self.style_h_header = ParagraphStyle(
            "GHS_H_Header",
            parent=self.styles["Normal"],
            fontSize=9,
            leading=11,
            textColor=colors.black,
            fontName="Helvetica-Bold",
        )

        self.style_h_body = ParagraphStyle(
            "GHS_H_Body",
            parent=self.styles["Normal"],
            fontSize=8,
            leading=10,
            textColor=colors.black,
        )

        self.style_p_header = ParagraphStyle(
            "GHS_P_Header",
            parent=self.styles["Normal"],
            fontSize=9,
            leading=11,
            textColor=colors.black,
            fontName="Helvetica-Bold",
        )

        self.style_p_body = ParagraphStyle(
            "GHS_P_Body",
            parent=self.styles["Normal"],
            fontSize=7,
            leading=9,
            textColor=colors.black,
        )

        self.style_supplier = ParagraphStyle(
            "GHSSupplier",
            parent=self.styles["Normal"],
            fontSize=7,
            leading=8,
            alignment=1,
            textColor=colors.black,
        )

    def generate_from_template(
        self, product_data, template, output_filename="ghs_label.pdf"
    ):
        """
        Generate a label using a saved template layout.

        Args:
            product_data: dict with product fields
            template: dict with template definition (id, name, width_mm, height_mm, elements[])
            output_filename: path for the output PDF
        """
        import datetime as _dt

        w_mm = template.get("width_mm", 200)
        h_mm = template.get("height_mm", 150)
        w, h = w_mm * mm, h_mm * mm

        rotation = int(template.get("rotation", 0))

        # ═══ PAGE SIZE & ROTATION ═══
        # The design canvas is always w_mm × h_mm.
        # Rotation controls how the content is oriented on the physical page.
        #
        # rotation=0:   PDF page = w × h (landscape if w > h). No transform.
        # rotation=90:  PDF page = h × w (portrait). Content rotated 90° CCW.
        # rotation=270: PDF page = h × w (portrait). Content rotated 90° CW.
        #
        # IMPORTANT: If your physical label stock is landscape (e.g., 200×150mm),
        # use rotation=0 to avoid printer scaling issues. Only use 90/270 if
        # you need the PDF to be portrait for a portrait label printer.

        logging.info("═══ Template PDF Generation ═══")
        logging.info(f"  Design canvas: {w_mm} × {h_mm} mm")
        logging.info(f"  Rotation: {rotation}°")

        if rotation in [90, 270]:
            # Swap page dimensions for the PDF file itself
            c_pdf = canvas.Canvas(output_filename, pagesize=(h, w))
            logging.info(
                f"  PDF page: {h_mm} × {w_mm} mm (portrait, dimensions swapped)"
            )
            logging.warning(
                f"  ⚠️ Rotation {rotation}° creates a {h_mm}×{w_mm}mm page."
            )
            logging.warning(
                f"     If your label stock is {w_mm}×{h_mm}mm, the printer may scale content!"
            )
            logging.warning("     Consider using rotation=0 for landscape labels.")

            # Apply transformation to rotate content
            if rotation == 90:
                c_pdf.translate(h, 0)
                c_pdf.rotate(90)
            elif rotation == 270:
                c_pdf.translate(0, w)
                c_pdf.rotate(-90)
        else:
            c_pdf = canvas.Canvas(output_filename, pagesize=(w, h))
            logging.info(f"  PDF page: {w_mm} × {h_mm} mm (no rotation)")

        # Resolve dynamic field values
        today_str = product_data.get(
            "batch_date", _dt.date.today().strftime("%d/%m/%Y")
        )
        reinsp_override = product_data.get("reinspection_date", "")

        # Helper: resolve reinsp_override into a display string
        def _resolve_reinsp_override(reinsp_val):
            if not reinsp_val or reinsp_val == "00":
                return ""
            try:
                # Handle "00/" sentinel in reinspection date (day-less)
                _rv = str(reinsp_val)
                _rv_parse = _rv
                _rv_had_00 = False
                if _rv.startswith("00/"):
                    _rv_parse = "01/" + _rv[3:]
                    _rv_had_00 = True
                if "-" in _rv_parse:
                    rd = _dt.datetime.strptime(_rv_parse, "%Y-%m-%d")
                else:
                    rd = _dt.datetime.strptime(_rv_parse, "%d/%m/%Y")
                if _rv_had_00:
                    return rd.strftime("%m/%Y")
                return rd.strftime("%d/%m/%Y")
            except Exception:
                return str(reinsp_val)

        try:
            dt = None
            # Handle "00/" sentinel in batch_date (day-less date)
            parse_str = str(today_str)
            had_00_day = False
            if parse_str.startswith("00/"):
                parse_str = "01/" + parse_str[3:]
                had_00_day = True

            if "-" in parse_str:
                dt = _dt.datetime.strptime(parse_str, "%Y-%m-%d")
            elif "/" in parse_str:
                parts = parse_str.split("/")
                if len(parts) == 3:
                    # Check if year is last (len 4)
                    if len(parts[2]) == 4:
                        dt = _dt.datetime(
                            int(parts[2]), int(parts[1]), int(parts[0])
                        )  # DMY
                    elif len(parts[0]) == 4:
                        dt = _dt.datetime(
                            int(parts[0]), int(parts[1]), int(parts[2])
                        )  # YMD

            if dt:
                if had_00_day:
                    elab_date = dt.strftime("%m/%Y")
                else:
                    elab_date = dt.strftime("%d/%m/%Y")
                # Use explicit reinspection_date if provided, otherwise auto-calc +1 year
                if reinsp_override:
                    insp_date = _resolve_reinsp_override(reinsp_override)
                else:
                    try:
                        insp_dt = dt.replace(year=dt.year + 1)
                    except ValueError:
                        insp_dt = dt.replace(year=dt.year + 1, day=28)
                    if had_00_day:
                        insp_date = insp_dt.strftime("%m/%Y")
                    else:
                        insp_date = insp_dt.strftime("%d/%m/%Y")
            else:
                elab_date = today_str
                # Still try to use reinsp_override even if batch date parsing failed
                if reinsp_override:
                    insp_date = _resolve_reinsp_override(reinsp_override)
                else:
                    insp_date = "N/A"
        except Exception:
            elab_date = today_str or _dt.date.today().strftime("%d/%m/%Y")
            # Still try to use reinsp_override even if batch date parsing failed
            if reinsp_override:
                insp_date = _resolve_reinsp_override(reinsp_override)
            else:
                insp_date = "N/A"

        is_almacen2 = template.get("name", "").strip().lower() == "almacen2"
        use_m_y_format = product_data.get("use_m_y_format", False) or is_almacen2

        if use_m_y_format:

            def to_m_y(d_str):
                d_str = str(d_str).strip()
                if not d_str or d_str == "N/A":
                    return d_str
                # Check for DD/MM/YYYY
                if len(d_str) >= 10 and d_str[2] == "/" and d_str[5] == "/":
                    return d_str[3:10]
                # Check for YYYY-MM-DD
                if len(d_str) >= 10 and d_str[4] == "-" and d_str[7] == "-":
                    return f"{d_str[5:7]}/{d_str[0:4]}"
                return d_str

            elab_date = to_m_y(elab_date)
            insp_date = to_m_y(insp_date)

        import decimal

        try:
            p_n = str(product_data.get("quantity", "0"))
            if not p_n.strip():
                p_n = "0"
            peso_neto = decimal.Decimal(p_n)
        except Exception:
            peso_neto = decimal.Decimal("0")

        try:
            p_t = str(product_data.get("peso_tara", "0.0"))
            if not p_t.strip():
                p_t = "0.0"
            peso_tara = decimal.Decimal(p_t)
        except Exception:
            peso_tara = decimal.Decimal("0.0")

        peso_bruto = peso_neto + peso_tara

        # New Rule: Liquids where gross weight is strictly 25kg or net 25 with tara 1.3
        p_type = product_data.get("product_type", "").lower()
        if "liquido" in p_type or "líquido" in p_type:
            if peso_neto == decimal.Decimal("25") and peso_tara == decimal.Decimal(
                "1.3"
            ):
                peso_neto = decimal.Decimal("23.7")
                peso_bruto = decimal.Decimal("25.0")
            elif peso_bruto == decimal.Decimal("25"):
                peso_tara = decimal.Decimal("1.3")
                peso_neto = decimal.Decimal("23.7")

        h_codes = product_data.get("h_codes", [])
        h_stmts = product_data.get("h_statements", [])
        h_text = "\n".join(
            (
                f"{h_codes[i]} - {h_stmts[i]}"
                if i < len(h_stmts) and h_stmts[i]
                else h_codes[i]
            )
            for i in range(len(h_codes))
        )
        p_codes = product_data.get("p_codes", [])
        p_stmts = product_data.get("p_statements", [])
        p_text = "\n".join(
            (
                f"{p_codes[i]} - {p_stmts[i]}"
                if i < len(p_stmts) and p_stmts[i]
                else p_codes[i]
            )
            for i in range(len(p_codes))
        )

        signal = str(product_data.get("signal_word", "")).upper()
        is_no_ghs = signal in (
            "NAN",
            "NONE",
            "NO APLICABLE",
            "NO APLICA",
            "N/A",
            "-",
            "",
        )
        if is_no_ghs:
            signal = ""
        signal = signal.replace("(MAJ)", "").strip()

        # ── Fallback text for empty GHS fields ──
        # When a product has no GHS data the label sections would be completely
        # blank.  Adding contextual N/A messages keeps the label legible and
        # signals that the data is intentionally absent (not a printing error).
        if not h_text:
            h_text = "No se identifican indicaciones de peligro para este producto."
        if not p_text:
            p_text = "Consultar Hoja de Seguridad (HDS) para mayor información."
        if not signal and is_no_ghs:
            signal = "N/A"

        cas_text = (
            f"CAS No. {product_data['cas']}"
            if product_data.get("cas")
            else "CAS No. Mezcla"
        )

        def format_w(w):
            s = str(w)
            if "e" in s.lower():
                s = f"{w:.10f}"
            parts = s.split(".")
            if len(parts) == 1:
                return f"{parts[0]}.00"
            return f"{parts[0]}.{(parts[1] + '00')[:2]}"

        field_values = {
            "process_barcode": "01-ENVASADO",
            "internal_code_barcode": str(product_data.get("internal_code", "")),
            "internal_code_text": str(product_data.get("internal_code", "")),
            "product_name": str(
                product_data.get("name", product_data.get("product_name", ""))
            ),
            "signal_word": signal,
            "cas_number": cas_text,
            "h_statements": h_text,
            "p_statements": p_text,
            "elab_date_value": elab_date,
            "reinsp_date_value": insp_date,
            "lote_value": str(product_data.get("batch_number", "000000")),
            "batch_barcode": str(product_data.get("batch_number", "000000")),
            "peso_bruto_value": f"{format_w(peso_bruto)} KG",
            "peso_tara_value": f"{format_w(peso_tara)} KG",
            "peso_neto_value": f"{format_w(peso_neto)} KG",
            "net_weight_barcode": f"{format_w(peso_neto)} KG",
            "gross_weight_barcode": f"{format_w(peso_bruto)} KG",
        }

        def resolve_image_path(el_field: str, src: str) -> Optional[str]:
            base_dir = get_base_dir()
            candidates = []
            if el_field == "company_logo":
                candidates.extend(
                    [
                        os.path.join(base_dir, "imagenes", "logo_vertical.2.png"),
                        os.path.join(base_dir, "images", "logo_vertical.2.png"),
                        os.path.join(
                            base_dir,
                            "sga_web",
                            "static",
                            "images",
                            "logo_vertical.2.png",
                        ),
                    ]
                )

            if src:
                if src.startswith("/static/"):
                    rel = src.replace("/static/", "", 1)
                    candidates.append(os.path.join(base_dir, "sga_web", "static", rel))
                else:
                    candidates.append(os.path.join(base_dir, src.lstrip("/")))
                    candidates.append(src)

            for candidate in candidates:
                if candidate and os.path.exists(candidate):
                    return candidate
            return None

        def draw_pictograms_grid(picto_names, x_pos, y_top, box_w, box_h):
            if not picto_names:
                return

            count = min(len(picto_names), 9)
            if count <= 4:
                cols, rows = 2, 2
            elif count <= 6:
                cols, rows = 3, 2
            else:
                cols, rows = 3, 3

            cell_w = box_w / cols
            cell_h = box_h / rows
            size = min(cell_w, cell_h)

            for idx in range(count):
                picto_name = picto_names[idx]
                path = self.manager.get_pictogram_path(picto_name)
                if not path:
                    continue

                row = idx // cols
                col = idx % cols
                img_x = x_pos + (col * cell_w) + (cell_w - size) / 2
                img_y = (y_top - ((row + 1) * cell_h)) + (cell_h - size) / 2

                try:
                    p_img = self._get_pil_image_cached(path)
                    if p_img:
                        bg = PILImage.new("RGB", p_img.size, (255, 255, 255))
                        bg.paste(p_img, (0, 0), p_img)
                        from reportlab.lib.utils import ImageReader

                        draw_obj = ImageReader(bg)
                        c_pdf.drawImage(
                            draw_obj,
                            img_x,
                            img_y,
                            width=size,
                            height=size,
                            mask=None,
                            preserveAspectRatio=True,
                        )
                    else:
                        c_pdf.drawImage(
                            path,
                            img_x,
                            img_y,
                            width=size,
                            height=size,
                            mask=None,
                            preserveAspectRatio=True,
                        )
                except Exception as e:
                    logging.warning(f"Template pictogram error for {picto_name}: {e}")

        def _strip_red_border(pil_img):
            import numpy as np

            arr = np.array(pil_img)
            red_mask = (
                (arr[:, :, 0] > 180)
                & (arr[:, :, 1] < 100)
                & (arr[:, :, 2] < 100)
                & (arr[:, :, 3] > 50)
            )
            arr[red_mask, 3] = 0
            result = PILImage.fromarray(arr)
            bbox = result.split()[-1].getbbox()
            if bbox:
                result = result.crop(bbox)

            # Place over white background to flatten alpha
            bg = PILImage.new("RGB", result.size, (255, 255, 255))
            bg.paste(result, (0, 0), result)
            return bg

        def draw_pictograms_locked(
            picto_names, x_pos, y_top, box_w, box_h, picto_size=None, picto_gap=None
        ):
            """Draw pictograms in fixed diamond positions for preprinted labels.

            The red diamond border is stripped from the image so it doesn't
            double-print on pre-printed label stock.

            Always renders all 4 diamond positions (Top, Left, Right, Bottom).
            Empty slots are filled with a bold 'N/A' label.

            Args:
                picto_names: list of pictogram name strings
                x_pos: left edge of bounding box (ReportLab points)
                y_top: top edge of bounding box (ReportLab points, Y-up)
                box_w: bounding box width (points)
                box_h: bounding box height (points)
                picto_size: size to draw each pictogram (points, bounding
                            square of the diamond).  Set this to the
                            preprinted diamond diagonal.  Default = box / 2.
                picto_gap: centre-to-centre distance between adjacent
                           diamonds (points).  Default = picto_size * 0.85
                           (slight overlap matching typical preprint).
            """
            if not picto_names:
                picto_names = []

            if picto_size is None:
                picto_size = min(box_w, box_h) / 2

            if picto_gap is None:
                picto_gap = picto_size * 0.85

            center_x = x_pos + box_w / 2
            center_y = y_top - box_h / 2

            import math

            h_off = picto_gap * math.cos(math.radians(45))
            v_off = picto_gap * math.sin(math.radians(45))

            # Always use all 4 positions: Top, Left, Right, Bottom
            all_positions = [
                (0, v_off),  # Top
                (-h_off, 0),  # Left
                (h_off, 0),  # Right
                (0, -v_off),  # Bottom
            ]

            # Pad picto_names to 4 slots (None = empty = N/A)
            slots = list(picto_names[:4])
            while len(slots) < 4:
                slots.append(None)

            for idx in range(4):
                picto_name = slots[idx]
                ox, oy = all_positions[idx]
                img_x = center_x + ox - (picto_size / 2)
                img_y = center_y + oy - (picto_size / 2)

                if picto_name:
                    # Draw the pictogram image
                    path = self.manager.get_pictogram_path(picto_name)
                    if not path:
                        # Pictogram name exists but image not found — draw N/A
                        self._draw_na_diamond(
                            c_pdf, center_x + ox, center_y + oy, picto_size
                        )
                        continue

                    draw_path = path
                    tmp_path = None
                    try:
                        if PIL_AVAILABLE:
                            try:
                                picto_img = self._get_pil_image_cached(path)
                                picto_img = _strip_red_border(picto_img)
                                from reportlab.lib.utils import ImageReader

                                draw_path = ImageReader(picto_img)
                            except Exception:
                                draw_path = path

                        c_pdf.drawImage(
                            draw_path,
                            img_x,
                            img_y,
                            width=picto_size,
                            height=picto_size,
                            mask=None,
                            preserveAspectRatio=True,
                        )
                    except Exception as e:
                        logging.warning(
                            f"Template locked pictogram error for {picto_name}: {e}"
                        )
                    finally:
                        if tmp_path and os.path.exists(tmp_path):
                            try:
                                os.unlink(tmp_path)
                            except Exception:
                                pass
                else:
                    # Empty slot — draw bold N/A
                    self._draw_na_diamond(
                        c_pdf, center_x + ox, center_y + oy, picto_size
                    )

        def draw_pictograms_dynamic(
            picto_names, x_pos, y_top, box_w, box_h, max_pictos=6
        ):
            """Draw pictograms with size that adapts to the number of pictograms.

            Uses PIL compositing: all pictograms are placed on an off-screen
            transparent canvas, auto-cropped to content, then drawn into
            the bounding box.  Produces the characteristic GHS diamond cluster.

            Layout:
              1 pictogram  -> Centre
              2 pictograms -> Left + Right
              3 pictograms -> Top + Left + Right
              4 pictograms -> Top + Left + Right + Bottom (tighter spacing)
              5-6           -> 4 diamond + extra row below
            """
            if not picto_names:
                return

            count = min(len(picto_names), max_pictos)
            if count == 0:
                return

            if not PIL_AVAILABLE:
                draw_pictograms_grid(picto_names[:count], x_pos, y_top, box_w, box_h)
                return

            try:
                picto_px = 500
                # Reduce spacing for 4+ pictograms so they all fit
                if count <= 3:
                    spacing_px = int(picto_px * 0.55)  # moderate overlap for 1-3
                elif count == 4:
                    spacing_px = int(picto_px * 0.42)  # tighter for 4 (diamond)
                else:
                    spacing_px = int(picto_px * 0.38)  # tightest for 5-6
                canvas_size = int(picto_px * 3.5)  # generous canvas for 4+

                # Transparent background so getbbox() auto-crops to content
                composite = PILImage.new(
                    "RGBA", (canvas_size, canvas_size), (255, 255, 255, 0)
                )
                cx_img, cy_img = canvas_size // 2, canvas_size // 2

                # Diamond cluster offsets (adaptive spacing)
                diamond_offsets = [
                    (0, -spacing_px),  # Top
                    (-spacing_px, 0),  # Left
                    (spacing_px, 0),  # Right
                    (0, spacing_px),  # Bottom
                ]
                extra_offsets = [
                    (-spacing_px, spacing_px * 2),  # Bottom-left extra
                    (spacing_px, spacing_px * 2),  # Bottom-right extra
                ]

                # Adjust positions for fewer pictograms
                if count == 1:
                    positions = [(0, 0)]  # Centre
                elif count == 2:
                    positions = [(-spacing_px, 0), (spacing_px, 0)]  # Left + Right
                elif count == 3:
                    positions = [
                        (0, -spacing_px),  # Top
                        (-spacing_px, 0),  # Left
                        (spacing_px, 0),  # Right
                    ]
                else:
                    # 4+ pictograms: diamond cluster + extras
                    positions = list(diamond_offsets[: min(count, 4)])
                    for i in range(4, count):
                        if i - 4 < len(extra_offsets):
                            positions.append(extra_offsets[i - 4])

                placed = 0
                for idx in range(count):
                    picto_name = picto_names[idx]
                    path = self.manager.get_pictogram_path(picto_name)
                    if not path:
                        logging.warning(
                            f"Dynamic pictogram: no path for '{picto_name}'"
                        )
                        continue

                    picto_img = self._get_pil_image_cached(path)
                    resampling_filter = getattr(PILImage, "Resampling", PILImage)
                    picto_img = picto_img.resize(
                        (picto_px, picto_px),
                        getattr(resampling_filter, "LANCZOS", PILImage.LANCZOS),
                    )

                    ox, oy = positions[idx]
                    paste_x = cx_img + ox - picto_px // 2
                    paste_y = cy_img + oy - picto_px // 2
                    composite.paste(picto_img, (paste_x, paste_y), picto_img)
                    placed += 1

                if placed == 0:
                    return

                # Auto-crop to content bounding box (maximises size)
                bbox = composite.getbbox()
                if not bbox:
                    return
                composite = composite.crop(bbox)
                logging.info(
                    f"Dynamic pictogram composite: {placed}/{count} placed, crop={composite.size}"
                )

                # Create ImageReader instead of tempfile
                from reportlab.lib.utils import ImageReader

                bg = PILImage.new("RGB", composite.size, (255, 255, 255))
                bg.paste(composite, (0, 0), composite)
                draw_img = ImageReader(bg)

                # Draw into the template bounding box, preserving aspect ratio
                # Center the composite in the box
                comp_w, comp_h = composite.size
                aspect = comp_w / comp_h

                if box_w / box_h > aspect:
                    # Box is wider than composite — fit to height
                    draw_h = box_h
                    draw_w = box_h * aspect
                else:
                    # Box is taller than composite — fit to width
                    draw_w = box_w
                    draw_h = box_w / aspect

                draw_x = x_pos + (box_w - draw_w) / 2
                draw_y = (y_top - box_h) + (box_h - draw_h) / 2

                # mask=None speeds up reportlab exponentially
                c_pdf.drawImage(
                    draw_img,
                    draw_x,
                    draw_y,
                    width=draw_w,
                    height=draw_h,
                    mask=None,
                    preserveAspectRatio=True,
                )
            except Exception as e:
                logging.warning(f"Dynamic pictogram composite error: {e}")
                import traceback

                traceback.print_exc()

        # Render each template element
        for el in template.get("elements", []):
            el_type = el.get("type", "text")
            field = el.get("field", "")

            # HACK: Force CAS Number to multiline so it wraps properly if long
            if field == "cas_number" and el_type == "text":
                el_type = "multiline"
                # Protect edgecase: JSON 'height_mm: null' parses as None
                _h = el.get("height_mm")
                if _h is None:
                    _h = 0

                if _h < 7:
                    el["height_mm"] = 7.0

            x = el.get("x_mm", 0) * mm
            # Template uses top-down Y; ReportLab uses bottom-up Y
            y = h - el.get("y_mm", 0) * mm

            font_size = el.get("font_size", 10)
            font_weight = el.get("font_weight", "normal")
            font_name = "Helvetica-Bold" if font_weight == "bold" else "Helvetica"
            alignment = el.get("alignment", "left")
            el_color = el.get("color", "#000000")

            try:
                r_c = int(el_color[1:3], 16) / 255
                g_c = int(el_color[3:5], 16) / 255
                b_c = int(el_color[5:7], 16) / 255
                draw_color = colors.Color(r_c, g_c, b_c)
            except Exception:
                draw_color = colors.black

            if el.get("custom_text"):
                text_val = el["custom_text"]
            elif field in field_values:
                text_val = field_values[field]
            else:
                text_val = ""

            if el_type in ("text", "static", "multiline", "barcode") and not text_val:
                continue

            width_el = el.get("width_mm", 50)

            if el_type == "line":
                line_w = el.get("line_width", 1)
                c_pdf.setLineWidth(line_w)
                c_pdf.setStrokeColor(draw_color)
                c_pdf.line(x, y, x + width_el * mm, y)
                c_pdf.setStrokeColor(colors.black)

            elif el_type == "barcode":
                bar_h = el.get("bar_height_mm", 8) * mm
                bar_w = el.get("bar_width", 1)
                auto_fit = el.get("auto_fit", False)
                try:
                    txt_str = str(text_val)
                    bc = code128.Code128(txt_str, barHeight=bar_h, barWidth=bar_w)
                    # Always honor the template slot width when present.
                    # This prevents silent clipping at page edges when a barcode
                    # is wider than its assigned box and auto_fit is disabled.
                    available_w_pts = (
                        width_el * mm if width_el and width_el > 0 else bc.width
                    )
                    min_bar_w = float(el.get("min_bar_width", 0.7))

                    if auto_fit and width_el > 0 and bc.width > 0:
                        target_bar_w = max(
                            min_bar_w, bar_w * (available_w_pts / bc.width)
                        )
                        bc = code128.Code128(
                            txt_str, barHeight=bar_h, barWidth=target_bar_w
                        )
                        if bc.width > available_w_pts:
                            attempt_bw = target_bar_w
                            while bc.width > available_w_pts and attempt_bw > min_bar_w:
                                attempt_bw -= 0.02
                                bc = code128.Code128(
                                    txt_str,
                                    barHeight=bar_h,
                                    barWidth=max(min_bar_w, attempt_bw),
                                )

                    if not auto_fit and width_el > 0 and bc.width > available_w_pts:
                        logging.warning(
                            "Barcode '%s' (%s) exceeds slot (%.2fmm > %.2fmm). Applying safety scale.",
                            field,
                            txt_str,
                            bc.width / mm,
                            available_w_pts / mm,
                        )

                    draw_w_pts = min(bc.width, available_w_pts)
                    if alignment == "center" and width_el > 0:
                        draw_x = x + max((available_w_pts - draw_w_pts) / 2, 0)
                    elif alignment == "right" and width_el > 0:
                        draw_x = x + max(available_w_pts - draw_w_pts, 0)
                    else:
                        draw_x = x

                    if bc.width > available_w_pts and bc.width > 0:
                        scale_factor = available_w_pts / bc.width
                        c_pdf.saveState()
                        c_pdf.translate(draw_x, y - bar_h)
                        c_pdf.scale(scale_factor, 1)
                        bc.drawOn(c_pdf, 0, 0)
                        c_pdf.restoreState()
                        draw_w_pts = available_w_pts
                    else:
                        bc.drawOn(c_pdf, draw_x, y - bar_h)
                        draw_w_pts = bc.width

                    if el.get("show_text", True):
                        c_pdf.setFont(font_name, font_size)
                        c_pdf.setFillColor(draw_color)
                        txt_w = stringWidth(txt_str, font_name, font_size)
                        txt_fs = font_size
                        text_limit_pts = available_w_pts if width_el > 0 else draw_w_pts
                        if txt_w > text_limit_pts and txt_w > 0:
                            txt_fs = max(4, font_size * (text_limit_pts / txt_w))
                            c_pdf.setFont(font_name, txt_fs)
                        c_pdf.drawCentredString(
                            draw_x + draw_w_pts / 2, y - bar_h - txt_fs - 1, txt_str
                        )
                        c_pdf.setFillColor(colors.black)
                except Exception as e:
                    logging.warning(f"Template barcode error for {field}: {e}")

            elif el_type == "multiline":
                # Dynamic multiline: auto-size font to fit within bounding box
                box_h_el = el.get("height_mm")
                box_w_pts = width_el * mm
                raw_lines = str(text_val).split("\n")

                if box_h_el and box_h_el > 0:
                    box_h_pts = box_h_el * mm
                    # --- Word-wrap then auto-shrink to fit the bounding box ---

                    def _wrap_lines(lines, fn, fs, max_w):
                        """Word-wrap lines to fit within max_w at the given font/size."""
                        wrapped = []
                        for ln in lines:
                            words = ln.split()
                            if not words:
                                wrapped.append("")
                                continue
                            cur = words[0]
                            for w in words[1:]:
                                test = cur + " " + w
                                if stringWidth(test, fn, fs) <= max_w:
                                    cur = test
                                else:
                                    wrapped.append(cur)
                                    cur = w
                            wrapped.append(cur)
                        return wrapped

                    # Start from the configured font_size and shrink until it fits
                    best_fs = font_size
                    min_fs = 3.0  # never go below 3pt
                    final_lines = raw_lines
                    for attempt_fs_10 in range(
                        int(font_size * 10), int(min_fs * 10) - 1, -2
                    ):
                        attempt_fs = attempt_fs_10 / 10.0
                        wrapped = _wrap_lines(
                            raw_lines, font_name, attempt_fs, box_w_pts
                        )
                        line_h = (attempt_fs + 1.5) * 1.15
                        total_h = len(wrapped) * line_h
                        if total_h <= box_h_pts:
                            best_fs = attempt_fs
                            final_lines = wrapped
                            break
                    else:
                        # Even at min_fs it doesn't fit — use min_fs and clip
                        best_fs = min_fs
                        final_lines = _wrap_lines(
                            raw_lines, font_name, best_fs, box_w_pts
                        )

                    # Draw with clipping rectangle
                    c_pdf.saveState()
                    clip_path = c_pdf.beginPath()
                    clip_y_bottom = y - box_h_pts
                    clip_path.rect(x, clip_y_bottom, box_w_pts, box_h_pts)
                    c_pdf.clipPath(clip_path, stroke=0)

                    c_pdf.setFont(font_name, best_fs)
                    c_pdf.setFillColor(draw_color)
                    line_h = (best_fs + 1.5) * 1.15
                    for i, line in enumerate(final_lines):
                        line_y = y - (i * line_h) - best_fs
                        if line_y < clip_y_bottom:
                            break
                        if alignment == "center":
                            c_pdf.drawCentredString(x + box_w_pts / 2, line_y, line)
                        elif alignment == "right":
                            c_pdf.drawRightString(x + box_w_pts, line_y, line)
                        else:
                            c_pdf.drawString(x, line_y, line)
                    c_pdf.restoreState()
                else:
                    # No height constraint — original fixed-size rendering
                    c_pdf.setFont(font_name, font_size)
                    c_pdf.setFillColor(draw_color)
                    line_h = (font_size + 2) * 0.352 * mm
                    for i, line in enumerate(raw_lines):
                        line_y = y - (i * line_h) - font_size
                        if alignment == "center":
                            c_pdf.drawCentredString(
                                x + (width_el * mm) / 2, line_y, line
                            )
                        elif alignment == "right":
                            c_pdf.drawRightString(x + width_el * mm, line_y, line)
                        else:
                            c_pdf.drawString(x, line_y, line)
                    c_pdf.setFillColor(colors.black)

            elif el_type == "image":
                img_path = resolve_image_path(field, el.get("src", ""))
                if not img_path:
                    continue
                img_w = el.get("width_mm", 20) * mm
                img_h = el.get("height_mm", 20) * mm
                img_y = y - img_h
                try:
                    el_img = self._get_pil_image_cached(img_path)
                    if el_img:
                        bg = PILImage.new("RGB", el_img.size, (255, 255, 255))
                        bg.paste(el_img, (0, 0), el_img)
                        from reportlab.lib.utils import ImageReader

                        draw_obj = ImageReader(bg)
                        c_pdf.drawImage(
                            draw_obj,
                            x,
                            img_y,
                            width=img_w,
                            height=img_h,
                            mask=None,
                            preserveAspectRatio=True,
                        )
                    else:
                        c_pdf.drawImage(
                            img_path,
                            x,
                            img_y,
                            width=img_w,
                            height=img_h,
                            mask=None,
                            preserveAspectRatio=True,
                        )
                except Exception as e:
                    logging.warning(f"Template image error for {field}: {e}")

            elif el_type == "pictogram_group":
                box_w = el.get("width_mm", 40) * mm
                box_h = el.get("height_mm", 40) * mm
                picto_names = product_data.get("pictograms", [])
                if picto_names:
                    draw_pictograms_grid(picto_names, x, y, box_w, box_h)
                else:
                    # Fallback for products with no pictograms
                    c_pdf.saveState()
                    c_pdf.setFont("Helvetica", 9)
                    c_pdf.setFillColor(colors.Color(0.45, 0.45, 0.45))
                    c_pdf.drawCentredString(
                        x + box_w / 2, y - box_h / 2, "Sin pictogramas"
                    )
                    c_pdf.drawCentredString(
                        x + box_w / 2, y - box_h / 2 - 12, "GHS aplicables"
                    )
                    c_pdf.restoreState()

            elif el_type == "pictogram_group_locked":
                picto_names = product_data.get("pictograms", [])
                box_w = el.get("width_mm", 70) * mm
                box_h = el.get("height_mm", 70) * mm
                # Support both property names (picto_square_mm from designer, picto_size_mm legacy)
                p_size = el.get("picto_square_mm", None) or el.get(
                    "picto_size_mm", None
                )
                if p_size is not None:
                    p_size = p_size * mm
                p_gap = el.get("picto_gap_mm", None)
                if p_gap is not None:
                    p_gap = p_gap * mm
                draw_pictograms_locked(picto_names, x, y, box_w, box_h, p_size, p_gap)

            elif el_type == "pictogram_group_dynamic":
                picto_names = product_data.get("pictograms", [])
                box_w = el.get("width_mm", 60) * mm
                box_h = el.get("height_mm", 60) * mm
                max_pictos = el.get("max_pictos", 6)
                if picto_names:
                    draw_pictograms_dynamic(picto_names, x, y, box_w, box_h, max_pictos)
                else:
                    c_pdf.saveState()
                    c_pdf.setFont("Helvetica", 9)
                    c_pdf.setFillColor(colors.Color(0.45, 0.45, 0.45))
                    c_pdf.drawCentredString(
                        x + box_w / 2, y - box_h / 2, "Sin pictogramas"
                    )
                    c_pdf.drawCentredString(
                        x + box_w / 2, y - box_h / 2 - 12, "GHS aplicables"
                    )
                    c_pdf.restoreState()

            else:  # text, static
                # ── Auto-shrink: reduce font until text fits within width_mm ──
                auto_fit = el.get("auto_fit", False)
                box_w_pts = width_el * mm
                text_str = str(text_val)
                best_fs = font_size
                if auto_fit and box_w_pts > 0:
                    min_fs = 4.0  # never go below 4pt for readability
                    tw = stringWidth(text_str, font_name, best_fs)
                    if tw > box_w_pts:
                        # Shrink font size proportionally, then verify
                        best_fs = max(min_fs, font_size * (box_w_pts / tw))
                        # Fine-tune: ensure it truly fits
                        while (
                            stringWidth(text_str, font_name, best_fs) > box_w_pts
                            and best_fs > min_fs
                        ):
                            best_fs -= 0.2
                        best_fs = max(min_fs, best_fs)

                # Optional height_mm bounding box — clip if text still overflows
                box_h_el = el.get("height_mm")
                if box_h_el and box_h_el > 0:
                    box_h_pts = box_h_el * mm
                    c_pdf.saveState()
                    clip_path = c_pdf.beginPath()
                    clip_y_bottom = y - box_h_pts
                    clip_path.rect(x, clip_y_bottom, box_w_pts, box_h_pts)
                    c_pdf.clipPath(clip_path, stroke=0)

                c_pdf.setFont(font_name, best_fs)
                c_pdf.setFillColor(draw_color)
                text_y = y - best_fs
                if alignment == "center":
                    c_pdf.drawCentredString(x + box_w_pts / 2, text_y, text_str)
                elif alignment == "right":
                    c_pdf.drawRightString(x + box_w_pts, text_y, text_str)
                else:
                    c_pdf.drawString(x, text_y, text_str)
                c_pdf.setFillColor(colors.black)

                if box_h_el and box_h_el > 0:
                    c_pdf.restoreState()

        # Debug grid removed — production labels should be clean

        c_pdf.save()
        logging.info(f"Template label generated: {output_filename}")
        logging.info(f"  Design canvas: {w_mm} x {h_mm} mm")
        logging.info(f"  Rotation: {rotation}°")
        print(f"Template label generated: {output_filename}")
        print(f"  PDF page size: {w_mm} x {h_mm} mm (Rotation: {rotation}°)")

    def generate_preview(self, product_code_or_data, dpi=150):
        """
        Generate a PIL Image preview of the label.
        Uses the exact same rendering as generate_label() but converts to image.

        Args:
            product_code_or_data: Product code string or product data dict
            dpi: Resolution for the preview image (default 150)

        Returns:
            PIL.Image object or None if generation fails
        """

        try:
            # Generate PDF to a temporary file (needed for pdf2image on Windows)
            with tempfile.NamedTemporaryFile(
                mode="wb", suffix=".pdf", delete=False
            ) as tmp_file:
                tmp_path = tmp_file.name

            # Use the exact same rendering as generate_label
            self.generate_label(product_code_or_data, tmp_path)

            # Convert PDF to image using pdf2image
            try:
                from pdf2image import convert_from_path

                # Use centralized Poppler path resolution
                poppler_path = get_poppler_path()
                if poppler_path:
                    print(f"[DEBUG] Using Poppler at: {poppler_path}")
                else:
                    print("[WARNING] Poppler not found - PDF preview may fail")

                # Convert to image
                images = convert_from_path(
                    tmp_path,
                    dpi=dpi,
                    first_page=1,
                    last_page=1,
                    poppler_path=poppler_path,
                )

                if images:
                    preview_img = images[0]
                    # Embed DPI metadata so the image reports correct physical size
                    # Without this, OS assumes 72 DPI and dimensions appear ~2x too large
                    preview_img.info["dpi"] = (dpi, dpi)
                    return preview_img

            except ImportError:
                print("[WARNING] pdf2image not available for preview generation")
                return None
            except Exception as e:
                print(f"[WARNING] PDF to image conversion failed: {e}")
                return None
            finally:
                # Clean up temp file
                try:
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)
                except Exception:
                    pass

        except Exception as e:
            print(f"[ERROR] Preview generation failed: {e}")
            import traceback

            traceback.print_exc()
            return None

        return None

    def generate_label(
        self, product_code_or_data, output_filename="ghs_label.pdf", supplier_info=None
    ):
        """
        Generate a GHS/NOM-018 label as a PDF file.

        COORDINATE SYSTEM:
          Origin (0,0) = BOTTOM-LEFT corner of the page
          X increases going RIGHT  (0 = left edge,   w=150mm = right edge)
          Y increases going UP     (0 = bottom edge, h=100mm = top edge)
          All positions use mm units: e.g. 3*mm = 3 millimeters from edge

        QUICK ADJUSTMENT GUIDE:
          Move RIGHT  → increase X    |  Move LEFT → decrease X
          Move UP     → increase Y    |  Move DOWN → decrease Y
          Bigger text → increase font  |  Taller barcode → increase barHeight

        LABEL LAYOUT MAP (Y from bottom, X from left):
        ┌───────────────────────────────────────────────┐ Y=100mm (top)
        │  SECTION 1: HEADER  (Y=74mm to Y=100mm)       │
        │  Process barcode(TL), Product name(C),        │
        │  Internal code barcode(TR), Signal word, CAS  │
        ├───────────────────────────────────────────────┤ Y=74mm
        │  SECTION 2: CONTENT  (Y=24mm to Y=74mm)       │
        │  LEFT: H+P statements | RIGHT: Pictograms+Logo│
        ├──────────────────────────┬────────────────────┤ Y=24mm
        │  SEC 3: BOTTOM LEFT      │  SEC 3: WEIGHTS    │
        │  Dates, LOTE, Barcodes   │  Bruto/Tara/Neto   │
        │  X=3→105mm               │  X=105→147mm       │
        └──────────────────────────┴────────────────────┘ Y=0mm
          SECTION 4: FOOTER (address at Y=0.5mm)
        """
        if isinstance(product_code_or_data, dict):
            product = product_code_or_data
        else:
            product = self.manager.get_product_data(product_code_or_data)

        if not product:
            print("Product data not found!")
            return

        # ═══ CANVAS SETUP ═══
        # Page defaults: 150mm wide × 100mm tall (Standard)
        # Warehouse 2 (Tlaquepaque?): 200mm wide x 155mm tall

        warehouse = str(product.get("warehouse", "")).strip()

        if warehouse == "02" or warehouse == "2":
            w_mm, h_mm = 200, 150
            logging.info(f"Generating large label (20x15cm) for Warehouse {warehouse}")
        else:
            w_mm, h_mm = 150, 100

        w, h = w_mm * mm, h_mm * mm
        c = canvas.Canvas(output_filename, pagesize=(w, h))

        # ═══ SECTION 1: HEADER (Y=74mm to Y=100mm) ═══

        # --- Process Barcode (TOP-LEFT) ---
        process_code = "01-ENVASADO"
        # barHeight=tall, barWidth=1=normal bar thickness
        bc1 = code128.Code128(process_code, barHeight=8 * mm, barWidth=0.75)
        bc1.drawOn(
            c, 0, h - 12 * mm
        )  # X=0 from left edge, Y=88mm from bottom (near top-left)
        c.setFont("Helvetica", 7)  # 7pt font for label below barcode
        c.drawCentredString(
            bc1.width / 2, h - 15 * mm, process_code
        )  # Text centered under barcode, Y=85mm

        # --- Internal Code Barcode (TOP-RIGHT) ---
        internal_code = str(product["internal_code"])
        # barWidth=1.25 = wider bars than process code
        bc2 = code128.Code128(internal_code, barHeight=7 * mm, barWidth=0.75)
        bc2_width = bc2.width  # Width auto-calculated from code length
        bc2_x = w - bc2_width - 3 * mm  # X = right-aligned, 3mm from right edge
        bc2.drawOn(c, bc2_x, h - 12 * mm)  # Y=88mm (same line as process barcode)
        c.drawCentredString(
            bc2_x + bc2_width / 2, h - 15 * mm, internal_code
        )  # Text centered under barcode

        # --- Product Name (CENTER) ---
        font_size = 18  # Default for short names (<=25 chars)
        if len(product["name"]) > 25:
            font_size = 16  # Medium names
        if len(product["name"]) > 35:
            font_size = 14  # Long names
        if len(product["name"]) > 45:
            font_size = 12  # Very long names

        c.setFont("Helvetica-Bold", font_size)
        c.drawCentredString(
            w / 2, h - 21 * mm, product["name"]
        )  # Centered X=75mm, Y=79mm

        # --- Signal Word (TOP-RIGHT, below internal code barcode) ---
        # "PELIGRO" = red, "ATENCIÓN" = black, empty/NA = gray "N/A"
        signal = str(product.get("signal_word", "")).upper()
        if signal in ("NAN", "NONE"):
            signal = ""
        is_no_ghs = signal in ("NO APLICABLE", "NO APLICA", "N/A", "-", "")
        if is_no_ghs:
            signal = "N/A"
        signal = signal.replace("(MAJ)", "").strip()
        if signal:
            if signal == "N/A":
                signal_color = colors.Color(0.45, 0.45, 0.45)
            elif signal == "PELIGRO":
                signal_color = colors.red
            else:
                signal_color = colors.black
            c.setFillColor(signal_color)
            c.setFont("Helvetica-Bold", 13)  # 13pt bold
            c.drawRightString(
                w - 1 * mm, h - 25 * mm, signal
            )  # Right-aligned, X=147mm, Y=78mm
            c.setFillColor(colors.black)  # Reset color to black

        # --- CAS Number (small text, left-aligned below product name) ---
        c.setFont("Helvetica", 6)  # 6pt small text
        cas_value = product.get("cas")
        cas_text = f"CAS No. {cas_value}" if cas_value else "CAS No. Mezcla"

        import textwrap

        cas_lines = textwrap.wrap(cas_text, width=20)
        # Calculate starting Y to keep the lowest line at h - 24.5 mm
        # Line spacing is 2.5 mm. So if 2 lines, we start 2.5 mm higher (h - 22.0 mm).
        y_cas = (h - 24.5 * mm) + ((len(cas_lines) - 1) * 2.5 * mm)

        for line in cas_lines:
            c.drawString(3 * mm, y_cas, line)
            y_cas -= 2.5 * mm  # Next line spacing

        # --- Header Separator Line ---
        c.setLineWidth(0.5)  # 0.5pt thin horizontal line
        c.line(
            3 * mm, h - 26 * mm, w - 3 * mm, h - 26 * mm
        )  # Y=74mm, from X=3mm to X=147mm

        # ═══ SECTION 2: MAIN CONTENT (Y=24mm to Y=74mm) ═══
        # Two-column layout: LEFT = H+P text, RIGHT = Pictograms + Logo
        #
        content_top = h - 26 * mm  # Y=74mm — top of content (below header line)
        content_bottom = 24 * mm  # Y=24mm — bottom of content (above bottom section)
        left_margin = 3 * mm  # 3mm left padding
        right_margin = 3 * mm  # 3mm right padding

        # --- Right Column (pictograms + logo) ---
        right_col_width = 75 * mm  # 75mm wide
        right_col_x = w - right_col_width - right_margin  # X=72mm

        # --- Company Logo size ---
        logo_sub_width = 15 * mm  # Logo width  (← adjust to resize)
        logo_sub_height = 15 * mm  # Logo height (← adjust to resize)

        # Left column: H and P statements (text only)
        left_col_width = right_col_x - left_margin - 2 * mm  # 2mm gap between columns

        # Vertical separator line between columns
        c.setLineWidth(0.3)
        c.setStrokeColor(colors.Color(0.75, 0.75, 0.75))  # Light gray
        c.line(right_col_x - 1 * mm, content_top, right_col_x - 1 * mm, content_bottom)
        c.setStrokeColor(colors.black)

        # --- RIGHT COLUMN: Company Logo (top-right corner, 50% reduced) ---
        if not hasattr(self, "_company_logo_path_cache"):
            self._company_logo_path_cache = None

        if self._company_logo_path_cache and os.path.exists(
            self._company_logo_path_cache
        ):
            company_logo_path = self._company_logo_path_cache
        else:
            try:
                from resource_path import get_base_dir

                base_dir = get_base_dir()
                # Try 'imagenes' first (where user put the file)
                company_logo_path = os.path.join(
                    base_dir, "imagenes", "logo_vertical.2.png"
                )
                if not os.path.exists(company_logo_path):
                    # Fallback to 'images' (legacy/resource_path default)
                    company_logo_path = os.path.join(
                        base_dir, "images", "logo_vertical.2.png"
                    )
            except ImportError:
                # Fallback if resource_path module is missing
                if os.path.exists(os.path.join("imagenes", "logo_vertical.2.png")):
                    company_logo_path = os.path.join("imagenes", "logo_vertical.2.png")
                else:
                    company_logo_path = os.path.join("images", "logo_vertical.2.png")

            if os.path.exists(company_logo_path):
                self._company_logo_path_cache = company_logo_path

        if os.path.exists(company_logo_path):
            try:
                logo_x = (
                    w - logo_sub_width - right_margin - 1 * mm
                )  # Top-right corner #Horizontal
                logo_y = content_top - logo_sub_height - 30 * mm  # Vertical
                logo_img = self._get_pil_image_cached(company_logo_path)
                if logo_img:
                    bg = PILImage.new("RGB", logo_img.size, (255, 255, 255))
                    bg.paste(logo_img, (0, 0), logo_img)
                    resampling_filter = getattr(PILImage, "Resampling", PILImage)
                    bg.thumbnail(
                        (600, 600),
                        getattr(resampling_filter, "LANCZOS", PILImage.LANCZOS),
                    )
                    from reportlab.lib.utils import ImageReader

                    draw_obj = ImageReader(bg)
                    c.drawImage(
                        draw_obj,
                        logo_x,
                        logo_y,
                        width=logo_sub_width,
                        height=logo_sub_height,
                        mask=None,
                        preserveAspectRatio=True,
                    )
                else:
                    c.drawImage(
                        company_logo_path,
                        logo_x,
                        logo_y,
                        width=logo_sub_width,
                        height=logo_sub_height,
                        mask=None,
                        preserveAspectRatio=True,
                    )
            except Exception as e:
                print(f"[DEBUG] Company logo error: {e}")

        # --- RIGHT COLUMN: Pictograms (40% bigger) ---
        picto_names = product.get("pictograms", [])
        num_pictos = len(picto_names)

        # Pictograms in diamond/grid arrangement — 40% larger than original
        picto_px = 500  # 235 * 1.4 = 329 (40% bigger)

        if PIL_AVAILABLE and num_pictos > 0:
            try:
                # Adaptive spacing: tighter for 4+ pictograms so they all fit
                if num_pictos <= 3:
                    spacing_px = int(picto_px * 0.44)
                    canvas_size = int(picto_px * 2.3)
                elif num_pictos == 4:
                    spacing_px = int(picto_px * 0.35)
                    canvas_size = int(picto_px * 2.5)
                else:
                    spacing_px = int(picto_px * 0.32)
                    canvas_size = int(picto_px * 3.0)

                # Use white opaque background to avoid black-box rendering in ReportLab
                composite = PILImage.new(
                    "RGBA", (canvas_size, canvas_size), (255, 255, 255, 255)
                )
                cx, cy = canvas_size // 2, canvas_size // 2

                diamond_offsets = [
                    (0, -spacing_px),  # Top
                    (-spacing_px, 0),  # Left
                    (spacing_px, 0),  # Right
                    (0, spacing_px),  # Bottom
                ]
                extra_offsets = [
                    (-spacing_px, spacing_px * 2),  # Bottom-left extra
                    (spacing_px, spacing_px * 2),  # Bottom-right extra
                ]

                # Build adaptive positions based on count
                if num_pictos == 1:
                    positions = [(0, 0)]
                elif num_pictos == 2:
                    positions = [(-spacing_px, 0), (spacing_px, 0)]
                elif num_pictos == 3:
                    positions = [
                        (0, -spacing_px),
                        (-spacing_px, 0),
                        (spacing_px, 0),
                    ]
                else:
                    # 4+ pictograms: diamond + extras
                    positions = list(diamond_offsets[: min(num_pictos, 4)])
                    for i in range(4, min(num_pictos, 6)):
                        if i - 4 < len(extra_offsets):
                            positions.append(extra_offsets[i - 4])

                for idx, picto_name in enumerate(picto_names[:6]):
                    if idx >= len(positions):
                        break
                    path = self.manager.get_pictogram_path(picto_name)
                    if path:
                        picto_img = self._get_pil_image_cached(path)
                        resampling_filter = getattr(PILImage, "Resampling", PILImage)
                        picto_img = picto_img.resize(
                            (picto_px, picto_px),
                            getattr(resampling_filter, "LANCZOS", PILImage.LANCZOS),
                        )

                        ox, oy = positions[idx]
                        paste_x = cx + ox - picto_px // 2
                        paste_y = cy + oy - picto_px // 2
                        composite.paste(picto_img, (paste_x, paste_y), picto_img)

                # Crop to content to maximize size
                bbox = composite.getbbox()
                if bbox:
                    composite = composite.crop(bbox)

                # Size and position: fill the right column (excluding logo corner)
                # Use max available space
                composite_size = min(right_col_width, content_top - content_bottom)

                # Center in the available space
                picto_x = right_col_x + (right_col_width - composite_size) / 2
                picto_y = (
                    content_bottom + (content_top - content_bottom - composite_size) / 2
                )

                from reportlab.lib.utils import ImageReader

                bg = PILImage.new("RGB", composite.size, (255, 255, 255))
                bg.paste(composite, (0, 0), composite)
                draw_img = ImageReader(bg)

                c.drawImage(
                    draw_img,
                    picto_x,
                    picto_y,
                    width=composite_size,
                    height=composite_size,
                    mask=None,
                    preserveAspectRatio=True,
                    anchor="c",
                )

            except Exception as e:
                print(f"[DEBUG] Composite pictogram error: {e}")
                import traceback

                traceback.print_exc()
        elif num_pictos == 0:
            # Fallback: draw a "no pictograms" message in the right column
            c.saveState()
            c.setFont("Helvetica", 9)
            c.setFillColor(colors.Color(0.45, 0.45, 0.45))
            center_x = right_col_x + right_col_width / 2
            center_y = content_bottom + (content_top - content_bottom) / 2
            c.drawCentredString(center_x, center_y + 5, "Sin pictogramas")
            c.drawCentredString(center_x, center_y - 8, "GHS aplicables")
            c.restoreState()

        # --- LEFT COLUMN: H Statements + P Statements ---
        # Helper: wrap text to fit pixel width using font metrics
        def wrap_text(text, font_name, font_size, max_width):
            """Word-wrap text to fit within max_width using actual font metrics."""
            words = text.split(" ")
            lines = []
            current_line = ""
            for word in words:
                test_line = f"{current_line} {word}".strip() if current_line else word
                if stringWidth(test_line, font_name, font_size) <= max_width:
                    current_line = test_line
                else:
                    if current_line:
                        lines.append(current_line)
                    current_line = word
            if current_line:
                lines.append(current_line)
            return lines

        # --- H Statements (INDICACIONES DE PELIGRO) ---
        h_font_name = "Helvetica"
        h_font_size = 5.5
        h_line_height = 3 * mm
        h_header_font_size = 7

        c.setFont("Helvetica-Bold", h_header_font_size)
        c.drawString(left_margin, content_top - 5 * mm, "INDICACIONES DE PELIGRO:")

        h_codes = product.get("h_codes", [])
        h_statements = product.get("h_statements", [])

        h_lines = []
        for i, code in enumerate(h_codes):
            if i < len(h_statements) and h_statements[i]:
                h_lines.append(f"{code} - {h_statements[i]}")
            else:
                h_lines.append(code)
        # Fallback when no H-statements exist
        if not h_lines:
            h_lines = ["No se identifican indicaciones de peligro para este producto."]

        c.setFont(h_font_name, h_font_size)
        h_text_y = content_top - 8 * mm
        h_drawn_lines = 0
        max_h_drawn = 10

        for h_line in h_lines:
            if h_drawn_lines >= max_h_drawn:
                break
            wrapped = wrap_text(h_line, h_font_name, h_font_size, left_col_width)
            for wl in wrapped:
                if h_drawn_lines >= max_h_drawn:
                    break
                c.drawString(
                    left_margin, h_text_y - (h_drawn_lines * h_line_height), wl
                )
                h_drawn_lines += 1

        # --- P Statements (CONSEJOS DE PRUDENCIA) ---
        p_font_name = "Helvetica"
        p_font_size = 5
        p_line_height = 2.8 * mm
        p_header_font_size = 7

        h_section_end = h_text_y - (h_drawn_lines * h_line_height) - 2.5 * mm

        c.setFont("Helvetica-Bold", p_header_font_size)
        c.drawString(left_margin, h_section_end, "CONSEJOS DE PRUDENCIA:")

        p_codes = product.get("p_codes", [])
        p_statements = product.get("p_statements", [])

        p_lines = []
        for i, code in enumerate(p_codes):
            if i < len(p_statements) and p_statements[i]:
                p_lines.append(f"{code} - {p_statements[i]}")
            else:
                p_lines.append(code)
        # Fallback when no P-statements exist
        if not p_lines:
            p_lines = ["Consultar Hoja de Seguridad (HDS) para mayor información."]

        c.setFont(p_font_name, p_font_size)
        p_text_y = h_section_end - 3.5 * mm
        available_p_lines = int((p_text_y - content_bottom) / p_line_height)

        p_drawn_lines = 0
        for p_line in p_lines:
            if p_drawn_lines >= available_p_lines:
                break
            wrapped = wrap_text(p_line, p_font_name, p_font_size, left_col_width)
            for wl in wrapped:
                if p_drawn_lines >= available_p_lines:
                    break
                c.drawString(
                    left_margin, p_text_y - (p_drawn_lines * p_line_height), wl
                )
                p_drawn_lines += 1

        # ═══ SECTION 3: BOTTOM (Y=0mm to Y=24mm) ═══
        # Left side (X=3→105mm): Dates, LOTE, batch & variant barcodes
        # Right side (X=105→147mm): Weight labels, values, net weight barcode
        #
        # BOTTOM SECTION LAYOUT MAP:
        # ┌─────────────────────────────────────┬──────────────────────┐ Y=24mm (top border)
        # │ F.ELAB: dd/mm/yyyy  F.REINSP: date  │ PESO BRUTO: ##.## KG│ Y=21.5mm
        # │ LOTE:                                │ PESO TARA:  ##.## KG│ Y=18mm
        # │ ACP55241025                         │                      │ Y=14.5mm
        # │                                     │ PESO NETO:           │ Y=9.5mm
        # │ [batch barcode @X=30] [var BC @X=~80]│ [net wt barcode]    │ Y=5-10mm
        # │                       VAR-QB00005   │    ## KG             │ Y=4.5mm
        # └─────────────────────────────────────┴──────────────────────┘ Y=3mm
        # X=3   X=5   X=30     X=55    X=~80   X=105  X=107  X=121 X=147

        # --- Top Border Line of bottom section ---
        c.setLineWidth(1)  # 1pt thick border line
        c.line(3 * mm, 24 * mm, w - 3 * mm, 24 * mm)  # Horizontal line at Y=24mm

        # --- Vertical Divider (separates dates/barcodes from weights) ---
        # Position: X = w - 45mm = 105mm from left
        # Vertical line X=105mm, from Y=24 down to Y=3
        c.line(w - 45 * mm, 24 * mm, w - 45 * mm, 3 * mm)

        # ── Date Parsing (auto-formats batch_date) ──
        today_str = product.get(
            "batch_date", datetime.date.today().strftime("%d/%m/%Y")
        )
        reinsp_override = product.get("reinspection_date", "")

        # Helper: resolve reinsp_override into a display string
        def _resolve_reinsp(reinsp_val):
            if not reinsp_val or reinsp_val == "00":
                return ""
            try:
                # Handle "00/" sentinel in reinspection date (day-less)
                _rv = str(reinsp_val)
                _rv_parse = _rv
                _rv_had_00 = False
                if _rv.startswith("00/"):
                    _rv_parse = "01/" + _rv[3:]
                    _rv_had_00 = True
                if "-" in _rv_parse:
                    rd = datetime.datetime.strptime(_rv_parse, "%Y-%m-%d")
                else:
                    rd = datetime.datetime.strptime(_rv_parse, "%d/%m/%Y")
                if _rv_had_00:
                    return rd.strftime("00/%m/%Y")
                return rd.strftime("%d/%m/%Y")
            except Exception:
                return str(reinsp_val)

        try:
            dt = None
            # Handle "00/" sentinel in batch_date (day-less date)
            parse_str = str(today_str)
            had_00_day = False
            if parse_str.startswith("00/"):
                parse_str = "01/" + parse_str[3:]
                had_00_day = True

            if "-" in parse_str:
                # ISO format: YYYY-MM-DD
                dt = datetime.datetime.strptime(parse_str, "%Y-%m-%d")
            elif "/" in parse_str:
                # Try different date formats
                parts = parse_str.split("/")
                if len(parts) == 3:
                    # Check if it's M/D/YYYY (US format) or D/M/YYYY
                    if len(parts[2]) == 4:  # Year is last
                        month_or_day = int(parts[0])
                        day_or_month = int(parts[1])
                        year = int(parts[2])
                        if month_or_day > 12:
                            dt = datetime.datetime(year, day_or_month, month_or_day)
                        elif day_or_month > 12:
                            dt = datetime.datetime(year, month_or_day, day_or_month)
                        else:
                            dt = datetime.datetime(year, month_or_day, day_or_month)

            if dt:
                if had_00_day:
                    elab_date = dt.strftime("00/%m/%Y")
                else:
                    elab_date = dt.strftime("%d/%m/%Y")
                # Use explicit reinspection_date if provided, otherwise auto-calc +1 year
                if reinsp_override:
                    insp_date = _resolve_reinsp(reinsp_override)
                else:
                    try:
                        insp_dt = dt.replace(
                            year=dt.year + 1
                        )  # Reinspection = elaboration + 1 year
                    except ValueError:
                        insp_dt = dt.replace(year=dt.year + 1, day=28)
                    if had_00_day:
                        insp_date = insp_dt.strftime("00/%m/%Y")
                    else:
                        insp_date = insp_dt.strftime("%d/%m/%Y")
            else:
                elab_date = today_str
                # Still try to use reinsp_override even if batch date parsing failed
                if reinsp_override:
                    insp_date = _resolve_reinsp(reinsp_override)
                else:
                    insp_date = "N/A"
        except Exception:
            elab_date = (
                today_str if today_str else datetime.date.today().strftime("%d/%m/%Y")
            )
            # Still try to use reinsp_override even if batch date parsing failed
            if reinsp_override:
                insp_date = _resolve_reinsp(reinsp_override)
            else:
                insp_date = "N/A"

        # Handle "00" sentinel: user wants this date field blank on the label
        if today_str == "00":
            elab_date = ""
            insp_date = "" if (not reinsp_override or reinsp_override == "00") else _resolve_reinsp(reinsp_override)
        elif reinsp_override == "00":
            insp_date = ""

        # ── ROW 1: DATES (label above, value below for each date) ──
        date_label_size = 7
        date_value_size = 11

        # Elaboration — label on top line, value on line below
        c.setFont("Helvetica-Bold", date_label_size)
        c.drawString(1 * mm, 21 * mm, "F.ELABORACION:")  # Label at Y=21mm
        c.setFont("Helvetica-Bold", date_value_size)
        c.drawString(1 * mm, 17.5 * mm, elab_date)  # Value at Y=17.5mm

        # Reinspection — label on top line, value on line below
        c.setFont("Helvetica-Bold", date_label_size)
        c.drawString(1 * mm, 13 * mm, "F. REINSPECCION:")  # Label at Y=13mm
        c.setFont("Helvetica-Bold", date_value_size)
        c.drawString(1 * mm, 9.5 * mm, insp_date)  # Value at Y=9.5mm

        # ── ROW 2: LOTE LABEL ──
        batch_num = product.get("batch_number", "000000")
        c.setFont("Helvetica-Bold", 10)  # Font: 10pt bold  ← adjust size here
        # X=5mm,  Y=18mm   ← "LOTE:" text position
        c.drawString(77 * mm, 18 * mm, "LOTE:")

        # ── ROW 3: BATCH NUMBER (below LOTE) ──
        # Font: 12pt bold  ← adjust for bigger/smaller
        c.setFont("Helvetica-Bold", 15)
        # X=5mm,  Y=14.5mm ← batch number position
        c.drawString(70 * mm, 10 * mm, batch_num)

        # ── BATCH BARCODE (bottom area, center-ish) ──
        # barHeight=4mm ← taller/shorter, barWidth=1.25 ← wider/thinner bars
        bc_batch = code128.Code128(batch_num, barHeight=4 * mm, barWidth=1.25)
        # X=30mm, Y=5mm  ← move barcode left/right with X, up/down with Y
        bc_batch.drawOn(c, 40 * mm, 3 * mm)

        # ── VARIANT BARCODE (right-aligned to weight divider) ──
        # var_code = product.get('variant_code', internal_code)
        # left_section_right = w - 45*mm                                      # X=105mm = position of weight divider line
        # bc_var = code128.Code128(var_code, barHeight=4.5*mm, barWidth=1)       # barHeight=5mm ← taller/shorter
        # bc_var_width = bc_var.width                                          # Auto-calculated from code length
        # bc_var_x = left_section_right - bc_var_width - 1*mm                 # Right-aligned to divider, 1mm gap  ← adjust gap
        # bc_var.drawOn(c, bc_var_x, 10*mm)                                   # Y=10mm  ← move barcode up/down

        # ── VARIANT CODE TEXT (centered under variant barcode) ──
        # c.setFont("Helvetica-Bold", 6)                                      # Font: 6pt bold
        # c.drawCentredString(bc_var_x + bc_var_width/2, 7.5*mm, var_code[:15] if
        # len(var_code) > 15 else var_code)  # Y=8mm

        # ── WEIGHT LABELS (right side of divider) ──
        weight_x = w - 43 * mm  # X=107mm ← left edge of weight labels
        c.setFont("Helvetica-Bold", 7)  # Font: 9pt bold
        c.drawString(weight_x, 19 * mm, "PESO BRUTO:")  # Y=21.5mm ← top row label
        c.drawString(weight_x, 13 * mm, "PESO TARA:")  # Y=18mm   ← second row label
        c.drawString(weight_x, 8.5 * mm, "PESO NETO:")  # Y=9.5mm  ← lower row label

        # ── WEIGHT VALUES (right-aligned) ──
        import decimal

        try:
            p_n = str(product.get("quantity", "0"))
            if not p_n.strip():
                p_n = "0"
            peso_neto = decimal.Decimal(p_n)
        except Exception:
            peso_neto = decimal.Decimal("0")

        try:
            p_t = str(product.get("peso_tara", "0.0"))
            if not p_t.strip():
                p_t = "0.0"
            peso_tara = decimal.Decimal(p_t)
        except Exception:
            peso_tara = decimal.Decimal("0.0")

        peso_bruto = peso_neto + peso_tara

        # New Rule: Liquids where gross weight is strictly 25kg or net 25 with tara 1.3
        p_type = product.get("product_type", "").lower()
        if "liquido" in p_type or "líquido" in p_type:
            if peso_neto == decimal.Decimal("25") and peso_tara == decimal.Decimal(
                "1.3"
            ):
                peso_neto = decimal.Decimal("23.7")
                peso_bruto = decimal.Decimal("25.0")
            elif peso_bruto == decimal.Decimal("25"):
                peso_tara = decimal.Decimal("1.3")
                peso_neto = decimal.Decimal("23.7")  # Bruto = Neto + Tara

        # Helper string format to strictly truncate to 3 decimals without rounding
        def format_w(w):
            s = str(w)
            if "e" in s.lower():
                s = f"{w:.10f}"
            parts = s.split(".")
            if len(parts) == 1:
                return f"{parts[0]}.00"
            return f"{parts[0]}.{(parts[1] + '00')[:2]}"

        peso_bruto_str = format_w(peso_bruto)
        peso_tara_str = format_w(peso_tara)
        format_w(peso_neto)

        c.setFont("Helvetica-Bold", 14)  # Font: 8pt bold
        c.drawRightString(
            w - 4 * mm, 19 * mm, f"{peso_bruto_str} KG"
        )  # Right-aligned X=146mm, Y=21.5mm
        c.drawRightString(
            w - 4 * mm, 13 * mm, f"{peso_tara_str} KG"
        )  # Right-aligned X=146mm, Y=18mm

        # ── NET WEIGHT BARCODE (right side, below PESO NETO label) ──
        # Keep payload compact for scanner reliability in the limited width area.
        try:
            peso_neto_bc = format_w(peso_neto)
        except Exception:
            peso_neto_bc = "0"

        bc_net = code128.Code128(peso_neto_bc, barHeight=6.5 * mm, barWidth=0.7)
        bc_net_x = w - 35.5 * mm  # ~114.5mm from left, leaves right quiet zone
        net_slot_right = w - 3 * mm
        net_available_w = max(1, net_slot_right - bc_net_x)

        if bc_net.width > net_available_w and bc_net.width > 0:
            net_scale = net_available_w / bc_net.width
            c.saveState()
            c.translate(bc_net_x, 8 * mm)
            c.scale(net_scale, 1)
            bc_net.drawOn(c, 0, 0)
            c.restoreState()
            bc_net_draw_w = net_available_w
        else:
            bc_net.drawOn(c, bc_net_x, 8 * mm)
            bc_net_draw_w = bc_net.width

        c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(
            bc_net_x + bc_net_draw_w / 2, 4.5 * mm, f"{peso_neto_bc} KG"
        )

        # ═══ SECTION 4: FOOTER (Y=0 to Y=3mm) ═══
        c.setFont("Helvetica", 7)  # Font: 4.5pt (very small)
        address = "QUIMICA BOSS San Agustin 759 Col. El Briseño, Zapopan, Jalisco, México. CP 45236 Tel: 36 84 05 05"
        c.drawCentredString(
            w / 2, 0.5 * mm, address
        )  # Centered X=75mm, Y=0.5mm (very bottom)

        # ── Version Watermark (tiny text, bottom-right) ──
        c.setFont("Helvetica", 7)  # Font: 4pt
        c.setFillColor(colors.gray)
        c.drawRightString(w - 1 * mm, 0.5 * mm, SGA_VERSION)
        c.setFillColor(colors.black)

        c.save()
        print(f"GHS Label generated: {output_filename}")


if __name__ == "__main__":
    base_dir = "/home/quimicab/Base_datos/original_data"
    generator = GHSLabelGenerator(base_dir)

    # Custom Supplier Info
    my_supplier = {
        "name": "QUIMICAB S.A. DE C.V.",
        "address": "Av. Industrial 123, Parque Industrial, Guadalajara, Jal. CP. 44000",
        "phone": "EMERGENCIAS 24/7: 01 800 002 1400",  # Using the one from DB as key
    }

    generator.generate_label(
        "IFF-QB00122",
        "/home/quimicab/Base_datos/sticker_preview_NOM018.pdf",
        supplier_info=my_supplier,
    )
