"""

Tara Weight Manager - Standardized container/tare weight system for GHS labels.

Provides a 3-level selector:  Product Type -> Container Type -> Tara Weight

Built from statistical analysis of 2600+ historical records.

Container types are inferred from tara weight clusters observed in the data:

  - Very low tara (0.015-0.035 kg) → Bags (bolsas) → Powder/Solid products

  - Low tara (0.09 kg) → Small bottles/jars (frascos) → Liquids ≤1 kg

  - Medium tara (0.24-0.29 kg) → Plastic pails/jugs (garrafas) → Liquids 1.5-4 kg

  - Medium-high (0.28-0.60 kg) → Pails (cubetas) → Liquids 5-10 kg

  - High tara (0.48-0.90 kg) → Plastic drums (tambos) → Liquids 9-20 kg

  - Very high (1.2-2.2 kg) → Metal drums/barrels → Liquids 15-50 kg

"""

import os

import json

import logging

import re

import pandas as pd

from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

CONTROL_INTERNO_EXCLUDED_CODE_RE = re.compile(r"^(?:AF\d+|SE\d+)", re.IGNORECASE)

CONTROL_INTERNO_EXCLUDED_CODES = {"ANTICIPO", "NC DESCUENTOS"}


def should_exclude_from_control_interno(product_id: str) -> bool:
    """Return True when a product should be hidden from the Control Interno panel."""

    code = str(product_id or "").strip().upper()

    if not code:

        return False

    return code in CONTROL_INTERNO_EXCLUDED_CODES or bool(
        CONTROL_INTERNO_EXCLUDED_CODE_RE.match(code)
    )


# ─── Container Definitions ──────────────────────────────────────────────────

# Each container has: id, name (Spanish), tara_kg, material, typical use

CONTAINER_CATALOG = [
    {
        "id": "bolsa_peq",
        "name": "Bolsa pequeña",
        "name_en": "Small bag",
        "tara_kg": 0.015,
        "material": "plastic",
        "product_types": ["polvo", "solido", "ligero"],
        "icon": "bag-small",
    },
    {
        "id": "bolsa",
        "name": "Bolsa",
        "name_en": "Bag",
        "tara_kg": 0.035,
        "material": "plastic",
        "product_types": ["polvo", "solido", "ligero"],
        "icon": "bag",
    },
    {
        "id": "frasco",
        "name": "Frasco / Botella",
        "name_en": "Bottle / Jar",
        "tara_kg": 0.09,
        "material": "plastic",
        "product_types": ["liquido", "ligero"],
        "icon": "bottle",
    },
    {
        "id": "garrafa",
        "name": "Garrafa plástica",
        "name_en": "Plastic jug",
        "tara_kg": 0.24,
        "material": "plastic",
        "product_types": ["liquido", "ligero"],
        "icon": "jug",
    },
    {
        "id": "cubeta_plastica",
        "name": "Cubeta plástica",
        "name_en": "Plastic pail",
        "tara_kg": 0.28,
        "material": "plastic",
        "product_types": ["liquido", "ligero"],
        "icon": "pail",
    },
    {
        "id": "cubeta_pesada",
        "name": "Cubeta plástica reforzada",
        "name_en": "Heavy plastic pail",
        "tara_kg": 0.29,
        "material": "plastic",
        "product_types": ["liquido", "viscoso", "solido"],
        "icon": "pail-heavy",
    },
    {
        "id": "cubeta_metalica",  # ID se mantiene por compatibilidad hacia atrás
        "name": "Cubeta plástica",
        "name_en": "Plastic pail",
        "tara_kg": 0.48,
        "material": "plastic",
        "product_types": ["liquido", "ligero"],
        "icon": "bucket",
    },
    {
        "id": "balde_metalico",
        "name": "Balde plástico",
        "name_en": "Plastic bucket",
        "tara_kg": 0.60,
        "material": "plastic",
        "product_types": ["liquido", "viscoso"],
        "icon": "bucket",
    },
    {
        "id": "tambo_plastico",
        "name": "Tambor plástico",
        "name_en": "Plastic drum",
        "tara_kg": 0.90,
        "material": "plastic",
        "product_types": ["liquido", "ligero"],
        "icon": "drum-plastic",
    },
    {
        "id": "tambo_metalico",
        "name": "Tambor metálico",
        "name_en": "Metal drum",
        "tara_kg": 1.20,
        "material": "metal",
        "product_types": ["liquido", "viscoso"],
        "icon": "drum-metal",
    },
    {
        "id": "barril",
        "name": "Barril",
        "name_en": "Barrel",
        "tara_kg": 2.20,
        "material": "metal",
        "product_types": ["liquido", "ligero"],
        "icon": "barrel",
    },
    {
        "id": "frasco_color",
        "name": "Frasco de color",
        "name_en": "Dye jar",
        "tara_kg": 0.075,
        "material": "plastic",
        "product_types": ["color"],
        "icon": "jar-color",
    },
    {
        "id": "bote_color",
        "name": "Bote de color",
        "name_en": "Dye container",
        "tara_kg": 0.35,
        "material": "plastic",
        "product_types": ["color", "polvo"],
        "icon": "container-color",
    },
]

# Product types with display info

PRODUCT_TYPES = [
    {"id": "liquido", "name": "Líquido", "name_en": "Liquid", "icon": "💧"},
    {"id": "viscoso", "name": "Viscoso", "name_en": "Viscous", "icon": "🫧"},
    {"id": "polvo", "name": "Polvo", "name_en": "Powder", "icon": "🧂"},
    {"id": "color", "name": "Color / Tinte", "name_en": "Dye / Color", "icon": "🎨"},
    {"id": "ligero", "name": "Ligero", "name_en": "Light liquid", "icon": "🌿"},
    {"id": "solido", "name": "Sólido", "name_en": "Solid", "icon": "🧊"},
]

# ─── Empirical mapping: which containers are typically used for each net weight range ──

# Built from analysis of 2600+ records. Key = (peso_neto, tara_kg) -> usage percentage

# This is the "smart suggestion" engine

WEIGHT_CONTAINER_MAP = {
    # peso_neto: [(container_id, tara_kg, usage_pct, is_default), ...]
    0.5: [
        ("frasco", 0.09, 86.4, True),
        ("bolsa_peq", 0.015, 11.8, False),
        ("cubeta_pesada", 0.29, 1.8, False),
    ],
    1.0: [
        ("frasco", 0.09, 81.1, True),
        ("bolsa_peq", 0.015, 10.8, False),
        ("cubeta_pesada", 0.29, 4.4, False),
        ("garrafa", 0.24, 3.6, False),
    ],
    1.5: [("garrafa", 0.24, 100.0, True)],
    2.0: [
        ("garrafa", 0.24, 80.3, True),
        ("bolsa_peq", 0.015, 9.2, False),
        ("cubeta_pesada", 0.29, 8.8, False),
        ("bolsa", 0.035, 1.6, False),
    ],
    3.0: [
        ("garrafa", 0.24, 80.6, True),
        ("bolsa", 0.035, 10.7, False),
        ("cubeta_pesada", 0.29, 8.7, False),
    ],
    4.0: [
        ("garrafa", 0.24, 74.8, True),
        ("bolsa", 0.035, 10.8, False),
        ("cubeta_pesada", 0.29, 8.4, False),
        ("cubeta_plastica", 0.28, 5.6, False),
        ("balde_metalico", 0.60, 0.4, False),
    ],
    5.0: [
        ("cubeta_plastica", 0.28, 74.1, True),
        ("balde_metalico", 0.60, 10.0, False),
        ("bolsa", 0.035, 9.3, False),
        ("cubeta_metalica", 0.48, 6.6, False),
    ],
    7.0: [
        ("cubeta_metalica", 0.48, 60.0, True),
        ("balde_metalico", 0.60, 40.0, False),
    ],  # CLASIFICACION.xlsx: liquidos/ligeros → 0.48; viscosos → 0.60
    8.0: [
        ("cubeta_metalica", 0.48, 60.0, True),
        ("balde_metalico", 0.60, 40.0, False),
    ],  # CLASIFICACION.xlsx: liquidos/ligeros → 0.48; viscosos → 0.60
    9.0: [("cubeta_metalica", 0.48, 100.0, True)],
    10.0: [
        ("cubeta_metalica", 0.48, 75.0, True),
        ("balde_metalico", 0.60, 9.5, False),
        ("bolsa", 0.035, 8.1, False),
        ("tambo_plastico", 0.90, 6.7, False),
        ("tambo_metalico", 1.20, 0.7, False),
    ],
    15.0: [("tambo_plastico", 0.90, 89.2, True), ("tambo_metalico", 1.20, 10.8, False)],
    16.0: [
        ("tambo_metalico", 1.20, 50.0, False),
        ("tambo_plastico", 0.90, 50.0, False),
    ],
    17.0: [("tambo_metalico", 1.20, 100.0, True)],
    18.0: [("tambo_plastico", 0.90, 94.1, True), ("tambo_metalico", 1.20, 5.9, False)],
    20.0: [("tambo_plastico", 0.90, 90.5, True), ("tambo_metalico", 1.20, 9.5, False)],
    23.7: [("tambo_plastico", 1.30, 100.0, True)],
    25.0: [("tambo_plastico", 1.30, 100.0, True)],
    40.0: [("barril", 2.20, 100.0, True)],
    45.0: [("barril", 2.20, 100.0, True)],
    47.0: [("barril", 2.20, 100.0, True)],
    50.0: [("barril", 2.20, 100.0, True)],
    200.0: [("tambo_plastico", 0.90, 100.0, True)],  # IBC / special containers
}

# ─── Per-Type Tara Tables (from CLASIFICACION.xlsx) ─────────────────────────

# Maps: product_type -> {peso_neto_kg: tara_kg}

# These take priority over WEIGHT_CONTAINER_MAP when the product type is known.

