#!/usr/bin/env python3
"""
GHS Data Lookup from PubChem + Legacy Data Parser
==================================================
Fills missing H/P codes, pictograms, and signal words for products in the SGA database.

Sources:
  1. PubChem REST API (free, no auth) - lookup by CAS number
  2. Legacy CSV text parsing - extract H/P codes from free-text descriptions

Usage:
  python ghs_pubchem_lookup.py                    # Full run: lookup + populate
  python ghs_pubchem_lookup.py --dry-run          # Preview without writing
  python ghs_pubchem_lookup.py --cas 56-81-5      # Test single CAS lookup
  python ghs_pubchem_lookup.py --report           # Show current missing data report
"""

import json
import csv
import re
import time
import logging
import argparse
from pathlib import Path
from datetime import datetime

# Optional: requests for PubChem API
try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    print("⚠️  'requests' module not installed. Install with: pip install requests")
    print("    PubChem lookups will be disabled, only legacy parsing will work.")

# Optional: pandas for CSV manipulation
try:
    import pandas as pd

    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================
UNIFIED_DB = Path(__file__).parent / "unified_db"
MISSING_FILE = Path(__file__).parent / "missing_HS.json"
RESULTS_FILE = Path(__file__).parent / "ghs_lookup_results.json"

PUBCHEM_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
PUBCHEM_VIEW = "https://pubchem.ncbi.nlm.nih.gov/rest/pug_view"
RATE_LIMIT_DELAY = 0.25  # seconds between API calls (PubChem allows 5/sec)

# GHS Pictogram code mapping (PubChem returns URLs, we need GHS codes)
PICTOGRAM_MAP = {
    "GHS01": ["Exploding Bomb", "bomba", "explosivo"],
    "GHS02": ["Flame", "llama", "inflamable", "flame"],
    "GHS03": ["Flame Over Circle", "oxidizer", "comburente", "llama sobre"],
    "GHS04": ["Gas Cylinder", "cilindro", "gas a presión", "compressed"],
    "GHS05": ["Corrosion", "corrosión", "corrosivo", "corrosive"],
    "GHS06": ["Skull and Crossbones", "calavera", "tóxico agudo", "skull"],
    "GHS07": ["Exclamation Mark", "exclamación", "irritante", "exclamation"],
    "GHS08": [
        "Health Hazard",
        "peligro para la salud",
        "health hazard",
        "mutagénico",
        "carcinógeno",
    ],
    "GHS09": ["Environment", "ambiente", "medio ambiente", "aquatic", "environment"],
}

# H-code to pictogram mapping (standard GHS classification)
H_TO_PICTOGRAM = {
    # GHS01 - Explosives
    "H200": "GHS01",
    "H201": "GHS01",
    "H202": "GHS01",
    "H203": "GHS01",
    "H204": "GHS01",
    "H205": "GHS01",
    "H240": "GHS01",
    "H241": "GHS01",
    # GHS02 - Flammables
    "H220": "GHS02",
    "H221": "GHS02",
    "H222": "GHS02",
    "H223": "GHS02",
    "H224": "GHS02",
    "H225": "GHS02",
    "H226": "GHS02",
    "H227": "GHS02",
    "H228": "GHS02",
    # "H241": "GHS02",  # duplicate removed
    "H242": "GHS02",
    "H250": "GHS02",
    "H251": "GHS02",
    "H252": "GHS02",
    "H260": "GHS02",
    "H261": "GHS02",
    # GHS03 - Oxidizers
    "H270": "GHS03",
    "H271": "GHS03",
    "H272": "GHS03",
    # GHS04 - Compressed gases
    "H280": "GHS04",
    "H281": "GHS04",
    "H282": "GHS04",
    "H283": "GHS04",
    "H284": "GHS04",
    # GHS05 - Corrosives
    "H290": "GHS05",
    "H314": "GHS05",
    "H318": "GHS05",
    # GHS06 - Acute toxicity (severe)
    "H300": "GHS06",
    "H301": "GHS06",
    "H310": "GHS06",
    "H311": "GHS06",
    "H330": "GHS06",
    "H331": "GHS06",
    # GHS07 - Irritant / Harmful
    "H302": "GHS07",
    "H312": "GHS07",
    "H315": "GHS07",
    "H317": "GHS07",
    "H319": "GHS07",
    "H332": "GHS07",
    "H335": "GHS07",
    "H336": "GHS07",
    "H320": "GHS07",
    # GHS08 - Health hazard (chronic)
    "H304": "GHS08",
    "H334": "GHS08",
    "H340": "GHS08",
    "H341": "GHS08",
    "H350": "GHS08",
    "H351": "GHS08",
    "H360": "GHS08",
    "H361": "GHS08",
    "H362": "GHS08",
    "H370": "GHS08",
    "H371": "GHS08",
    "H372": "GHS08",
    "H373": "GHS08",
    # GHS09 - Environmental
    "H400": "GHS09",
    "H401": "GHS09",
    "H402": "GHS09",
    "H410": "GHS09",
    "H411": "GHS09",
    "H412": "GHS09",
    "H413": "GHS09",
    "H420": "GHS09",
}