TARA_BY_TYPE = {
    "liquido": {
        0.5: 0.09,
        1: 0.09,
        2: 0.24,
        3: 0.24,
        4: 0.24,
        5: 0.28,
        6: 0.48,
        7: 0.48,
        8: 0.48,
        9: 0.48,
        10: 0.48,
        11: 0.9,
        12: 0.9,
        13: 0.9,
        14: 0.9,
        15: 0.9,
        16: 0.9,
        17: 0.9,
        18: 0.9,
        19: 0.9,
        20: 0.9,
        23.7: 1.3,
        25: 1.3,
        50: 2.2,
    },
    "viscoso": {
        1: 0.29,
        2: 0.29,
        3: 0.29,
        4: 0.29,
        5: 0.6,
        6: 0.6,
        7: 0.6,
        8: 0.6,
        9: 0.6,
        10: 0.6,
        11: 1.2,
        12: 1.2,
        13: 1.2,
        14: 1.2,
        15: 1.2,
        16: 1.2,
        17: 1.2,
        18: 1.2,
        19: 1.2,
        20: 1.2,
    },
    "polvo": {
        0.5: 0.015,
        1: 0.015,
        2: 0.015,
        3: 0.035,
        4: 0.035,
        5: 0.035,
        6: 0.035,
        7: 0.035,
        8: 0.035,
        9: 0.035,
        10: 0.035,
    },
    "color": {
        0.5: 0.075,
        1: 0.35,
    },
    "ligero": {
        0.5: 0.09,
        1: 0.09,
        2: 0.24,
        3: 0.24,
        4: 0.24,
        5: 0.28,
        6: 0.48,
        7: 0.48,
        8: 0.48,
        9: 0.48,
        10: 0.48,
        11: 0.9,
        12: 0.9,
        13: 0.9,
        14: 0.9,
        15: 0.9,
        16: 0.9,
        17: 0.9,
        18: 0.9,
        19: 0.9,
        20: 0.9,
        23.7: 1.3,
        25: 1.3,
        30: 2.2,
        45: 2.2,
        50: 2.2,
    },
}

# ─── Product-to-Type Mapping (from CLASIFICACION.xlsx) ──────────────────────

# Explicit mapping of product IDs to their classification.

# Built from the sheet-based classification in the Excel file.

# This is loaded dynamically by load_clasificacion_excel() at runtime.

CLASIFICACION_EXCEL_PRODUCTS: Dict[str, str] = {}  # product_id -> product_type

# Notes from LIQUIDOS sheet (special packaging rules)

LIQUIDOS_PACKAGING_NOTES = {
    30: "30kg: 2 envases de 15kg",  # 2 containers of 15kg
    40: "40kg: 2 envases de 20kg",  # 2 containers of 20kg
    100: "100kg: 2 envases de 100kg",  # 2 containers of 100kg (likely 50kg each)
}


def load_clasificacion_excel(excel_path: Optional[str] = None) -> Dict[str, str]:
    """

    Load product-to-type mapping from CLASIFICACION.xlsx.

    Each sheet (LIQUIDOS, VISCOSOS, POLVOS, COLORES, LIGEROS) maps to a product type.

    Returns dict of {product_id: product_type} and updates the global mapping.

    """

    # global CLASIFICACION_EXCEL_PRODUCTS  # removed: never assigned in scope

    if excel_path is None:

        base = os.path.dirname(os.path.abspath(__file__))

        excel_path = os.path.join(base, "original_data", "CLASIFICACION.xlsx")

    if not os.path.exists(excel_path):

        logger.warning(f"⚠️ CLASIFICACION.xlsx not found at {excel_path}")

        return {}

    SHEET_TYPE_MAP = {
        "LIQUIDOS": "liquido",
        "VISCOSOS": "viscoso",
        "POLVOS": "polvo",
        "COLORES": "color",
        "LIGEROS": "ligero",
    }

    mapping = {}

    try:

        xls = pd.ExcelFile(excel_path)

        for sheet_name, product_type in SHEET_TYPE_MAP.items():

            if sheet_name not in xls.sheet_names:

                continue

            df = pd.read_excel(xls, sheet_name=sheet_name, dtype=str)

            col_name = [c for c in df.columns if "codigo" in c.lower().strip()]

            if not col_name:

                continue

            col = col_name[0]

            for _, row in df.iterrows():

                pid = str(row.get(col, "")).strip()

                if pid and pid != "nan" and not pid.startswith("Codigo"):

                    mapping[pid] = product_type

        CLASIFICACION_EXCEL_PRODUCTS.update(mapping)

        logger.info(
            f"✅ Loaded {len(mapping)} product classifications from CLASIFICACION.xlsx"
        )

    except Exception as e:

        logger.error(f"❌ Error loading CLASIFICACION.xlsx: {e}")

    return mapping


def resolve_tara_by_type(product_type: str, peso_neto: float) -> Optional[float]:
    """

    Resolve tara weight using the type-specific tara table.

    Returns None if the type or weight is not in the table (caller can fall back).

    For weights between known entries, uses the nearest lower entry.

    """

    if product_type not in TARA_BY_TYPE:

        return None

    type_table = TARA_BY_TYPE[product_type]

    # Exact match

    if peso_neto in type_table:

        return type_table[peso_neto]

    # Find nearest known weight (prefer lower to avoid overestimating container)

    known_weights = sorted(type_table.keys())

    if not known_weights:

        return None

    # Find closest weight

    closest = min(known_weights, key=lambda w: abs(w - peso_neto))

    # Only use if within reasonable proximity (50% range)

    if abs(closest - peso_neto) / max(peso_neto, 0.1) < 0.5:

        return type_table[closest]

    return None