# Signal word determination from H codes
DANGER_H_CODES = {
    "H200",
    "H201",
    "H202",
    "H203",
    "H204",
    "H205",
    "H220",
    "H224",
    "H225",
    "H240",
    "H241",
    "H250",
    "H260",
    "H270",
    "H271",
    "H280",
    "H281",
    "H300",
    "H301",
    "H310",
    "H311",
    "H314",
    "H318",
    "H330",
    "H331",
    "H334",
    "H340",
    "H341",
    "H350",
    "H351",
    "H360",
    "H361",
    "H370",
    "H372",
    "H304",
}

# Spanish signal word mapping
SIGNAL_WORD_MAP = {
    "Danger": "PELIGRO",
    "Warning": "ATENCION",
    "danger": "PELIGRO",
    "warning": "ATENCION",
    "DANGER": "PELIGRO",
    "WARNING": "ATENCION",
}


# ============================================================================
# PUBCHEM API FUNCTIONS
# ============================================================================
class PubChemLookup:
    """Query PubChem for GHS classification data by CAS number."""

    def __init__(self):
        self.session = requests.Session() if REQUESTS_AVAILABLE else None
        self.cache = {}
        self._load_cache()

    def _load_cache(self):
        """Load previously fetched results from cache file."""
        cache_file = Path(__file__).parent / ".pubchem_cache.json"
        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    self.cache = json.load(f)
                logger.info(f"📦 Loaded {len(self.cache)} cached PubChem results")
            except Exception:
                self.cache = {}

    def _save_cache(self):
        """Save fetched results to cache file."""
        cache_file = Path(__file__).parent / ".pubchem_cache.json"
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Could not save cache: {e}")

    def _clean_cas(self, cas_str):
        """Clean CAS number string for API lookup."""
        if not cas_str:
            return None
        # Remove spaces around hyphens
        cas = re.sub(r"\s*-\s*", "-", cas_str.strip())
        # If multiple CAS numbers (comma or slash separated), take the first
        if "," in cas:
            cas = cas.split(",")[0].strip()
        if "/" in cas:
            cas = cas.split("/")[0].strip()
        # Validate CAS format: digits-digits-digit
        if re.match(r"^\d{2,7}-\d{2}-\d$", cas):
            return cas
        return None

    def get_cid_by_cas(self, cas_number):
        """Get PubChem CID from CAS number."""
        if not REQUESTS_AVAILABLE:
            return None

        url = f"{PUBCHEM_BASE}/compound/name/{cas_number}/cids/JSON"
        try:
            resp = self.session.get(url, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                cids = data.get("IdentifierList", {}).get("CID", [])
                if cids:
                    return cids[0]
            elif resp.status_code == 404:
                logger.debug(f"  CAS {cas_number}: Not found in PubChem")
            return None
        except Exception as e:
            logger.warning(f"  CAS {cas_number}: API error - {e}")
            return None

    def get_ghs_data(self, cid):
        """Get GHS classification from PubChem compound page."""
        if not REQUESTS_AVAILABLE:
            return None

        url = f"{PUBCHEM_VIEW}/data/compound/{cid}/JSON"
        params = {"heading": "GHS Classification"}
        try:
            resp = self.session.get(url, params=params, timeout=20)
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception as e:
            logger.warning(f"  CID {cid}: Could not fetch GHS data - {e}")
            return None

    def parse_ghs_response(self, ghs_json):
        """Parse PubChem GHS JSON into structured H/P/pictogram/signal word data.

        PubChem structure:
          Record > Section[Safety and Hazards] > Section[Hazards Identification]
            > Section[GHS Classification] > Information[] > Value > StringWithMarkup[]

        All GHS data (pictograms, signal word, H codes, P codes) is in a flat
        list of StringWithMarkup entries under a single GHS Classification section.
        The FIRST set of entries is the "harmonized" classification.
        """
        result = {
            "h_codes": [],
            "p_codes": [],
            "pictograms": [],
            "signal_word": None,
            "source": "PubChem",
        }

        if not ghs_json:
            return result

        try:
            # Recursively find the GHS Classification section
            ghs_section = self._find_section(
                ghs_json.get("Record", {}), "GHS Classification"
            )
            if not ghs_section:
                return result

            # Process all Information entries (flat structure)
            first_block_done = False
            for info in ghs_section.get("Information", []):
                value = info.get("Value", {})

                for sv in value.get("StringWithMarkup", []):
                    text = sv.get("String", "").strip()
                    markups = sv.get("Markup", [])

                    # Check for pictogram images (SVG URLs)
                    for markup in markups:
                        url = markup.get("URL", "")
                        extra = markup.get("Extra", "")
                        if "ghs/GHS" in url or ".svg" in url:
                            pic_code = self._extract_pictogram_code(url, extra)
                            if pic_code and pic_code not in result["pictograms"]:
                                result["pictograms"].append(pic_code)

                    # Signal word detection
                    if text in ("Danger", "Warning"):
                        if not result["signal_word"]:
                            result["signal_word"] = SIGNAL_WORD_MAP.get(text, text)

                    # H code extraction (e.g., "H225: Highly Flammable..." or "H225 (>99%):...")
                    h_match = re.match(
                        r"^(H\d{3})\s*(?:\*+\s*)?(?:\([^)]*\)\s*)?:", text
                    )
                    if h_match:
                        h_code = h_match.group(1)
                        if h_code not in result["h_codes"]:
                            result["h_codes"].append(h_code)
                    else:
                        # Also try to find H codes anywhere in text
                        h_codes_in_text = re.findall(r"\bH(\d{3})\b", text)
                        for h_num in h_codes_in_text:
                            h_code = f"H{h_num}"
                            if h_code not in result["h_codes"]:
                                result["h_codes"].append(h_code)

                    # P code extraction (comma-separated list like "P210, P233, P240...")
                    p_codes_in_text = re.findall(r"P\d{3}(?:\s*\+\s*P\d{3})*", text)
                    for p_code in p_codes_in_text:
                        clean = re.sub(r"\s+", "", p_code)
                        if clean not in result["p_codes"]:
                            result["p_codes"].append(clean)

                    # Stop after "This chemical does not meet GHS hazard criteria"
                    # (marks the boundary before the aggregated/secondary data)
                    if "does not meet GHS hazard criteria" in text:
                        first_block_done = True
                        break

                if first_block_done:
                    break

        except Exception as e:
            logger.warning(f"  Error parsing GHS response: {e}")

        return result

    def _find_section(self, obj, heading):
        """Recursively find a section by TOCHeading."""
        if isinstance(obj, dict):
            if obj.get("TOCHeading") == heading:
                return obj
            for section in obj.get("Section", []):
                result = self._find_section(section, heading)
                if result:
                    return result
        return None

    def _extract_pictogram_code(self, url, extra):
        """Extract GHS pictogram code from PubChem URL or description."""
        # PubChem URLs look like: .../GHS01.svg or contain pictogram name
        for code, keywords in PICTOGRAM_MAP.items():
            code_num = code.replace("GHS", "")
            if f"GHS{code_num}" in url or f"GHS0{code_num}" in url:
                return code
            for kw in keywords:
                if kw.lower() in url.lower() or kw.lower() in extra.lower():
                    return code
        # Try to extract directly from URL
        match = re.search(r"GHS0?(\d)", url)
        if match:
            return f"GHS0{match.group(1)}"
        return None

    def lookup_cas(self, cas_number, chemical_name=""):
        """Full lookup: CAS → CID → GHS data. Returns parsed result dict."""
        clean_cas = self._clean_cas(cas_number)
        if not clean_cas:
            return None

        # Check cache first
        if clean_cas in self.cache:
            logger.info(f"  📦 Cache hit for CAS {clean_cas}")
            return self.cache[clean_cas]

        logger.info(f"  🔍 Looking up CAS {clean_cas} ({chemical_name})...")

        # Step 1: Get CID
        cid = self.get_cid_by_cas(clean_cas)
        if not cid:
            logger.info(f"  ❌ CAS {clean_cas} not found in PubChem")
            self.cache[clean_cas] = None
            return None

        time.sleep(RATE_LIMIT_DELAY)

        # Step 2: Get GHS data
        ghs_json = self.get_ghs_data(cid)

        time.sleep(RATE_LIMIT_DELAY)

        # Step 3: Parse
        result = self.parse_ghs_response(ghs_json)
        result["cid"] = cid
        result["cas"] = clean_cas
        result["chemical_name"] = chemical_name

        # If we got H codes but no pictograms, infer from H codes
        if result["h_codes"] and not result["pictograms"]:
            result["pictograms"] = self._infer_pictograms(result["h_codes"])

        # If we got H codes but no signal word, infer from H codes
        if result["h_codes"] and not result["signal_word"]:
            result["signal_word"] = self._infer_signal_word(result["h_codes"])

        # Cache the result
        self.cache[clean_cas] = result
        self._save_cache()

        return result

    def _infer_pictograms(self, h_codes):
        """Infer pictogram codes from H codes."""
        pics = set()
        for h in h_codes:
            # Handle combined codes like H300+H310
            for sub_h in h.split("+"):
                sub_h = sub_h.strip()
                if sub_h in H_TO_PICTOGRAM:
                    pics.add(H_TO_PICTOGRAM[sub_h])
        return sorted(list(pics))

    def _infer_signal_word(self, h_codes):
        """Infer signal word from H codes."""
        for h in h_codes:
            for sub_h in h.split("+"):
                if sub_h.strip() in DANGER_H_CODES:
                    return "PELIGRO"
        return "ATENCION"


# ============================================================================
# LEGACY TEXT PARSER
# ============================================================================
class LegacyDataParser:
    """Parse H/P codes from free-text legacy data in missing_HS.json."""

    # Map Spanish descriptions to H codes
    H_TEXT_MAP = {
        "irritación cutánea": "H315",
        "irritación ocular grave": "H319",
        "irritación ocular": "H320",
        "lesiones oculares graves": "H318",
        "nocivo en caso de ingestión": "H302",
        "tóxico en caso de ingestión": "H301",
        "mortal en caso de ingestión": "H300",
        "nocivo en contacto con la piel": "H312",
        "tóxico en contacto con la piel": "H311",
        "mortal en contacto con la piel": "H310",
        "nocivo en caso de inhalación": "H332",
        "tóxico en caso de inhalación": "H331",
        "mortal en caso de inhalación": "H330",
        "quemaduras graves en la piel y lesiones oculares graves": "H314",
        "quemaduras graves en la piel": "H314",
        "reacción alérgica en la piel": "H317",
        "líquido y vapores extremadamente inflamables": "H224",
        "líquido y vapores muy inflamables": "H225",
        "líquidos y vapores inflamables": "H226",
        "líquido combustible": "H227",
        "muy tóxico para los organismos acuáticos": "H400",
        "muy tóxico para los organismos acuáticos, con efectos nocivos duraderos": "H410",
        "tóxico para los organismos acuáticos, con efectos nocivos duraderos": "H411",
        "tóxico para los organismos acuáticos": "H401",
        "nocivo para los organismos acuáticos, con efectos nocivos duraderos": "H412",
        "nocivo para los organismos acuáticos": "H402",
        "nocivo para la vida acuática": "H402",
        "puede provocar cáncer": "H350",
        "se sospecha que provoca cáncer": "H351",
        "puede provocar defectos genéticos": "H340",
        "se sospecha que provoca defectos genéticos": "H341",
        "puede perjudicar la fertilidad o dañar al feto": "H360",
        "se sospecha que puede perjudicar la fertilidad": "H361",
        "provoca daños en los órganos": "H370",
        "puede provocar daños en los órganos": "H371",
        "provoca daños en los órganos tras exposiciones prolongadas o repetidas": "H372",
        "puede provocar daños en los órganos tras exposiciones prolongadas": "H373",
        "puede ser mortal en caso de ingestión y penetración en las vías respiratorias": "H304",
        "puede provocar síntomas de alergia o asma": "H334",
        "puede irritar las vías respiratorias": "H335",
        "puede provocar somnolencia o vértigo": "H336",
        "gas extremadamente inflamable": "H220",
        "gas inflamable": "H221",
        "aerosol extremadamente inflamable": "H222",
        "aerosol inflamable": "H223",
        "sólido inflamable": "H228",
        "explosivo inestable": "H200",
        "polvo combustible": "H232",  # dust explosion hazard (not standard H, but common)
        "polvo explosivas en el aire": "H232",
        "concentraciones de polvo combustible": "H232",
        "toxicidad aguda por inhalacion": "H332",
        "causa seria irritación ocular": "H319",
        "causa irritación en piel": "H315",
        "causes serious eye irritation": "H319",
        "causes skin irritation": "H315",
    }

    # P code patterns from Spanish text
    P_TEXT_MAP = {
        "mantener fuera del alcance de los niños": "P102",
        "leer la etiqueta antes del uso": "P103",
        "solicitar instrucciones especiales": "P201",
        "mantener alejado de fuentes de calor": "P210",
        "mantener alejado del calor": "P210",
        "no respirar el polvo": "P260",
        "no respirar los vapores": "P261",
        "lavarse la piel cuidadosamente": "P264",
        "lavarse las manos concienzudamente": "P264",
        "lavarse concienzudamente": "P264",
        "lavarse bien después de manipularlo": "P264",
        "no comer, beber ni fumar": "P270",
        "no comer": "P270",
        "utilizar equipo de protección": "P280",
        "llevar guantes de protección": "P280",
        "llevar gafas o máscara": "P280",
        "llevar prendas de protección": "P280",
        "usar equipo de protección": "P280",
        "equipo de protección personal": "P280",
        "en caso de ingestión": "P301",
        "en caso de contacto con la piel": "P302",
        "en caso de inhalación": "P304",
        "en caso de contacto con los ojos": "P305",
        "enjuagar con agua cuidadosamente": "P351",
        "aclarar cuidadosamente con agua": "P351",
        "quitar las lentes de contacto": "P338",
        "consultar a un médico": "P313",
        "llamar inmediatamente a un centro de información toxicológica": "P310",
        "llamar a un centro de información toxicológica": "P312",
        "transportar a la persona al aire libre": "P340",
        "transportar a la víctima al exterior": "P340",
        "aclararse la piel con agua": "P352",
        "lavar con abundante agua": "P352",
        "quitar inmediatamente todas las prendas contaminadas": "P361",
        "quitarse las prendas contaminadas": "P362",
        "lavar las prendas contaminadas": "P363",
        "enjuagarse la boca": "P330",
        "no provocar el vómito": "P331",
        "guardar cerrado": "P403",
        "mantener el recipiente herméticamente cerrado": "P233",
        "almacenar en un lugar bien ventilado": "P403",
        "mantener en lugar fresco": "P235",
        "eliminar el contenido y el recipiente": "P501",
        "evitar su liberación al medio ambiente": "P273",
        "recoger el vertido": "P391",
    }

    def extract_h_codes(self, h_texts):
        """Extract H codes from legacy text descriptions."""
        h_codes = set()

        if not h_texts:
            return []

        for text in h_texts:
            if not text or text in ("No Aplicable", "No aplicable", "-", ""):
                continue

            # Direct H code references (e.g., "H302", "H319")
            direct = re.findall(r"H\d{3}", text)
            for code in direct:
                h_codes.add(code)

            # Text-based matching
            text_lower = text.lower().replace("\r\n", " ").replace("\n", " ")
            for desc, code in self.H_TEXT_MAP.items():
                if desc.lower() in text_lower:
                    h_codes.add(code)

        return sorted(list(h_codes))

    def extract_p_codes(self, p_texts):
        """Extract P codes from legacy text descriptions."""
        p_codes = set()

        if not p_texts:
            return []

        for text in p_texts:
            if not text or text in ("No Aplicable", "No aplicable", "-", ""):
                continue

            # Direct P code references (e.g., "P264", "P305+P351+P338")
            direct = re.findall(r"P\d{3}(?:\s*\+\s*P\d{3})*", text)
            for code in direct:
                clean = re.sub(r"\s+", "", code)
                p_codes.add(clean)

            # Text-based matching
            text_lower = text.lower().replace("\r\n", " ").replace("\n", " ")
            for desc, code in self.P_TEXT_MAP.items():
                if desc.lower() in text_lower:
                    p_codes.add(code)

        return sorted(list(p_codes))

    def parse_legacy_product(self, product):
        """Parse a single product's legacy data into structured H/P/pictogram data."""
        legacy = product.get("legacy_data", {})
        if not legacy:
            return None

        h_codes = self.extract_h_codes(legacy.get("h_codes", []))
        p_codes = self.extract_p_codes(legacy.get("p_codes", []))
        pictograms = legacy.get("pictograms", [])
        signal_word = legacy.get("signal_word", "")

        # Clean signal word
        if signal_word in ("No Aplicable", "No aplicable", "-", ""):
            signal_word = None

        # If we have H codes but no pictograms, infer them
        if h_codes and not pictograms:
            pics = set()
            for h in h_codes:
                for sub_h in h.split("+"):
                    sub_h = sub_h.strip()
                    if sub_h in H_TO_PICTOGRAM:
                        pics.add(H_TO_PICTOGRAM[sub_h])
            pictograms = sorted(list(pics))

        # If we have H codes but no signal word, infer it
        if h_codes and not signal_word:
            for h in h_codes:
                for sub_h in h.split("+"):
                    if sub_h.strip() in DANGER_H_CODES:
                        signal_word = "PELIGRO"
                        break
                if signal_word:
                    break
            if not signal_word:
                signal_word = "ATENCION"

        if not h_codes and not p_codes and not pictograms:
            return None

        return {
            "product_id": product["product_id"],
            "chemical_name": product["chemical_name"],
            "cas_number": product.get("cas_number", ""),
            "h_codes": h_codes,
            "p_codes": p_codes,
            "pictograms": pictograms,
            "signal_word": signal_word,
            "source": "legacy_parse",
        }


# ============================================================================
# DATABASE POPULATOR
# ============================================================================
class DatabasePopulator:
    """Write resolved GHS data into the unified_db CSV files."""

    def __init__(self, db_path=UNIFIED_DB, dry_run=False):
        self.db_path = Path(db_path)
        self.dry_run = dry_run
        self.stats = {
            "products_updated": 0,
            "h_entries_added": 0,
            "p_entries_added": 0,
            "pic_entries_added": 0,
            "signal_words_updated": 0,
        }

    def _read_csv(self, filename):
        """Read a CSV file and return rows as list of dicts."""
        filepath = self.db_path / filename
        if not filepath.exists():
            return []
        with open(filepath, "r", encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    def _write_csv(self, filename, rows, fieldnames):
        """Write rows to a CSV file."""
        filepath = self.db_path / filename
        with open(filepath, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def populate(self, results):
        """
        Populate the database with resolved GHS data.

        Args:
            results: list of dicts with keys: product_id, h_codes, p_codes, pictograms, signal_word
        """
        if not results:
            logger.info("No results to populate.")
            return self.stats

        # Load current data
        products_master = self._read_csv("products_master.csv")
        product_hazards = self._read_csv("product_hazards.csv")
        product_precautions = self._read_csv("product_precautions.csv")
        product_pictograms = self._read_csv("product_pictograms.csv")
        h_statements = self._read_csv("h_statements.csv")
        p_statements = self._read_csv("p_statements.csv")

        # Build lookup sets for existing data
        existing_h = {(r["product_id"], r["h_code"]) for r in product_hazards}
        existing_p = {(r["product_id"], r["p_code"]) for r in product_precautions}
        existing_pic = {
            (r["product_id"], r["pictogram_id"]) for r in product_pictograms
        }
        known_h_codes = {r["h_code"] for r in h_statements}
        known_p_codes = {r["p_code"] for r in p_statements}
        products_by_id = {r["product_id"]: r for r in products_master}

        new_h_entries = []
        new_p_entries = []
        new_pic_entries = []

        for result in results:
            pid = result["product_id"]
            logger.info(f"  📝 Populating {pid}: {result.get('chemical_name', '')}")

            # Add H codes
            for h_code in result.get("h_codes", []):
                # Handle combined codes like H300+H310
                for sub_h in h_code.split("+"):
                    sub_h = sub_h.strip()
                    if (pid, sub_h) not in existing_h:
                        new_h_entries.append({"product_id": pid, "h_code": sub_h})
                        existing_h.add((pid, sub_h))
                        self.stats["h_entries_added"] += 1

                        # Check if H code exists in h_statements reference
                        if sub_h not in known_h_codes:
                            logger.warning(
                                f"    ⚠️ H code {sub_h} not in h_statements.csv (add description manually)"
                            )

            # Add P codes
            for p_code in result.get("p_codes", []):
                if (pid, p_code) not in existing_p:
                    new_p_entries.append({"product_id": pid, "p_code": p_code})
                    existing_p.add((pid, p_code))
                    self.stats["p_entries_added"] += 1

                    if p_code not in known_p_codes:
                        logger.warning(
                            f"    ⚠️ P code {p_code} not in p_statements.csv (add description manually)"
                        )

            # Add pictograms
            for pic in result.get("pictograms", []):
                if (pid, pic) not in existing_pic:
                    new_pic_entries.append({"product_id": pid, "pictogram_id": pic})
                    existing_pic.add((pid, pic))
                    self.stats["pic_entries_added"] += 1

            # Update signal word in products_master
            sw = result.get("signal_word")
            if sw and pid in products_by_id:
                current_sw = products_by_id[pid].get("signal_word", "")
                if current_sw in ("No Aplicable", "No aplicable", "-", ""):
                    products_by_id[pid]["signal_word"] = sw
                    self.stats["signal_words_updated"] += 1

            self.stats["products_updated"] += 1

        # Write back
        if not self.dry_run:
            logger.info("💾 Writing updated database files...")

            # Append new entries
            all_hazards = product_hazards + new_h_entries
            all_precautions = product_precautions + new_p_entries
            all_pictograms = product_pictograms + new_pic_entries

            self._write_csv(
                "product_hazards.csv", all_hazards, ["product_id", "h_code"]
            )
            self._write_csv(
                "product_precautions.csv", all_precautions, ["product_id", "p_code"]
            )
            self._write_csv(
                "product_pictograms.csv", all_pictograms, ["product_id", "pictogram_id"]
            )

            # Update products_master
            master_fields = list(products_master[0].keys()) if products_master else []
            self._write_csv(
                "products_master.csv", list(products_by_id.values()), master_fields
            )

            logger.info("✅ Database updated successfully!")
        else:
            logger.info("🏃 DRY RUN - no files were modified")

        return self.stats


# ============================================================================
# MAIN ORCHESTRATOR
# ============================================================================
def load_missing_products():
    """Load the missing products from missing_HS.json."""
    with open(MISSING_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("products", [])


def run_report():
    """Print current status report of missing GHS data."""
    products = load_missing_products()

    skip_cas = {
        "Mezcla",
        "No aplicable",
        "No Aplicable",
        "",
        "Mixture",
        "-",
        None,
        "Sustancia",
    }
    has_cas = [p for p in products if p.get("cas_number") not in skip_cas]
    no_cas = [p for p in products if p.get("cas_number") in skip_cas]

    # Count those with legacy text that could be parsed
    parser = LegacyDataParser()
    parseable = 0
    for p in products:
        result = parser.parse_legacy_product(p)
        if result and (result["h_codes"] or result["p_codes"]):
            parseable += 1

    print("=" * 70)
    print("  GHS Missing Data Report")
    print("=" * 70)
    print(f"  Total products with missing data:  {len(products)}")
    print(f"  Products with CAS (PubChem lookup): {len(has_cas)}")
    print(f"  Products without CAS (Mezcla/etc):  {len(no_cas)}")
    print(f"  Products with parseable legacy text: {parseable}")
    print(
        f"  Genuinely non-hazardous (approx):    {len(products) - len(has_cas) - parseable}"
    )
    print("=" * 70)
    print()
    print("  Strategy:")
    print("    1. PubChem API lookup for 78 products with CAS numbers")
    print("    2. Parse legacy text for products with H/P descriptions")
    print("    3. Infer pictograms and signal words from H codes")
    print("    4. Mark genuinely non-hazardous products as confirmed")
    print()


def run_single_cas_test(cas_number):
    """Test lookup for a single CAS number."""
    if not REQUESTS_AVAILABLE:
        print("❌ 'requests' module required. Install: pip install requests")
        return

    lookup = PubChemLookup()
    result = lookup.lookup_cas(cas_number, "Test Compound")

    if result:
        print(f"\n✅ PubChem result for CAS {cas_number}:")
        print(f"  CID:         {result.get('cid')}")
        print(f"  Signal Word: {result.get('signal_word')}")
        print(f"  H Codes:     {result.get('h_codes')}")
        print(f"  P Codes:     {result.get('p_codes')}")
        print(f"  Pictograms:  {result.get('pictograms')}")
    else:
        print(f"\n❌ No GHS data found for CAS {cas_number}")
        print("   This may mean: compound not in PubChem, or not GHS-classified")


def run_full_lookup(dry_run=False):
    """Run the full lookup: PubChem + legacy parsing → database population."""
    products = load_missing_products()
    results = []

    # Phase 1: Parse legacy data (no network needed)
    print("\n" + "=" * 70)
    print("  PHASE 1: Parsing legacy text data")
    print("=" * 70)

    parser = LegacyDataParser()
    legacy_count = 0

    for p in products:
        result = parser.parse_legacy_product(p)
        if result and (result["h_codes"] or result["p_codes"] or result["pictograms"]):
            results.append(result)
            legacy_count += 1
            logger.info(
                f"  ✅ {result['product_id']}: {len(result['h_codes'])} H, "
                f"{len(result['p_codes'])} P, {len(result['pictograms'])} pics"
            )

    print(f"\n  📊 Legacy parsing: {legacy_count} products recovered\n")

    # Phase 2: PubChem lookup for products with CAS numbers
    if REQUESTS_AVAILABLE:
        print("=" * 70)
        print("  PHASE 2: PubChem API lookup (by CAS number)")
        print("=" * 70)

        skip_cas = {
            "Mezcla",
            "No aplicable",
            "No Aplicable",
            "",
            "Mixture",
            "-",
            None,
            "Sustancia",
        }
        already_resolved = {r["product_id"] for r in results}

        lookup = PubChemLookup()
        pubchem_count = 0
        pubchem_enriched = 0

        for p in products:
            pid = p["product_id"]
            cas = p.get("cas_number", "")

            if cas in skip_cas:
                continue

            # Try PubChem lookup
            pc_result = lookup.lookup_cas(cas, p.get("chemical_name", ""))

            if pc_result and (pc_result.get("h_codes") or pc_result.get("pictograms")):
                pubchem_count += 1

                if pid in already_resolved:
                    # Merge with legacy data - PubChem data supplements legacy
                    for existing in results:
                        if existing["product_id"] == pid:
                            # Add any new H codes from PubChem
                            for h in pc_result["h_codes"]:
                                if h not in existing["h_codes"]:
                                    existing["h_codes"].append(h)
                            for p_code in pc_result["p_codes"]:
                                if p_code not in existing["p_codes"]:
                                    existing["p_codes"].append(p_code)
                            for pic in pc_result["pictograms"]:
                                if pic not in existing["pictograms"]:
                                    existing["pictograms"].append(pic)
                            if not existing["signal_word"] and pc_result.get(
                                "signal_word"
                            ):
                                existing["signal_word"] = pc_result["signal_word"]
                            existing["source"] = "legacy+pubchem"
                            pubchem_enriched += 1
                            break
                else:
                    # New result from PubChem
                    results.append(
                        {
                            "product_id": pid,
                            "chemical_name": p.get("chemical_name", ""),
                            "cas_number": cas,
                            "h_codes": pc_result["h_codes"],
                            "p_codes": pc_result["p_codes"],
                            "pictograms": pc_result["pictograms"],
                            "signal_word": pc_result.get("signal_word"),
                            "source": "pubchem",
                        }
                    )

                logger.info(
                    f"  ✅ {pid}: {len(pc_result['h_codes'])} H, "
                    f"{len(pc_result['p_codes'])} P, {len(pc_result['pictograms'])} pics"
                )
            else:
                logger.info(
                    f"  ⚪ {pid}: No GHS classification in PubChem (may be non-hazardous)"
                )

            time.sleep(RATE_LIMIT_DELAY)

        print(
            f"\n  📊 PubChem: {pubchem_count} new lookups, {pubchem_enriched} enriched\n"
        )
    else:
        print("\n⚠️  Skipping PubChem lookup (install 'requests' module)")

    # Phase 3: Populate database
    print("=" * 70)
    print(f"  PHASE 3: {'DRY RUN - ' if dry_run else ''}Populating database")
    print("=" * 70)

    populator = DatabasePopulator(dry_run=dry_run)
    stats = populator.populate(results)

    print("\n  📊 Population results:")
    print(f"     Products updated:    {stats['products_updated']}")
    print(f"     H entries added:     {stats['h_entries_added']}")
    print(f"     P entries added:     {stats['p_entries_added']}")
    print(f"     Pictogram entries:   {stats['pic_entries_added']}")
    print(f"     Signal words set:    {stats['signal_words_updated']}")

    # Save detailed results
    save_results = []
    for r in results:
        save_results.append(
            {
                "product_id": r["product_id"],
                "chemical_name": r.get("chemical_name", ""),
                "cas_number": r.get("cas_number", ""),
                "h_codes": r.get("h_codes", []),
                "p_codes": r.get("p_codes", []),
                "pictograms": r.get("pictograms", []),
                "signal_word": r.get("signal_word", ""),
                "source": r.get("source", ""),
            }
        )

    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {
                "metadata": {
                    "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "total_results": len(save_results),
                    "stats": stats,
                    "dry_run": dry_run,
                },
                "results": save_results,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(f"\n  💾 Detailed results saved to: {RESULTS_FILE}")

    return results


# ============================================================================
# CLI
# ============================================================================
def main():
    parser = argparse.ArgumentParser(
        description="GHS Data Lookup from PubChem + Legacy Data Parser",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python ghs_pubchem_lookup.py --report         # See what's missing
  python ghs_pubchem_lookup.py --cas 56-81-5    # Test single CAS lookup
  python ghs_pubchem_lookup.py --dry-run        # Preview all changes
  python ghs_pubchem_lookup.py                  # Run full lookup & populate DB
        """,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without modifying database files",
    )
    parser.add_argument("--cas", type=str, help="Test lookup for a single CAS number")
    parser.add_argument(
        "--report", action="store_true", help="Show current missing data report"
    )
    parser.add_argument(
        "--legacy-only",
        action="store_true",
        help="Only parse legacy text data (no PubChem API)",
    )

    args = parser.parse_args()

    if args.report:
        run_report()
    elif args.cas:
        run_single_cas_test(args.cas)
    elif args.legacy_only:
        # Temporarily disable requests
        global REQUESTS_AVAILABLE
        REQUESTS_AVAILABLE = False
        run_full_lookup(dry_run=args.dry_run)
    else:
        run_full_lookup(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