class TaraWeightManager:
    """

    Manages tara (container) weight resolution with a 3-level selector:

    Product Type → Container → Tara Weight



    Also provides smart suggestions based on historical data patterns.

    """

    def __init__(self, csv_path: Optional[str] = None):

        self._product_tara_cache: Dict[str, Dict] = (
            {}
        )  # product_code -> {peso_neto -> tara}

        self._product_classifications: Dict[str, Dict] = (
            {}
        )  # product_code -> classification

        self._is_initialized = False

        self._csv_path = csv_path

        self.sql_engine = None

        try:

            from database_client import get_shared_client

            client = get_shared_client()

            if client.is_connected():

                self.sql_engine = client.get_sql_engine()

        except Exception as e:

            logger.warning(
                f"[WARN] Warning initializing DB in tara_weight_manager: {e}"
            )

        if csv_path and os.path.exists(csv_path) and not self.sql_engine:

            self._load_product_history(csv_path)

        self._load_classifications()

    def _load_product_history(self, csv_path: str):
        """Load historical tara data per product from the main CSV."""

        try:

            df = pd.read_csv(csv_path, dtype=str)

            df.columns = [c.strip() for c in df.columns]

            df = df.dropna(subset=["Codigo interno"])

            df["PESO TARA"] = pd.to_numeric(df["PESO TARA"], errors="coerce")

            df["PESO NETO"] = pd.to_numeric(df["PESO NETO"], errors="coerce")

            df = df.dropna(subset=["PESO TARA", "PESO NETO"])

            df = df[df["PESO TARA"] > 0]

            # Build per-product cache: product_code -> {peso_neto -> tara_kg}

            for _, row in df.iterrows():

                code = str(row["Codigo interno"]).strip()

                peso_neto = float(row["PESO NETO"])

                peso_tara = float(row["PESO TARA"])

                if code not in self._product_tara_cache:

                    self._product_tara_cache[code] = {}

                # Keep the most common tara for each peso_neto (last one wins from sorted data)

                self._product_tara_cache[code][peso_neto] = peso_tara

            logger.info(
                f"✅ TaraWeightManager loaded history for {len(self._product_tara_cache)} products"
            )

        except Exception as e:

            logger.error(f"❌ Error loading tara history: {e}")

    def get_product_types(self) -> List[Dict]:
        """Return all product types for the first selector level."""

        return PRODUCT_TYPES

    def get_containers_for_type(self, product_type: str) -> List[Dict]:
        """Return available containers filtered by product type."""

        return [c for c in CONTAINER_CATALOG if product_type in c["product_types"]]

    def get_all_containers(self) -> List[Dict]:
        """Return the full container catalog."""

        return CONTAINER_CATALOG

    def get_smart_suggestions(
        self, peso_neto: float, product_code: Optional[str] = None
    ) -> List[Dict]:
        """

        Get smart tara weight suggestions based on net weight and optionally product history.



        Returns a list of container options sorted by likelihood, each with:

        - container info (id, name, tara_kg, material)

        - is_default: whether this is the most common choice

        - usage_pct: historical usage percentage

        - source: 'classification' | 'tara_override' | 'type_table' | 'product_history' | 'statistical' | 'interpolated'



        Priority order:

        0. default_container set in Control Interno (highest)

        0b. tara_override for this specific peso_neto (from Control Interno or Excel import)

        1. Product-specific CSV history (exact peso_neto)

        2. Type-specific tara table (TARA_BY_TYPE by product classification)

        3. Statistical WEIGHT_CONTAINER_MAP

        4. Interpolated from nearest weight

        """

        suggestions = []

        # ── Priority 0: Control Interno saved classification ──────────────────

        if product_code and product_code in self._product_classifications:

            classification = self._product_classifications[product_code]

            # 0a. Explicit default_container set by the user in Control Interno

            default_container_id = classification.get("default_container", "")

            if default_container_id and default_container_id != "custom":

                container = self._get_container_by_id(default_container_id)

                if container:

                    suggestions.append(
                        {
                            **container,
                            "is_default": True,
                            "usage_pct": 100.0,
                            "source": "classification",
                            "label": f"✅ {container['name']} — {container['tara_kg']} kg (configurado)",
                        }
                    )

            # 0b. tara_override for this specific peso_neto

            if not suggestions:

                tara_overrides = classification.get("tara_overrides", {})

                # Try multiple key formats: "7", "7.0", "7.00" etc.

                override_tara = None

                for key in [
                    str(int(peso_neto)) if peso_neto == int(peso_neto) else None,
                    str(float(peso_neto)),
                    str(peso_neto),
                ]:

                    if key and key in tara_overrides:

                        override_tara = tara_overrides[key]

                        break

                if override_tara is not None:

                    container = self._find_container_by_tara(float(override_tara))

                    if container:

                        suggestions.append(
                            {
                                **container,
                                "tara_kg": float(override_tara),
                                "is_default": True,
                                "usage_pct": 100.0,
                                "source": "tara_override",
                                "label": f"✅ {container['name']} — {override_tara} kg (tabla producto)",
                            }
                        )

        # ── Priority 1: Product-specific CSV history / Overrides ──────────────────────────

        if product_code:

            known_taras = self.get_product_known_tara(product_code)

            if peso_neto in known_taras and known_taras[peso_neto] >= 0:

                tara_kg = known_taras[peso_neto]

                container = self._find_container_by_tara(tara_kg)

                if container and not any(
                    s["id"] == container["id"] for s in suggestions
                ):

                    suggestions.append(
                        {
                            **container,
                            "tara_kg": tara_kg,
                            "is_default": len(suggestions) == 0,
                            "usage_pct": 100.0,
                            "source": "product_history",
                            "label": f"⭐ {container['name']} — {tara_kg} kg (histórico del producto)",
                        }
                    )

        # ── Priority 2: Type-specific table (CLASIFICACION.xlsx rules) ────────

        if product_code:

            product_type = self._get_product_type(product_code)

            if product_type:

                type_tara = resolve_tara_by_type(product_type, peso_neto)

                if type_tara is not None:

                    container = self._find_container_by_tara(type_tara)

                    if container and not any(
                        s["id"] == container["id"] for s in suggestions
                    ):

                        suggestions.append(
                            {
                                **container,
                                "tara_kg": type_tara,
                                "is_default": len(suggestions) == 0,
                                "usage_pct": 90.0,
                                "source": "type_table",
                                "label": f"📋 {container['name']} — {type_tara} kg (tabla {product_type})",
                            }
                        )

        # ── Priority 3: Statistical WEIGHT_CONTAINER_MAP ──────────────────────

        if peso_neto in WEIGHT_CONTAINER_MAP:

            for container_id, tara_kg, usage_pct, is_default in WEIGHT_CONTAINER_MAP[
                peso_neto
            ]:

                if any(s["id"] == container_id for s in suggestions):

                    continue

                container = self._get_container_by_id(container_id)

                if container:

                    suggestions.append(
                        {
                            **container,
                            "tara_kg": tara_kg,
                            "is_default": is_default and len(suggestions) == 0,
                            "usage_pct": usage_pct,
                            "source": "statistical",
                            "label": f"{container['name']} — {tara_kg} kg ({usage_pct:.0f}%)",
                        }
                    )

        elif not suggestions:

            # ── Priority 4: Interpolate from nearest weight ─────────────

            suggestions = self._interpolate_suggestions(peso_neto)

        # Always add a "custom" option at the end

        suggestions.append(
            {
                "id": "custom",
                "name": "Personalizado",
                "name_en": "Custom",
                "tara_kg": 0,
                "material": "unknown",
                "product_types": [
                    "liquido",
                    "viscoso",
                    "polvo",
                    "color",
                    "ligero",
                    "solido",
                ],
                "icon": "edit",
                "is_default": len(suggestions) == 0,
                "usage_pct": 0,
                "source": "manual",
                "label": "✏️ Ingresar valor manualmente",
            }
        )

        return suggestions

    def resolve_best_tara(
        self, peso_neto: float, product_code: Optional[str] = None
    ) -> float:
        """

        Resolve the single best tara weight for a given net weight and product.

        Returns 0.0 if no suggestion found.



        Priority:

        1. Product-specific history (exact match)

        2. Product-specific history (nearest weight interpolation)

        3. Type-specific tara table (from CLASIFICACION.xlsx rules)

        4. Statistical WEIGHT_CONTAINER_MAP (exact)

        5. Statistical WEIGHT_CONTAINER_MAP (nearest interpolation)

        """

        if peso_neto <= 0:

            return 0.0

        # 1. Product-specific exact match

        if product_code:

            known_taras = self.get_product_known_tara(product_code)

            if peso_neto in known_taras and known_taras[peso_neto] >= 0:

                return known_taras[peso_neto]

            # 2. Product-specific nearest weight interpolation

            if known_taras:

                # filter out logical deletes (-1)

                valid_taras = {k: v for k, v in known_taras.items() if v >= 0}

                if valid_taras:

                    float_keys = [
                        k for k in valid_taras.keys() if isinstance(k, (int, float))
                    ]

                    if float_keys:

                        closest = min(float_keys, key=lambda w: abs(w - peso_neto))

                        # Only use if within 50% range

                        if abs(closest - peso_neto) / max(peso_neto, 0.1) < 0.5:

                            return valid_taras[closest]

        # 3. Type-specific tara table

        if product_code:

            product_type = self._get_product_type(product_code)

            if product_type:

                type_tara = resolve_tara_by_type(product_type, peso_neto)

                if type_tara is not None:

                    return type_tara

        # 4. Statistical exact match

        if peso_neto in WEIGHT_CONTAINER_MAP:

            entries = WEIGHT_CONTAINER_MAP[peso_neto]

            # Return the default entry's tara

            for container_id, tara_kg, usage_pct, is_default in entries:

                if is_default:

                    return tara_kg

            # If no default, return the highest usage

            return entries[0][1] if entries else 0.0

        # 4. Statistical nearest interpolation

        float_keys = [
            k for k in WEIGHT_CONTAINER_MAP.keys() if isinstance(k, (int, float))
        ]

        if float_keys:

            closest = min(float_keys, key=lambda w: abs(w - peso_neto))

            entries = WEIGHT_CONTAINER_MAP[closest]

            for container_id, tara_kg, usage_pct, is_default in entries:

                if is_default:

                    return tara_kg

            return entries[0][1] if entries else 0.0

        return 0.0

    def _interpolate_suggestions(self, peso_neto: float) -> List[Dict]:
        """For non-standard weights, find the nearest known weight containers."""

        known_weights = sorted(
            k for k in WEIGHT_CONTAINER_MAP.keys() if isinstance(k, (int, float))
        )

        # Find closest weight

        closest = min(known_weights, key=lambda w: abs(w - peso_neto))

        suggestions = []

        for container_id, tara_kg, usage_pct, is_default in WEIGHT_CONTAINER_MAP[
            closest
        ]:

            container = self._get_container_by_id(container_id)

            if container:

                suggestions.append(
                    {
                        **container,
                        "is_default": is_default,
                        "usage_pct": usage_pct,
                        "source": "interpolated",
                        "label": f"{container['name']} — {tara_kg} kg (≈{closest} kg ref)",
                    }
                )

        return suggestions

    def _find_container_by_tara(self, tara_kg: float) -> Optional[Dict]:
        """Find the container whose tara_kg is closest to the given value."""

        best = None

        best_diff = float("inf")

        for c in CONTAINER_CATALOG:

            diff = abs(c["tara_kg"] - tara_kg)

            if diff < best_diff:

                best_diff = diff

                best = c

        # Only match if within 10% or 0.05 kg tolerance

        if best and (best_diff <= 0.05 or best_diff / max(tara_kg, 0.001) <= 0.1):

            return dict(best)  # Return a copy

        return None

    def _get_container_by_id(self, container_id: str) -> Optional[Dict]:
        """Get container dict by ID."""

        for c in CONTAINER_CATALOG:

            if c["id"] == container_id:

                return dict(c)

        return None

    def get_product_known_tara(self, product_code: str) -> Dict[float, float]:
        """

        Return all known (peso_neto -> tara_kg) pairs for a specific product.

        Combines historical data from CSV with manual overrides from JSON.

        """

        # Start with historical cache

        base_tara = dict(self._product_tara_cache.get(product_code, {}))

        # Overlay with manual overrides from classifications

        classification = self.get_classification(product_code)

        if classification and "tara_overrides" in classification:

            for neto_str, tara_val in classification["tara_overrides"].items():

                try:

                    base_tara[float(neto_str)] = float(tara_val)

                except ValueError:

                    pass

        return base_tara

    def resolve_tara(
        self, product_code: str, peso_neto: float, container_id: Optional[str] = None
    ) -> float:
        """

        Resolve the tara weight with priority:

        1. Explicit container selection (if container_id provided)

        2. Product-specific history (exact peso_neto match)

        3. Type-specific tara table (from CLASIFICACION.xlsx rules)

        4. Statistical default for this peso_neto

        5. 0.0 (unknown)

        """

        # 1. Explicit container

        if container_id and container_id != "custom":

            container = self._get_container_by_id(container_id)

            if container:

                return container["tara_kg"]

        # 2. Product history

        known_taras = self.get_product_known_tara(product_code)

        if peso_neto in known_taras and known_taras[peso_neto] >= 0:

            return known_taras[peso_neto]

        # 3. Type-specific tara table

        product_type = self._get_product_type(product_code)

        if product_type:

            type_tara = resolve_tara_by_type(product_type, peso_neto)

            if type_tara is not None:

                return type_tara

        # 4. Statistical default

        if peso_neto in WEIGHT_CONTAINER_MAP:

            for _, tara_kg, _, is_default in WEIGHT_CONTAINER_MAP[peso_neto]:

                if is_default:

                    return tara_kg

        return 0.0

    def _get_product_type(self, product_code: str) -> Optional[str]:
        """Get the product type from classifications or Excel mapping."""

        # Check classifications first

        if product_code in self._product_classifications:

            pt = self._product_classifications[product_code].get("product_type", "")

            if pt:

                return pt

        # Fall back to Excel mapping

        return CLASIFICACION_EXCEL_PRODUCTS.get(product_code)

    def get_summary_stats(self) -> Dict:
        """Return summary statistics for the admin dashboard."""

        visible_items = [
            p
            for p in self._product_classifications.values()
            if not should_exclude_from_control_interno(p.get("product_id", ""))
        ]

        # Count classified products

        classified = sum(1 for p in visible_items if p.get("product_type"))

        unclassified = len(visible_items) - classified

        return {
            "total_products_with_history": sum(
                1
                for code, p in self._product_classifications.items()
                if not should_exclude_from_control_interno(code)
                and p.get("tara_overrides")
            ),
            "total_products_classified": classified,
            "total_products_unclassified": unclassified,
            "total_products": len(visible_items),
            "container_types": len(CONTAINER_CATALOG),
            "product_types": len(PRODUCT_TYPES),
            "known_weight_ranges": len(WEIGHT_CONTAINER_MAP),
            "weight_ranges": sorted(WEIGHT_CONTAINER_MAP.keys()),
        }

    # ─── Product Classification Persistence ──────────────────────────────────

    def _get_classifications_path(self) -> str:
        """Path to the JSON file that stores product classifications."""

        base = os.path.dirname(os.path.abspath(__file__))

        return os.path.join(base, "unified_db", "product_classifications.json")

    def _load_classifications(self, force=False):
        """Load product classifications from SQL or JSON file."""

        if getattr(self, "_product_classifications", None) and not force:

            return

        if self.sql_engine:

            try:

                df = pd.read_sql(
                    "SELECT * FROM product_classifications", con=self.sql_engine
                )

                # Convert back to dict of dicts

                classifications = {}

                for _, row in df.iterrows():

                    pid = str(row["product_id"])

                    props = row.dropna().to_dict()

                    # Do not delete product_id as it's needed by get_classifications

                    # Unpack json strings

                    def _sanitize_nans(obj):
                        import math

                        if isinstance(obj, float) and math.isnan(obj):
                            return ""
                        if isinstance(obj, dict):
                            return {k: _sanitize_nans(val) for k, val in obj.items()}
                        if isinstance(obj, list):
                            return [_sanitize_nans(val) for val in obj]
                        return obj

                    for k, v in props.items():

                        if isinstance(v, str) and (
                            v.startswith("{") or v.startswith("[")
                        ):

                            try:

                                props[k] = _sanitize_nans(json.loads(v))

                            except json.JSONDecodeError:

                                pass

                    classifications[pid] = props

                    # Commented out loading of tara_history column into _product_tara_cache
                    # to prevent dynamic type-specific weights from contaminating the historical cache.
                    pass

                self._product_classifications = classifications

                logger.info(
                    f"✅ Loaded {len(self._product_classifications)} product classifications from SQL"
                )

                # Also load batch data from product_batches table and merge into classifications
                try:
                    df_batches = pd.read_sql(
                        "SELECT * FROM product_batches", con=self.sql_engine
                    )

                    if not df_batches.empty:
                        merged_count = 0
                        for _, batch_row in df_batches.iterrows():
                            pid = str(batch_row["product_id"])
                            lote = str(batch_row["lote"])
                            fecha_elab = (
                                str(batch_row.get("fecha_elaboracion", ""))[:10]
                                if pd.notna(batch_row.get("fecha_elaboracion"))
                                else ""
                            )
                            fecha_insp = (
                                str(batch_row.get("fecha_reinspeccion", ""))[:10]
                                if pd.notna(batch_row.get("fecha_reinspeccion"))
                                else ""
                            )

                            if pid in classifications:
                                entry = classifications[pid]

                                # Only merge if product doesn't already have this lote
                                existing_lotes = entry.get("lotes_info", {})
                                if not isinstance(existing_lotes, dict):
                                    existing_lotes = {}

                                if lote not in existing_lotes:
                                    existing_lotes[lote] = {
                                        "fecha_elaboracion": fecha_elab,
                                        "fecha_inspeccion": fecha_insp,
                                    }
                                    entry["lotes_info"] = existing_lotes

                                    # If this is the only lote or no primary lote is set, make it primary
                                    if not entry.get("lote"):
                                        entry["lote"] = lote
                                        entry["lote_date"] = fecha_elab
                                        entry["lote_reinspection_date"] = fecha_insp

                                    merged_count += 1

                        if merged_count > 0:
                            logger.info(
                                f"✅ Merged {merged_count} batch records from product_batches table"
                            )
                except Exception as e:
                    logger.warning(f"⚠️ Could not load product_batches: {e}")

                # Also merge from product_lotes table (created by SQL migration)
                # This table has a different schema: fecha_inspeccion instead of fecha_reinspeccion
                try:
                    df_plotes = pd.read_sql(
                        "SELECT product_id, lote, fecha_elaboracion, fecha_inspeccion FROM product_lotes",
                        con=self.sql_engine,
                    )
                    if not df_plotes.empty:
                        plotes_count = 0
                        for _, row in df_plotes.iterrows():
                            pid = str(row["product_id"])
                            lote = str(row.get("lote", ""))
                            if not lote or lote.lower() in ("nan", "none"):
                                continue
                            fecha_elab = (
                                str(row.get("fecha_elaboracion", ""))[:10]
                                if pd.notna(row.get("fecha_elaboracion"))
                                else ""
                            )
                            fecha_insp = (
                                str(row.get("fecha_inspeccion", ""))[:10]
                                if pd.notna(row.get("fecha_inspeccion"))
                                else ""
                            )
                            if fecha_elab.lower() in ("nan", "none", "nat"):
                                fecha_elab = ""
                            if fecha_insp.lower() in ("nan", "none", "nat"):
                                fecha_insp = ""

                            if pid in classifications:
                                entry = classifications[pid]
                                existing_lotes = entry.get("lotes_info", {})
                                if not isinstance(existing_lotes, dict):
                                    existing_lotes = {}

                                if lote not in existing_lotes:
                                    existing_lotes[lote] = {
                                        "fecha_elaboracion": fecha_elab,
                                        "fecha_inspeccion": fecha_insp,
                                    }
                                    entry["lotes_info"] = existing_lotes

                                    if not entry.get("lote"):
                                        entry["lote"] = lote
                                        entry["lote_date"] = fecha_elab
                                        entry["lote_reinspection_date"] = fecha_insp

                                    plotes_count += 1

                        if plotes_count > 0:
                            logger.info(
                                f"✅ Merged {plotes_count} batch records from product_lotes table"
                            )
                except Exception as e:
                    logger.debug(f"product_lotes table not available (non-fatal): {e}")

                # OPTIMIZED: Use ROW_NUMBER() to only fetch the latest 20 entries per product
                # instead of loading all 224K+ rows. Uses groupby + set dedup instead of iterrows + O(n²) any().
                try:
                    df_history = pd.read_sql(
                        """
                        SELECT * FROM (
                            SELECT *, ROW_NUMBER() OVER (
                                PARTITION BY product_id ORDER BY event_date DESC
                            ) as rn
                            FROM product_lote_history
                        ) t WHERE rn <= 20
                        ORDER BY product_id, event_date DESC
                        """,
                        con=self.sql_engine,
                    )
                    if not df_history.empty:
                        hist_count = 0

                        def _safe_str(val):
                            if pd.isna(val):
                                return ""
                            s = str(val).strip()
                            if s.lower() in ("nan", "none", "nat", "<na>"):
                                return ""
                            return s

                        # Batch process by product_id using groupby instead of iterrows
                        for pid, group in df_history.groupby("product_id"):
                            pid = str(pid)
                            if pid not in self._product_classifications:
                                continue

                            entry = self._product_classifications[pid]
                            if "lote_history" not in entry or not isinstance(
                                entry["lote_history"], list
                            ):
                                entry["lote_history"] = []

                            # Build a set of existing timestamps for O(1) dedup
                            existing_ts = set()
                            for x in entry["lote_history"]:
                                ts_val = x.get("timestamp", "")
                                if ts_val:
                                    existing_ts.add(ts_val)
                                date_val = x.get("date", "")
                                if date_val:
                                    existing_ts.add(date_val)

                            for _, hist_row in group.iterrows():
                                h_entry = {
                                    "old_lote": _safe_str(hist_row.get("old_lote")),
                                    "new_lote": _safe_str(hist_row.get("new_lote")),
                                    "old_date": _safe_str(hist_row.get("old_date"))[
                                        :10
                                    ],
                                    "new_date": _safe_str(hist_row.get("new_date"))[
                                        :10
                                    ],
                                    "user": _safe_str(hist_row.get("user_name"))
                                    or "Sistema",
                                    "timestamp": _safe_str(hist_row.get("event_date"))[
                                        :19
                                    ],
                                    "source": "sql_recovery",
                                    "notes": _safe_str(hist_row.get("notes")),
                                }

                                ts = h_entry["timestamp"]
                                if ts not in existing_ts:
                                    entry["lote_history"].append(h_entry)
                                    existing_ts.add(ts)
                                    hist_count += 1

                        if hist_count > 0:
                            logger.info(
                                f"✅ Rebuilt {hist_count} history entries from product_lote_history SQL table"
                            )
                except Exception as e:
                    logger.warning(f"⚠️ Could not recover lote history from SQL: {e}")

                # Recover lote from lote_history (authoritative source of truth)
                self._recover_lotes_from_history()

                return

            except Exception as e:

                logger.warning(
                    f"⚠️ SQL load classifications failed, falling back to JSON: {e}"
                )

        path = self._get_classifications_path()

        if os.path.exists(path):

            try:

                with open(path, "r", encoding="utf-8") as f:

                    self._product_classifications = json.load(f)

                logger.info(
                    f"✅ Loaded {len(self._product_classifications)} product classifications"
                )

            except Exception as e:
                logger.error(f"❌ Error loading classifications: {e}")
                self._product_classifications = {}
        else:
            self._product_classifications = {}

        self._recover_lotes_from_history()

    def _recover_lotes_from_history(self):
        """
        Authoritative lote recovery: for each product, check its lote_history
        (sorted newest-first) and update the 'lote' field to match the newest
        entry's new_lote.  This corrects stale data from SQL/JSON on every load.
        Falls back to _sync_priority_lotes for products that have valid dates
        in lotes_info but no lote_history.
        """
        import datetime as dt

        recovered = 0
        for pid, class_data in self._product_classifications.items():
            if not isinstance(class_data, dict):
                continue

            history = class_data.get("lote_history", [])
            if not isinstance(history, list) or not history:
                continue

            # Find the newest entry by parsing date/timestamp
            best_entry = None
            best_ts = dt.datetime.min

            for entry in history:
                if not isinstance(entry, dict):
                    continue
                new_lote = str(entry.get("new_lote", "")).strip()
                if not new_lote:
                    continue

                # Parse timestamp from either 'date' or 'timestamp' field
                ts_raw = str(
                    entry.get("date", entry.get("timestamp", "")) or ""
                ).strip()
                ts = dt.datetime.min
                for fmt in (
                    "%Y-%m-%d %H:%M:%S",
                    "%Y-%m-%dT%H:%M:%S.%f",
                    "%Y-%m-%dT%H:%M:%S",
                    "%Y-%m-%d",
                ):
                    try:
                        ts = dt.datetime.strptime(ts_raw, fmt)
                        break
                    except ValueError:
                        pass

                if ts > best_ts:
                    best_ts = ts
                    best_entry = entry

            if best_entry and best_ts > dt.datetime.min:
                target_lote = str(best_entry.get("new_lote", "")).strip()
                current_lote = str(class_data.get("lote", "")).strip()

                if target_lote and target_lote != current_lote:
                    class_data["lote"] = target_lote
                    # Also update dates from the history entry
                    new_date = str(
                        best_entry.get("new_elab_date", best_entry.get("new_date", ""))
                        or ""
                    ).strip()
                    new_reinsp = str(
                        best_entry.get("new_reinsp_date", "") or ""
                    ).strip()
                    if new_date and new_date != "nan":
                        class_data["lote_date"] = new_date[:10]
                    if new_reinsp and new_reinsp != "nan":
                        class_data["lote_reinspection_date"] = new_reinsp[:10]
                    recovered += 1

        # Also run _sync_priority_lotes for products that have valid dated entries
        # in lotes_info but no lote_history
        self._sync_priority_lotes()

        if recovered > 0:
            logger.info(f"🔄 Recovered {recovered} stale lote values from lote_history")

    def _sync_priority_lotes(self):
        """
        Ensures the active 'lote', 'lote_date', and 'lote_reinspection_date'
        are synced to the manually added batch with the newest fecha_elaboracion.
        Only overrides the current lote if at least one entry has a valid date;
        otherwise the most recent user edit (already stored in 'lote') is preserved.
        """
        import datetime

        for pid, class_data in self._product_classifications.items():
            if not isinstance(class_data, dict):
                continue
            lotes_info = class_data.get("lotes_info", {})
            if not isinstance(lotes_info, dict) or not lotes_info:
                continue

            best_lote = None
            best_dt = None
            best_info = None
            has_valid_date = False

            for lote_id, info in lotes_info.items():
                if not isinstance(info, dict) or not str(lote_id).strip():
                    continue

                f_elab = str(info.get("fecha_elaboracion", "")).strip()[:10]
                try:
                    dt = datetime.datetime.strptime(f_elab, "%Y-%m-%d")
                    # Ignore future dates as they are likely typos (e.g., 2027 instead of 2025)
                    # We allow up to 2 days in the future to account for timezone differences
                    now_limit = datetime.datetime.now() + datetime.timedelta(days=2)
                    if dt > now_limit:
                        continue
                    has_valid_date = True
                except ValueError:
                    dt = datetime.datetime.min

                if best_dt is None or dt > best_dt:
                    best_dt = dt
                    best_lote = lote_id
                    best_info = info

            # Only override lote if we found at least one entry with a real date.
            # When all dates are invalid/empty, preserve the current lote value
            # (which was just set by the user's edit).
            if best_lote and best_info and has_valid_date:
                current_lote = str(class_data.get("lote", "")).strip()
                should_override = True

                # If the current lote is already in lotes_info and has the SAME date as best_dt,
                # preserve it! This prevents reverting user edits that changed the lote name but kept the same date.
                if current_lote in lotes_info:
                    c_elab = str(
                        lotes_info[current_lote].get("fecha_elaboracion", "")
                    ).strip()[:10]
                    try:
                        c_dt = datetime.datetime.strptime(c_elab, "%Y-%m-%d")
                        if c_dt >= best_dt:
                            should_override = False
                    except ValueError:
                        pass

                if should_override:
                    class_data["lote"] = str(best_lote)
                    class_data["lote_date"] = best_info.get(
                        "fecha_elaboracion", class_data.get("lote_date", "")
                    )
                    class_data["lote_reinspection_date"] = best_info.get(
                        "fecha_inspeccion", class_data.get("lote_reinspection_date", "")
                    )

    def _save_classifications(self):
        """Save product classifications to SQL and JSON file."""
        import re

        # Always save to JSON as fallback WITH ATOMIC WRITES AND RETENTION BACKUPS

        path = self._get_classifications_path()

        try:
            import shutil
            from datetime import datetime

            os.makedirs(os.path.dirname(path), exist_ok=True)

            # 1. Create a rolling backup before overwriting
            if os.path.exists(path):
                backup_dir = os.path.join(os.path.dirname(path), "backups")
                os.makedirs(backup_dir, exist_ok=True)
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = os.path.join(backup_dir, f"classifications_{ts}.json")

                try:
                    shutil.copy2(path, backup_path)
                    # Prune old backups (Keep last 30)
                    all_backups = sorted(
                        [
                            os.path.join(backup_dir, f)
                            for f in os.listdir(backup_dir)
                            if f.endswith(".json")
                        ]
                    )
                    for old_bkp in all_backups[:-30]:
                        os.remove(old_bkp)
                except Exception as bk_e:
                    logger.warning(f"⚠️ Rolling Backup Warning: {bk_e}")

            # 2. Atomic Write: Dump to Temp, Flush to Disk, Replace
            tmp_path = path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(
                    self._product_classifications, f, ensure_ascii=False, indent=2
                )
                f.flush()
                import platform

                if platform.system() == "Windows":
                    os.fsync(f.fileno())

            os.replace(tmp_path, path)

            logger.info(
                f"✅ Saved {len(self._product_classifications)} product classifications to JSON (Atomic Save)"
            )

        except Exception as e:

            logger.error(f"❌ Error saving classifications to JSON: {e}")

        # Save to SQL

        if self.sql_engine:

            try:
                from sqlalchemy import text

                records = []

                # Compile all possible keys exactly to avoid pandas missing columns
                all_possible_keys = [
                    "product_id",
                    "chemical_name",
                    "cas_number",
                    "signal_word",
                    "product_type",
                    "type_source",
                    "default_container",
                    "notes",
                    "tara_history",
                    "tara_overrides",
                    "lote",
                    "lotes_info",
                    "requires_attention",
                    "lote_date",
                    "lote_reinspection_date",
                    "lote_history",
                ]

                for pid, props in self._product_classifications.items():
                    rec = {k: None for k in all_possible_keys}
                    rec["product_id"] = pid
                    for k, v in props.items():
                        if k in all_possible_keys:
                            if isinstance(v, (dict, list)):
                                rec[k] = json.dumps(v, ensure_ascii=False)
                            else:
                                rec[k] = v
                    records.append(rec)

                if records:
                    with self.sql_engine.connect() as conn:
                        with conn.begin():
                            # 1. UPSERT classifications using a single connection/transaction
                            conn.execute(text("""
                                IF OBJECT_ID('product_classifications', 'U') IS NULL
                                BEGIN
                                    CREATE TABLE product_classifications (
                                        product_id VARCHAR(50) PRIMARY KEY,
                                        chemical_name NVARCHAR(255),
                                        cas_number VARCHAR(100),
                                        signal_word VARCHAR(100),
                                        product_type VARCHAR(50),
                                        default_container VARCHAR(50),
                                        notes NVARCHAR(MAX),
                                        type_source VARCHAR(50),
                                        tara_history NVARCHAR(MAX),
                                        tara_overrides NVARCHAR(MAX),
                                        lote VARCHAR(255),
                                        lote_date VARCHAR(50),
                                        lote_reinspection_date VARCHAR(50),
                                        lotes_info NVARCHAR(MAX),
                                        lote_history NVARCHAR(MAX),
                                        requires_attention BIT
                                    );
                                END
                            """))
                            
                            conn.execute(text("""
                                IF OBJECT_ID('tempdb..#temp_classifications') IS NOT NULL DROP TABLE #temp_classifications;
                            """))

                            conn.execute(text("""
                                CREATE TABLE #temp_classifications (
                                    product_id VARCHAR(50),
                                    chemical_name NVARCHAR(255),
                                    cas_number VARCHAR(100),
                                    signal_word VARCHAR(100),
                                    product_type VARCHAR(50),
                                    default_container VARCHAR(50),
                                    notes NVARCHAR(MAX),
                                    type_source VARCHAR(50),
                                    tara_history NVARCHAR(MAX),
                                    tara_overrides NVARCHAR(MAX),
                                    lote VARCHAR(255),
                                    lote_date VARCHAR(50),
                                    lote_reinspection_date VARCHAR(50),
                                    lotes_info NVARCHAR(MAX),
                                    lote_history NVARCHAR(MAX),
                                    requires_attention BIT
                                );
                            """))

                            # Upload to the SAME connection's temp table via native executemany
                            conn.execute(
                                text("""
                                    INSERT INTO #temp_classifications (
                                        product_id, chemical_name, cas_number, signal_word, 
                                        product_type, default_container, notes, type_source, 
                                        tara_history, tara_overrides, lote, lote_date, 
                                        lote_reinspection_date, lotes_info, lote_history, requires_attention
                                    ) VALUES (
                                        :product_id, :chemical_name, :cas_number, :signal_word, 
                                        :product_type, :default_container, :notes, :type_source, 
                                        :tara_history, :tara_overrides, :lote, :lote_date, 
                                        :lote_reinspection_date, :lotes_info, :lote_history, :requires_attention
                                    )
                                """),
                                records,
                            )

                            # Merge temp table into actual table
                            conn.execute(text("""
                                MERGE product_classifications AS target
                                USING #temp_classifications AS source
                                ON target.product_id = source.product_id
                                WHEN MATCHED THEN
                                    UPDATE SET 
                                        chemical_name = source.chemical_name,
                                        cas_number = source.cas_number,
                                        signal_word = source.signal_word,
                                        product_type = source.product_type,
                                        default_container = source.default_container,
                                        notes = source.notes,
                                        type_source = source.type_source,
                                        tara_history = source.tara_history,
                                        tara_overrides = source.tara_overrides,
                                        lote = source.lote,
                                        lote_date = source.lote_date,
                                        lote_reinspection_date = source.lote_reinspection_date,
                                        lotes_info = source.lotes_info,
                                        lote_history = CASE 
                                            WHEN source.lote_history IS NULL OR source.lote_history = '[]' OR source.lote_history = '' THEN target.lote_history 
                                            ELSE source.lote_history 
                                        END,
                                        requires_attention = source.requires_attention
                                WHEN NOT MATCHED THEN
                                    INSERT (product_id, chemical_name, cas_number, signal_word, product_type, default_container, notes, type_source, tara_history, tara_overrides, lote, lote_date, lote_reinspection_date, lotes_info, lote_history, requires_attention)
                                    VALUES (source.product_id, source.chemical_name, source.cas_number, source.signal_word, source.product_type, source.default_container, source.notes, source.type_source, source.tara_history, source.tara_overrides, source.lote, source.lote_date, source.lote_reinspection_date, source.lotes_info, source.lote_history, source.requires_attention);
                            """))

                    logger.info("✅ Saved classifications to SQL (UPSERT Mode)")

            except Exception as e:
                logger.error(f"❌ Error saving classifications to SQL: {e}")

        # Added: Sync product_batches to a dedicated SQL table
        if self.sql_engine:
            try:
                from sqlalchemy import text

                batch_records = []
                for pid, props in self._product_classifications.items():
                    if not isinstance(props, dict):
                        continue
                    lotes_info = props.get("lotes_info", {})
                    if not isinstance(lotes_info, dict):
                        lotes_info = {}

                    primary = props.get("lote")
                    if primary and primary not in lotes_info:
                        lotes_info[primary] = {
                            "fecha_elaboracion": props.get("lote_date"),
                            "fecha_inspeccion": props.get("lote_reinspection_date"),
                        }

                    for lote, info in lotes_info.items():
                        if not str(lote).strip() or not isinstance(info, dict):
                            continue

                        f_elab = str(info.get("fecha_elaboracion") or "")[:10]
                        f_insp = str(info.get("fecha_inspeccion") or "")[:10]

                        # import re  # already imported at module level

                        date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
                        batch_records.append(
                            {
                                "product_id": str(pid)[:50],
                                "lote": str(lote)[:255],
                                "fecha_elaboracion": (
                                    f_elab if date_pattern.match(f_elab) else None
                                ),
                                "fecha_reinspeccion": (
                                    f_insp if date_pattern.match(f_insp) else None
                                ),
                            }
                        )

                if batch_records:
                    # Optimized: Use a single transaction and batch MERGE
                    with self.sql_engine.connect() as conn:
                        with conn.begin():
                            # Create table if it doesn't exist
                            conn.execute(text("""
                                IF OBJECT_ID('product_batches', 'U') IS NULL
                                BEGIN
                                    CREATE TABLE product_batches (
                                        id INT IDENTITY(1,1) PRIMARY KEY,
                                        product_id VARCHAR(50),
                                        lote VARCHAR(255),
                                        fecha_elaboracion DATE,
                                        fecha_reinspeccion DATE,
                                        CONSTRAINT UQ_product_batches UNIQUE (product_id, lote)
                                    );
                                END
                            """))

                            conn.execute(text("""
                                IF OBJECT_ID('tempdb..#temp_batches') IS NOT NULL DROP TABLE #temp_batches;
                            """))

                            # Create temp table for batch upsert
                            conn.execute(text("""
                                CREATE TABLE #temp_batches (
                                    product_id VARCHAR(50),
                                    lote VARCHAR(255),
                                    fecha_elaboracion DATE,
                                    fecha_reinspeccion DATE
                                );
                            """))

                            # Fast upload via executemany
                            conn.execute(
                                text(
                                    "INSERT INTO #temp_batches (product_id, lote, fecha_elaboracion, fecha_reinspeccion) VALUES (:product_id, :lote, :fecha_elaboracion, :fecha_reinspeccion)"
                                ),
                                batch_records,
                            )

                            # Single-statement MERGE
                            conn.execute(text("""
                                MERGE product_batches AS target
                                USING #temp_batches AS source
                                ON target.product_id = source.product_id AND target.lote = source.lote
                                WHEN MATCHED THEN
                                    UPDATE SET 
                                        fecha_elaboracion = source.fecha_elaboracion,
                                        fecha_reinspeccion = source.fecha_reinspeccion
                                WHEN NOT MATCHED THEN
                                    INSERT (product_id, lote, fecha_elaboracion, fecha_reinspeccion)
                                    VALUES (source.product_id, source.lote, source.fecha_elaboracion, source.fecha_reinspeccion);
                            """))

                    logger.info(
                        f"✅ Saved {len(batch_records)} batch records to product_batches SQL table (UPSERT mode)"
                    )
            except Exception as e:
                logger.error(f"❌ Error saving batch records to SQL: {e}")

        # Added: Sync product_lote_history to a dedicated SQL table for Control Interno protection
        if self.sql_engine:
            try:
                from sqlalchemy import text
                from datetime import datetime as _dt

                # Helper: sanitize date strings
                _DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

                def _safe_date(val):
                    if val is None:
                        return None
                    s = str(val).strip()[:10]
                    if s.lower() in ("nan", "none", "nat", "", "null"):
                        return None
                    if not _DATE_RE.match(s):
                        return None
                    return s

                def _safe_datetime(val):
                    if val is None:
                        return None
                    s = str(val).strip()[:19]
                    if s.lower() in ("nan", "none", "nat", "", "null"):
                        return None
                    if len(s) < 10:
                        return None
                    try:
                        date_str = s.replace(" ", "T")
                        return _dt.strptime(date_str, "%Y-%m-%dT%H:%M:%S")
                    except ValueError:
                        try:
                            return _dt.strptime(s[:10], "%Y-%m-%d")
                        except ValueError:
                            return None

                seen_history = set()
                history_records = []
                for pid, props in self._product_classifications.items():
                    if not isinstance(props, dict):
                        continue
                    lote_history = props.get("lote_history", [])
                    if not isinstance(lote_history, list):
                        continue

                    for entry in lote_history:
                        if not isinstance(entry, dict):
                            continue
                        raw_event = entry.get("date") or entry.get("timestamp") or ""
                        event_date = _safe_datetime(raw_event)
                        
                        # Fallback to prevent multiple NULLs causing UNIQUE constraint violation in SQL Server
                        if event_date is None:
                            event_date = _dt(1900, 1, 1)
                            
                        unique_key = (str(pid)[:50], str(entry.get("old_lote") or "")[:255], str(entry.get("new_lote") or "")[:255], event_date)
                        if unique_key in seen_history:
                            continue
                        seen_history.add(unique_key)
                        
                        history_records.append(
                            {
                                "product_id": str(pid)[:50],
                                "old_lote": str(entry.get("old_lote") or "")[:255],
                                "new_lote": str(entry.get("new_lote") or "")[:255],
                                "old_date": _safe_date(entry.get("old_date")),
                                "new_date": _safe_date(entry.get("new_date")),
                                "old_reinsp_date": _safe_date(
                                    entry.get("old_reinsp_date")
                                ),
                                "new_reinsp_date": _safe_date(
                                    entry.get("new_reinsp_date")
                                ),
                                "event_date": event_date,
                                "user_name": str(entry.get("user") or "")[:50],
                                "merma_kg": (
                                    float(entry.get("merma_kg"))
                                    if entry.get("merma_kg") is not None
                                    else None
                                ),
                                "notes": str(entry.get("notes") or "")[:4000],
                            }
                        )

                if history_records:
                    # Optimized: Single transaction and batch MERGE for history
                    with self.sql_engine.connect() as conn:
                        with conn.begin():
                            # Create table if it doesn't exist
                            conn.execute(text("""
                                IF OBJECT_ID('product_lote_history', 'U') IS NULL
                                BEGIN
                                    CREATE TABLE product_lote_history (
                                        id INT IDENTITY(1,1) PRIMARY KEY,
                                        product_id VARCHAR(50),
                                        old_lote VARCHAR(255),
                                        new_lote VARCHAR(255),
                                        old_date DATE,
                                        new_date DATE,
                                        old_reinsp_date DATE,
                                        new_reinsp_date DATE,
                                        event_date DATETIME,
                                        user_name VARCHAR(50),
                                        merma_kg FLOAT,
                                        notes NVARCHAR(MAX),
                                        CONSTRAINT UQ_product_lote_history UNIQUE (product_id, old_lote, new_lote, event_date)
                                    );
                                END
                            """))
                            
                            conn.execute(text("""
                                IF OBJECT_ID('tempdb..#temp_history') IS NOT NULL DROP TABLE #temp_history;
                            """))

                            # Create temp table
                            conn.execute(text("""
                                CREATE TABLE #temp_history (
                                    product_id VARCHAR(50),
                                    old_lote VARCHAR(255),
                                    new_lote VARCHAR(255),
                                    old_date DATE,
                                    new_date DATE,
                                    old_reinsp_date DATE,
                                    new_reinsp_date DATE,
                                    event_date DATETIME,
                                    user_name VARCHAR(50),
                                    merma_kg FLOAT,
                                    notes NVARCHAR(MAX)
                                );
                            """))

                            # Fast upload via executemany
                            conn.execute(
                                text("""
                                    INSERT INTO #temp_history (
                                        product_id, old_lote, new_lote, old_date, new_date, 
                                        old_reinsp_date, new_reinsp_date, event_date, user_name, 
                                        merma_kg, notes
                                    ) VALUES (
                                        :product_id, :old_lote, :new_lote, :old_date, :new_date, 
                                        :old_reinsp_date, :new_reinsp_date, :event_date, :user_name, 
                                        :merma_kg, :notes
                                    )
                                """),
                                history_records,
                            )

                            # Single-statement MERGE
                            conn.execute(text("""
                                MERGE product_lote_history AS target
                                USING #temp_history AS source
                                ON target.product_id = source.product_id 
                                   AND target.old_lote = source.old_lote 
                                   AND target.new_lote = source.new_lote
                                   AND target.event_date = source.event_date
                                WHEN MATCHED THEN
                                    UPDATE SET 
                                        old_date = source.old_date,
                                        new_date = source.new_date,
                                        old_reinsp_date = source.old_reinsp_date,
                                        new_reinsp_date = source.new_reinsp_date,
                                        user_name = source.user_name,
                                        merma_kg = source.merma_kg,
                                        notes = source.notes
                                WHEN NOT MATCHED THEN
                                    INSERT (product_id, old_lote, new_lote, old_date, new_date, 
                                            old_reinsp_date, new_reinsp_date, event_date, user_name, merma_kg, notes)
                                    VALUES (source.product_id, source.old_lote, source.new_lote, 
                                            source.old_date, source.new_date, 
                                            source.old_reinsp_date, source.new_reinsp_date, 
                                            source.event_date, source.user_name, source.merma_kg, source.notes);
                            """))

                    logger.info(
                        f"✅ Saved {len(history_records)} lote history records to product_lote_history SQL table (UPSERT mode)"
                    )
            except Exception as e:
                logger.error(f"❌ Error saving lote history records to SQL: {e}")

    def auto_classify_all(self):
        """
        Auto-classify all unclassified products based on:
        1. Historical tara patterns

        2. Chemical name heuristics

        3. Product ID prefix heuristics

        Only fills in products that do not already have a manual classification.

        """

        # Load Excel classifications if not loaded yet

        if not CLASIFICACION_EXCEL_PRODUCTS:

            load_clasificacion_excel()

        # Keywords for product type inference from chemical names

        # ── POLVO ─────────────────────────────────────────────────────────────

        POWDER_KEYWORDS = [
            # Explicit
            "polvo",
            "powder",
            "microesfera",
            "granulo",
            "pellet",
            "escama",
            "flake",
            "perla",
            "grano",
            "tableta",
            "pastilla",
            # Fatty solids & waxes
            "cetilico",
            "estearico",
            "cera ",
            "wax",
            "alcohol cetilico",
            "aceite de castor hidrogenado",
            "aceite de coco rbd",
            # Acids/salts in solid form
            "acido citrico",
            "benzoato de sodio",
            "sorbato de potasio",
            "sulfato de sodio",
            "estanato de sodio",
            "acido estearico",
            # Polymers / thickeners supplied as powder
            "cmc",
            "c.m.c.",
            "edta",
            "carbopol",
            "carbomer",
            "natrosol",
            "benecel",
            "sensomer",
            "cosmedia guar",
            "polyquaternium 10",
            "espesante d150",
            # Actives typically solid
            "menthol",
            "alcanfor",
            "triclosan",
            "octopirox",
            "abrillantador optico polvo",
            # Exfoliants
            "exfoliante",
        ]

        # ── VISCOSO ───────────────────────────────────────────────────────────

        VISCOUS_KEYWORDS = [
            # Known viscous suppliers / series
            "quartamin",
            "poiz",
            "tetranyl",
            "kaosoft",
            "emulboss",
            "ciclodimeticona",
            "silika",
            "fixate",
            "glucam",
            "glucamate",
            "novemer",
            "silsense",
            "copolyol",
            "silicone",
            "silicona",
            # Thickeners / gelling agents (supplied as gel)
            "viscosol",
            "novethix",
            "noverite",
            "lubrajel",
            # Latexes / emulsions (thick)
            "butonal",
            "latex ",
            # Physical descriptors
            "pasta",
            "crema",
            "vaselina",
            "lanolina",
            "manteca",
            "shea butter",
            "gel ",
            " gel",
            # Cosmetic conditioning agents
            "cationics",
            "dynagen",
            # Cellulose solutions (liquid viscoso)
            "arbalon",
            # Rheology modifiers in solution
            "aquaflex",
        ]

        # ── COLOR ─────────────────────────────────────────────────────────────

        COLOR_KEYWORDS = [
            "color ",
            "color amarillo",
            "color azul",
            "color rojo",
            "color verde",
            "color violeta",
            "color negro",
            "rodamina",
            "colorante",
            "tinte",
            "dye",
            "pigment",
            "chromafen",
        ]

        # ── LIGERO ────────────────────────────────────────────────────────────

        LIGERO_KEYWORDS = [
            # Fragrance raw materials
            "citrus",
            "lemon",
            "lime",
            "limon",
            "naranja",
            "grapefruit",
            "toronja",
            "fruity",
            "pino",
            "citronella",
            "terpenos",
            "d-limoneno",
            "aceite de pino",
            # Light solvents
            "ipa",
            "isopropanol",
            "alcohol isopropilico",
            "acetato de isoamilo",
            "transcutol",
            # Light mineral oils / esters
            "aceite mineral",
            "miristato de isopropilo",
            "danox",
            "surfadone",
            # Difuser bases
            "base para difusores",
            "difusor",
        ]

        # ── SÓLIDO ────────────────────────────────────────────────────────────

        SOLID_KEYWORDS = [
            "solido",
            "solid ",
        ]

        changes = 0

        for code, data in list(self._product_classifications.items()):

            if should_exclude_from_control_interno(code):

                continue

            # Skip products already classified manually or from Excel — only fill in unclassified ones

            if data.get("product_type") and data.get("type_source") in (
                "manual",
                "excel",
            ):

                continue

            name = (data.get("chemical_name") or "").lower()

            inferred_type = None

            source = "auto"

            # 0. CLASIFICACION.xlsx direct mapping (highest priority)

            if code in CLASIFICACION_EXCEL_PRODUCTS:

                inferred_type = CLASIFICACION_EXCEL_PRODUCTS[code]

                source = "excel"

            # 1. Check tara history — powders use bags (low tara)

            if not inferred_type and code in self._product_tara_cache:

                taras = set(self._product_tara_cache[code].values())

                if taras.intersection({0.015, 0.035}):

                    inferred_type = "polvo"

                elif taras.intersection({0.29}) and not taras.intersection(
                    {0.09, 0.24}
                ):

                    inferred_type = "viscoso"

            # 2. Name-based heuristics (more specific first)

            if not inferred_type:

                for kw in COLOR_KEYWORDS:

                    if kw in name:

                        inferred_type = "color"

                        break

            if not inferred_type:

                for kw in VISCOUS_KEYWORDS:

                    if kw in name:

                        inferred_type = "viscoso"

                        break

            if not inferred_type:

                for kw in POWDER_KEYWORDS:

                    if kw in name:

                        inferred_type = "polvo"

                        break

            if not inferred_type:

                for kw in LIGERO_KEYWORDS:

                    if kw in name:

                        inferred_type = "ligero"

                        break

            if not inferred_type:

                for kw in SOLID_KEYWORDS:

                    if kw in name:

                        inferred_type = "solido"

                        break

            # 3. Prefix-based heuristics (last resort for unrecognized names)

            if not inferred_type:

                if code.startswith("IFF-"):

                    inferred_type = (
                        "liquido"  # IFF = fragrances / liquid specialty chemicals
                    )

                elif code.startswith("KAO-"):

                    inferred_type = (
                        "viscoso"  # KAO = Kao specialty chemicals, often viscous
                    )

                elif code.startswith("ASH-"):

                    inferred_type = (
                        "liquido"  # Ashland specialty chemicals — mostly liquids
                    )

                elif code.startswith("LUB-"):

                    inferred_type = (
                        "liquido"  # Lubrizol / Lubrichem — mostly liquid actives
                    )

                elif code.startswith("VAR-"):

                    inferred_type = "liquido"  # VAR general chemicals — mostly liquid surfactants/actives

                elif code.startswith("PRD-"):

                    inferred_type = (
                        "liquido"  # PRD = internal products (aromatics / bases)
                    )

                elif code.startswith("BSF-"):

                    inferred_type = (
                        "viscoso"  # BASF specialty — often viscous emulsions
                    )

            if inferred_type:

                data["product_type"] = inferred_type

                data["type_source"] = source

                changes += 1

        if changes > 0:

            self._save_classifications()

            logger.info(f"✅ Auto-classified {changes} products")

        return changes

    def initialize_classifications(self, smart_label_manager=None, force=False):
        """

        Initialize the classification database from all known products.

        Merges data from: products_master CSV, original_data CSV, and existing classifications.

        """
        if self._is_initialized and not force:
            return len(self._product_classifications)

        self._load_classifications()

        # Gather all known products
        all_products = {}

        # 1. Start by attempting to load from SmartLabelManager (so we get SQL/live info if available)
        if smart_label_manager and smart_label_manager.df_products is not None:
            for _, row in smart_label_manager.df_products.iterrows():
                pid = str(row.get("product_id", "")).strip()
                if not pid:
                    # Check legacy format
                    pid = str(row.get("Codigo interno", "")).strip()
                if pid:
                    all_products[pid] = {
                        "chemical_name": str(
                            row.get("chemical_name", row.get("Chemical Name", ""))
                        ).strip(),
                        "cas_number": str(
                            row.get("cas_number", row.get("CAS Number", ""))
                        ).strip(),
                        "signal_word": str(
                            row.get("signal_word", row.get("Signal Word", ""))
                        ).strip(),
                    }

        # 2. Fallback or addition: From products_master.csv (unified_db)
        base = os.path.dirname(os.path.abspath(__file__))

        pm_path = os.path.join(base, "unified_db", "products_master.csv")

        if os.path.exists(pm_path):

            try:

                pm = pd.read_csv(pm_path, dtype=str)

                for _, row in pm.iterrows():

                    pid = str(row.get("product_id", "")).strip()

                    if pid:

                        all_products[pid] = {
                            "chemical_name": str(row.get("chemical_name", "")).strip(),
                            "cas_number": str(row.get("cas_number", "")).strip(),
                            "signal_word": str(row.get("signal_word", "")).strip(),
                        }

            except Exception as e:

                logger.error(f"Error reading products_master: {e}")

        # From original_data CSV (has tara info)

        if self._csv_path and os.path.exists(self._csv_path):

            try:

                df = pd.read_csv(self._csv_path, dtype=str)

                df.columns = [c.strip() for c in df.columns]

                df = df.dropna(subset=["Codigo interno"])

                for _, row in df.drop_duplicates("Codigo interno").iterrows():

                    pid = str(row["Codigo interno"]).strip()

                    if pid and pid not in all_products:

                        all_products[pid] = {
                            "chemical_name": str(row.get("Chemical Name", "")).strip(),
                            "cas_number": "",
                            "signal_word": "",
                        }

            except Exception:

                pass

        # Merge into classifications — add new products, keep existing entries

        new_count = 0

        for pid, info in all_products.items():

            if pid not in self._product_classifications:

                self._product_classifications[pid] = {
                    "product_id": pid,
                    "chemical_name": info["chemical_name"],
                    "cas_number": info.get("cas_number", ""),
                    "signal_word": info.get("signal_word", ""),
                    "product_type": "",  # liquido|pasta|polvo|solido
                    "type_source": "",  # auto|manual
                    "default_container": "",  # container_id from CONTAINER_CATALOG
                    "notes": "",
                    "tara_overrides": {},  # {peso_neto_str: tara_kg}
                }

                new_count += 1

            else:

                # Update chemical name if empty

                existing = self._product_classifications[pid]

                if not existing.get("chemical_name") and info["chemical_name"]:

                    existing["chemical_name"] = info["chemical_name"]

        # Add tara history as overrides

        for code, tara_map in self._product_tara_cache.items():

            if code in self._product_classifications:

                existing_overrides = self._product_classifications[code].get(
                    "tara_overrides", {}
                )

                for peso_neto, tara_kg in tara_map.items():

                    key = str(peso_neto)

                    if key not in existing_overrides:

                        existing_overrides[key] = tara_kg

                self._product_classifications[code][
                    "tara_overrides"
                ] = existing_overrides

        if new_count > 0:

            self._save_classifications()

            logger.info(f"✅ Initialized {new_count} new product classifications")

        # Auto-classify products that haven't been classified yet

        self.auto_classify_all()

        self._is_initialized = True

        return len(self._product_classifications)

    def get_classifications(
        self,
        page: int = 1,
        per_page: int = 50,
        search: str = "",
        product_type: str = "",
        status: str = "",
    ) -> Tuple[List[Dict], int]:
        """

        Return paginated product classifications with filtering.

        status: 'classified' | 'unclassified' | '' (all)

        """

        items = [
            p
            for p in self._product_classifications.values()
            if not should_exclude_from_control_interno(p.get("product_id", ""))
        ]

        # Filter by search

        if search:

            s = search.lower()

            items = [
                p
                for p in items
                if s in (p.get("product_id") or "").lower()
                or s in (p.get("chemical_name") or "").lower()
            ]

        # Filter by product type

        if product_type:

            items = [p for p in items if p.get("product_type") == product_type]

        # Filter by classification status

        if status == "classified":

            items = [p for p in items if p.get("product_type")]

        elif status == "unclassified":

            items = [p for p in items if not p.get("product_type")]

        elif status == "lote":

            items = [p for p in items if p.get("lote")]

        elif status == "sin_lote":

            items = [p for p in items if not p.get("lote")]

        elif status == "atencion":

            from datetime import datetime

            atencion_items = []

            for p in items:

                req = False

                lotes_info = p.get("lotes_info", {})

                if isinstance(lotes_info, dict):

                    for lname, info in lotes_info.items():

                        fecha_ins = info.get("fecha_inspeccion")

                        if fecha_ins:

                            try:

                                insp_date = datetime.strptime(fecha_ins, "%Y-%m-%d")

                                if (insp_date - datetime.now()).days <= 180:

                                    req = True

                                    break

                            except ValueError:

                                pass

                if req:

                    atencion_items.append(p)

            items = atencion_items

        # Sort by product_id

        items.sort(key=lambda p: p.get("product_id", ""))

        total = len(items)

        start = (page - 1) * per_page

        end = start + per_page

        return items[start:end], total

    def get_classification(self, product_id: str) -> Optional[Dict]:
        """Get classification for a single product."""

        if should_exclude_from_control_interno(product_id):

            return None

        return self._product_classifications.get(product_id)

    def update_classification(self, product_id: str, updates: Dict) -> bool:
        """Update a product classification."""

        if should_exclude_from_control_interno(product_id):
            return False

        if product_id not in self._product_classifications:
            return False

        entry = self._product_classifications[product_id]

        # Check if product_type is changing
        old_type = entry.get("product_type", "")
        new_type = updates.get("product_type")

        # If product type changed (or is being set to empty/different), clear tara_overrides and default_container
        if new_type is not None and new_type != old_type:
            entry["tara_overrides"] = {}
            entry["default_container"] = ""
            # Filter them out of updates so they don't overwrite the cleared values
            updates = dict(updates)
            updates.pop("tara_overrides", None)
            updates.pop("default_container", None)

        allowed_fields = [
            "product_type",
            "default_container",
            "notes",
            "tara_overrides",
            "lote",
            "lote_date",
            "lote_reinspection_date",
            "lote_history",
            "lotes_info",
        ]

        for field in allowed_fields:
            if field in updates:
                entry[field] = updates[field]

        # Mark as manually classified if product_type was set
        if "product_type" in updates and updates["product_type"]:
            entry["type_source"] = "manual"

        self._sync_priority_lotes()
        self._save_classifications()
        return True

    def bulk_update_type(self, product_ids: List[str], product_type: str) -> int:
        """Bulk update product types for multiple products."""

        count = 0

        for pid in product_ids:

            if should_exclude_from_control_interno(pid):
                continue

            if pid in self._product_classifications:
                entry = self._product_classifications[pid]
                old_type = entry.get("product_type", "")
                if old_type != product_type:
                    entry["product_type"] = product_type
                    entry["type_source"] = "manual"
                    entry["tara_overrides"] = {}
                    entry["default_container"] = ""
                    count += 1

        if count > 0:
            self._save_classifications()

        return count

    def get_classification_summary(self) -> Dict:
        """Return count of products by type."""

        summary = {
            "liquido": 0,
            "viscoso": 0,
            "polvo": 0,
            "color": 0,
            "ligero": 0,
            "solido": 0,
            "sin_clasificar": 0,
        }

        for p in self._product_classifications.values():

            if should_exclude_from_control_interno(p.get("product_id", "")):

                continue

            pt = p.get("product_type", "")

            if pt in summary:

                summary[pt] += 1

            else:

                summary["sin_clasificar"] += 1

        return summary

    def import_from_excel(self, excel_path: Optional[str] = None) -> Dict:
        """

        Import classifications AND per-product NETO->TARA pairs from CLASIFICACION.xlsx.



        For each product found in a sheet:

        - Sets product_type from the sheet name (liquido/viscoso/polvo/color/ligero)

        - Saves the NETO->TARA pair from that row as a tara_override so that

          get_smart_suggestions will use the correct container for that weight.



        Manual classifications (type_source='manual') are NOT overwritten.

        Tara overrides ARE always added/updated from the Excel (Excel is the authoritative source).

        """

        if excel_path is None:

            base = os.path.dirname(os.path.abspath(__file__))

            excel_path = os.path.join(base, "original_data", "CLASIFICACION.xlsx")

        if not os.path.exists(excel_path):

            return {
                "success": False,
                "error": f"CLASIFICACION.xlsx not found at {excel_path}",
                "imported": 0,
            }

        SHEET_TYPE_MAP = {
            "LIQUIDOS": "liquido",
            "VISCOSOS": "viscoso",
            "POLVOS": "polvo",
            "COLORES": "color",
            "LIGEROS": "ligero",
        }

        imported = 0

        skipped_manual = 0

        new_products = 0

        tara_overrides_added = 0

        try:

            xls = pd.ExcelFile(excel_path)

        except Exception as e:

            return {"success": False, "error": str(e), "imported": 0}

        for sheet_name, product_type in SHEET_TYPE_MAP.items():

            if sheet_name not in xls.sheet_names:

                continue

            try:

                df = pd.read_excel(xls, sheet_name=sheet_name, dtype=str)

                df.columns = [c.strip() for c in df.columns]

                # Find product_id column

                col_pid = next((c for c in df.columns if "codigo" in c.lower()), None)

                # Find NETO and TARA columns (strip spaces from headers)

                col_neto = next(
                    (c for c in df.columns if c.upper().startswith("NETO")), None
                )

                col_tara = next(
                    (c for c in df.columns if c.upper().startswith("TARA")), None
                )

                for _, row in df.iterrows():

                    pid = str(row.get(col_pid, "") if col_pid else "").strip()

                    if not pid or pid == "nan" or pid.lower().startswith("codigo"):

                        continue

                    # ── Product type import ────────────────────────────────

                    if pid in self._product_classifications:

                        entry = self._product_classifications[pid]

                        if entry.get("type_source") == "manual":

                            skipped_manual += 1

                        else:

                            entry["product_type"] = product_type

                            entry["type_source"] = "excel"

                            imported += 1

                    else:

                        self._product_classifications[pid] = {
                            "product_id": pid,
                            "chemical_name": (
                                str(row.get("Chemical Name", "")).strip()
                                if "Chemical Name" in df.columns
                                else ""
                            ),
                            "cas_number": "",
                            "signal_word": "",
                            "product_type": product_type,
                            "type_source": "excel",
                            "default_container": "",
                            "notes": "",
                            "tara_overrides": {},
                        }

                        imported += 1

                        new_products += 1

                    # ── Tara override import (NETO->TARA from Excel row) ───

                    if col_neto and col_tara:

                        try:

                            neto_val = float(
                                str(row.get(col_neto, "")).replace(",", ".")
                            )

                            tara_val = float(
                                str(row.get(col_tara, "")).replace(",", ".")
                            )

                            if neto_val > 0 and tara_val > 0:

                                entry = self._product_classifications[pid]

                                overrides = entry.setdefault("tara_overrides", {})

                                key = str(neto_val)

                                overrides[key] = tara_val

                                tara_overrides_added += 1

                        except (ValueError, TypeError):

                            pass  # Row without valid NETO/TARA data — skip silently

            except Exception as e:

                logger.error(f"❌ Error reading sheet {sheet_name}: {e}")

                continue

        if imported > 0 or tara_overrides_added > 0:

            self._save_classifications()

        return {
            "success": True,
            "imported": imported,
            "skipped_manual": skipped_manual,
            "new_products": new_products,
            "tara_overrides_added": tara_overrides_added,
            "total_in_excel": imported + skipped_manual,
        }

    def get_tara_table_for_type(self, product_type: str) -> Dict[float, float]:
        """Return the tara lookup table for a specific product type."""

        return dict(TARA_BY_TYPE.get(product_type, {}))

    def get_packaging_notes(self, peso_neto: float) -> Optional[str]:
        """Return special packaging notes for large weights (e.g. multi-container)."""

        peso_int = int(peso_neto) if peso_neto == int(peso_neto) else None

        if peso_int and peso_int in LIQUIDOS_PACKAGING_NOTES:

            return LIQUIDOS_PACKAGING_NOTES[peso_int]

        return None


# Singleton instance (lazy-loaded)

_instance: Optional[TaraWeightManager] = None


def get_tara_manager(csv_path: Optional[str] = None) -> TaraWeightManager:
    """Get or create the singleton TaraWeightManager instance."""

    global _instance

    if _instance is None:

        if csv_path is None:

            # Try default path

            base = os.path.dirname(os.path.abspath(__file__))

            csv_path = os.path.join(
                base, "original_data", "Sample DataBase Tectronic QBR.csv"
            )

        _instance = TaraWeightManager(csv_path)

    return _instance
