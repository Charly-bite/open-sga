#!/usr/bin/env python3
"""
Unified Database Builder for SGA (Sistema de Gestión de Almacén)

This script creates a normalized, SAP-ready database structure by:
1. Loading and cleaning local GHS data (CSV sources)
2. Normalizing H-Statements and P-Statements into lookup tables
3. Creating relational junction tables (Product <-> Statements)
4. Preparing the structure for SAP HANA material sync

Output Structure (unified_db/):
├── products_master.csv      # Core product safety data
├── h_statements.csv         # H-Statement lookup table
├── p_statements.csv         # P-Statement lookup table
├── product_hazards.csv      # Product <-> H-Statement relationships
├── product_precautions.csv  # Product <-> P-Statement relationships
├── product_pictograms.csv   # Product <-> Pictogram relationships
├── pictograms.csv           # Pictogram master data
├── product_variants.csv     # Barcode/PackSize variants
└── sap_material_sync.csv    # Mapping to SAP MATNR (populated after sync)

Usage:
    python unify_for_sga.py              # Build from local data only
    python unify_for_sga.py --with-sap   # Include SAP material sync
"""

import os
import sys
import json
import glob
import re
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ORIGINAL_DATA_DIR = os.path.join(BASE_DIR, "original_data")
UNIFIED_DB_DIR = os.path.join(BASE_DIR, "unified_db")
ASSETS_DIR = os.path.join(BASE_DIR, "assets", "pictograms")

# Pictogram definitions
PICTOGRAM_DEFINITIONS = {
    "exclamacion": {
        "id": "GHS07",
        "name": "Exclamación",
        "ghs_code": "GHS07",
        "un_code": "UN3082",
    },
    "corrosion": {
        "id": "GHS05",
        "name": "Corrosión",
        "ghs_code": "GHS05",
        "un_code": "UN1760",
    },
    "peligro_salud": {
        "id": "GHS08",
        "name": "Peligro para la salud",
        "ghs_code": "GHS08",
        "un_code": "UN2810",
    },
    "calavera": {
        "id": "GHS06",
        "name": "Calavera",
        "ghs_code": "GHS06",
        "un_code": "UN2810",
    },
    "llama": {"id": "GHS02", "name": "Llama", "ghs_code": "GHS02", "un_code": "UN1993"},
    "ambiente": {
        "id": "GHS09",
        "name": "Ambiente",
        "ghs_code": "GHS09",
        "un_code": "UN3082",
    },
    "llama_circulo": {
        "id": "GHS03",
        "name": "Llama sobre círculo",
        "ghs_code": "GHS03",
        "un_code": "UN2015",
    },
    "bomba": {
        "id": "GHS01",
        "name": "Bomba explotando",
        "ghs_code": "GHS01",
        "un_code": "UN0349",
    },
    "cilindro": {
        "id": "GHS04",
        "name": "Cilindro de gas",
        "ghs_code": "GHS04",
        "un_code": "UN1956",
    },
}

# Column name mapping for pictograms in source data
PICTO_COLUMN_MAP = {
    "Exclamación": "exclamacion",
    "Corrosión": "corrosion",
    "Peligro para la salud": "peligro_salud",
    "Calavera": "calavera",
    "Llama": "llama",
    "Ambiente": "ambiente",
    "Llama sobre círculo": "llama_circulo",
    "Bomba explotando": "bomba",
    "Cilindro de gas": "cilindro",
}


# =============================================================================
# DATA LOADING
# =============================================================================


def find_csv_by_pattern(directory: str, pattern: str) -> Optional[str]:
    """Find a CSV file matching a pattern."""
    matches = glob.glob(os.path.join(directory, f"*{pattern}*.csv"))
    if matches:
        return matches[0]
    return None


def load_master_products() -> pd.DataFrame:
    """Load the main product database."""
    logger.info("Loading master product database...")

    # Try to find the main GHS database
    file_path = find_csv_by_pattern(
        ORIGINAL_DATA_DIR, "GHS Sample DataBase Tectronic Q"
    )

    if not file_path:
        # Fallback to unified database if it exists
        file_path = os.path.join(ORIGINAL_DATA_DIR, "Unified_GHS_Database.csv")

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"No product database found in {ORIGINAL_DATA_DIR}")

    logger.info(f"  Found: {os.path.basename(file_path)}")

    df = pd.read_csv(file_path, dtype=str, encoding="utf-8")
    df.fillna("", inplace=True)

    # Standardize column names (remove PICTOGRAMA suffix)
    rename_map = {}
    for col in df.columns:
        if "(PICTOGRAMA" in col:
            new_name = col.split("(")[0].strip()
            rename_map[col] = new_name

    if rename_map:
        df.rename(columns=rename_map, inplace=True)

    logger.info(f"  Loaded {len(df)} products")
    return df


def load_h_statements() -> pd.DataFrame:
    """Load H-Statement definitions."""
    logger.info("Loading H-Statement definitions...")

    file_path = find_csv_by_pattern(ORIGINAL_DATA_DIR, "Significados de H")

    if not file_path:
        raise FileNotFoundError("H-Statements file not found")

    df = pd.read_csv(file_path, dtype=str, encoding="utf-8")
    df.fillna("", inplace=True)

    # Standardize column names
    df.columns = ["h_code", "description_es"]

    # Clean H codes
    df["h_code"] = df["h_code"].str.strip().str.upper()

    logger.info(f"  Loaded {len(df)} H-Statements")
    return df


def load_p_statements() -> pd.DataFrame:
    """Load P-Statement definitions."""
    logger.info("Loading P-Statement definitions...")

    file_path = find_csv_by_pattern(ORIGINAL_DATA_DIR, "Significados de P")

    if not file_path:
        raise FileNotFoundError("P-Statements file not found")

    df = pd.read_csv(file_path, dtype=str, encoding="utf-8")
    df.fillna("", inplace=True)

    # Standardize column names
    df.columns = ["p_code", "description_es"]

    # Clean P codes
    df["p_code"] = df["p_code"].str.strip().str.upper()

    logger.info(f"  Loaded {len(df)} P-Statements")
    return df


def load_barcode_mappings() -> Dict:
    """Load barcode to product mappings."""
    logger.info("Loading barcode mappings...")

    file_path = os.path.join(BASE_DIR, "mock_barcode_db.json")

    if not os.path.exists(file_path):
        logger.warning("  No barcode database found, using empty mappings")
        return {"mappings": {}, "variants": {}}

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    logger.info(f"  Loaded {len(data.get('mappings', {}))} barcode mappings")
    return data


# =============================================================================
# DATA TRANSFORMATION
# =============================================================================


def parse_statement_codes(statement_string: str) -> List[str]:
    """
    Parse a comma-separated string of H/P statement codes.

    Examples:
        "H227, H304, H315" -> ['H227', 'H304', 'H315']
        "P210, P261, P280" -> ['P210', 'P261', 'P280']
    """
    if not statement_string or statement_string.lower() in ["no aplicable", "na", ""]:
        return []

    # Handle multi-line emergency procedures (not statement codes)
    if "\n" in statement_string and len(statement_string) > 200:
        return []

    # Find all H/P codes using regex
    codes = re.findall(r"[HP]\d+(?:\s*\+\s*[HP]?\d+)*", statement_string.upper())

    # Clean up compound codes (P301 + P310 -> P301+P310)
    cleaned = []
    for code in codes:
        # Remove spaces around +
        code = re.sub(r"\s*\+\s*", "+", code)
        cleaned.append(code)

    return cleaned


def build_products_master(df: pd.DataFrame) -> pd.DataFrame:
    """Build the normalized products master table."""
    logger.info("Building products_master table...")

    # Define the core columns we want
    master_columns = {
        "Codigo interno": "product_id",
        "Chemical Name": "chemical_name",
        "CAS Number": "cas_number",
        "Signal Word": "signal_word",
        "Emergencia": "emergency_phone",
        "Fecha de actualización": "last_updated",
        "Requiere actualizar": "needs_update",
    }

    # Build the master table
    result = pd.DataFrame()

    for src_col, dst_col in master_columns.items():
        if src_col in df.columns:
            result[dst_col] = df[src_col]
        else:
            result[dst_col] = ""

    # Add SAP placeholder columns
    result["sap_matnr"] = ""  # Will be populated after SAP sync
    result["sap_sync_date"] = ""
    result["is_active"] = "Y"

    # Clean up
    result = result[result["product_id"].str.strip() != ""]
    result.drop_duplicates(subset=["product_id"], keep="first", inplace=True)

    logger.info(f"  Created {len(result)} product records")
    return result


def build_product_hazards(df: pd.DataFrame) -> pd.DataFrame:
    """Build the product <-> H-Statement junction table."""
    logger.info("Building product_hazards junction table...")

    records = []
    h_col = "H-Statements" if "H-Statements" in df.columns else None

    if not h_col:
        for col in df.columns:
            if "h-statement" in col.lower() or col == "H":
                h_col = col
                break

    if not h_col:
        logger.warning("  No H-Statements column found")
        return pd.DataFrame(columns=["product_id", "h_code"])

    for _, row in df.iterrows():
        product_id = str(row.get("Codigo interno", "")).strip()
        if not product_id:
            continue

        h_codes = parse_statement_codes(str(row.get(h_col, "")))

        for code in h_codes:
            records.append({"product_id": product_id, "h_code": code})

    result = pd.DataFrame(records)
    result.drop_duplicates(inplace=True)

    logger.info(f"  Created {len(result)} product-hazard relationships")
    return result


def build_product_precautions(df: pd.DataFrame) -> pd.DataFrame:
    """Build the product <-> P-Statement junction table."""
    logger.info("Building product_precautions junction table...")

    records = []
    p_col = "Consejos (Frases P)" if "Consejos (Frases P)" in df.columns else None

    if not p_col:
        for col in df.columns:
            if "consejos" in col.lower() or "frases p" in col.lower() or col == "P":
                p_col = col
                break

    if not p_col:
        logger.warning("  No P-Statements column found")
        return pd.DataFrame(columns=["product_id", "p_code"])

    for _, row in df.iterrows():
        product_id = str(row.get("Codigo interno", "")).strip()
        if not product_id:
            continue

        p_codes = parse_statement_codes(str(row.get(p_col, "")))

        for code in p_codes:
            records.append({"product_id": product_id, "p_code": code})

    result = pd.DataFrame(records)
    result.drop_duplicates(inplace=True)

    logger.info(f"  Created {len(result)} product-precaution relationships")
    return result


def build_product_pictograms(df: pd.DataFrame) -> pd.DataFrame:
    """Build the product <-> pictogram junction table."""
    logger.info("Building product_pictograms junction table...")

    records = []

    for _, row in df.iterrows():
        product_id = str(row.get("Codigo interno", "")).strip()
        if not product_id:
            continue

        for col_name, picto_key in PICTO_COLUMN_MAP.items():
            # Check if this column exists and has a value
            value = str(row.get(col_name, "")).strip().upper()
            if value == "X":
                picto_def = PICTOGRAM_DEFINITIONS.get(picto_key, {})
                records.append(
                    {
                        "product_id": product_id,
                        "pictogram_id": picto_def.get("id", picto_key),
                    }
                )

    result = pd.DataFrame(records)
    result.drop_duplicates(inplace=True)

    logger.info(f"  Created {len(result)} product-pictogram relationships")
    return result


def build_pictograms_master() -> pd.DataFrame:
    """Build the pictograms master table."""
    logger.info("Building pictograms master table...")

    records = []

    for key, info in PICTOGRAM_DEFINITIONS.items():
        # Check if asset file exists
        asset_path = os.path.join(ASSETS_DIR, f"{key}.png")

        records.append(
            {
                "pictogram_id": info["id"],
                "name": info["name"],
                "ghs_code": info["ghs_code"],
                "un_code": info["un_code"],
                "asset_filename": f"{key}.png",
                "asset_exists": "Y" if os.path.exists(asset_path) else "N",
            }
        )

    result = pd.DataFrame(records)

    logger.info(f"  Created {len(result)} pictogram definitions")
    return result


def build_product_variants(barcode_data: Dict) -> pd.DataFrame:
    """Build the product variants (barcodes/pack sizes) table."""
    logger.info("Building product_variants table...")

    records = []

    mappings = barcode_data.get("mappings", {})
    variants = barcode_data.get("variants", {})

    for barcode, product_id in mappings.items():
        variant_info = variants.get(barcode, {})

        records.append(
            {
                "variant_id": f"VAR-{barcode}",
                "product_id": product_id,
                "barcode": barcode,
                "pack_size": variant_info.get("pack_size", ""),
                "description": variant_info.get("description", ""),
                "is_active": "Y",
            }
        )

    result = pd.DataFrame(records)

    logger.info(f"  Created {len(result)} product variants")
    return result


# =============================================================================
# SAP HANA INTEGRATION
# =============================================================================


def sync_with_sap_hana(
    products_df: pd.DataFrame, username: str, password: str
) -> pd.DataFrame:
    """
    Sync local product data with SAP HANA material master.

    This function:
    1. Connects to SAP HANA
    2. Retrieves material master data
    3. Attempts to match local products to SAP materials
    4. Updates the sap_matnr field where matches are found
    """
    logger.info("Syncing with SAP HANA...")

    try:
        from sap_connector import SAPHanaConnector

        connector = SAPHanaConnector(dsn="SAP Hana")
        connector.connect(username, password)

        # Get SAP materials
        sap_materials = connector.get_materials_for_ghs_sync()

        logger.info(f"  Retrieved {len(sap_materials)} materials from SAP")

        # Create mapping table
        sync_records = []

        for _, product in products_df.iterrows():
            product_id = product["product_id"]
            chemical_name = product["chemical_name"].upper()

            # Try to find matching SAP material
            matched_matnr = None
            match_method = None

            # Method 1: Exact product ID match
            exact_match = sap_materials[
                sap_materials["sap_matnr"].str.strip() == product_id.strip()
            ]
            if len(exact_match) > 0:
                matched_matnr = exact_match.iloc[0]["sap_matnr"]
                match_method = "exact_id"

            # Method 2: Name similarity match
            if not matched_matnr:
                name_match = sap_materials[
                    sap_materials["chemical_name"]
                    .str.upper()
                    .str.contains(chemical_name[:20], na=False, regex=False)
                ]
                if len(name_match) > 0:
                    matched_matnr = name_match.iloc[0]["sap_matnr"]
                    match_method = "name_similarity"

            sync_records.append(
                {
                    "product_id": product_id,
                    "chemical_name": product["chemical_name"],
                    "sap_matnr": matched_matnr or "",
                    "match_method": match_method or "no_match",
                    "sync_date": datetime.now().isoformat(),
                }
            )

        connector.disconnect()

        result = pd.DataFrame(sync_records)

        matched = result[result["sap_matnr"] != ""]
        logger.info(
            f"  Matched {len(matched)} of {len(result)} products to SAP materials"
        )

        return result

    except ImportError:
        logger.error("SAP connector not available")
        return pd.DataFrame()
    except Exception as e:
        logger.error(f"SAP sync failed: {e}")
        return pd.DataFrame()


# =============================================================================
# OUTPUT
# =============================================================================


def save_unified_database(tables: Dict[str, pd.DataFrame]):
    """Save all tables to the unified_db directory."""
    logger.info(f"Saving unified database to {UNIFIED_DB_DIR}...")

    # Create output directory
    os.makedirs(UNIFIED_DB_DIR, exist_ok=True)

    for name, df in tables.items():
        file_path = os.path.join(UNIFIED_DB_DIR, f"{name}.csv")
        df.to_csv(file_path, index=False, encoding="utf-8")
        logger.info(f"  Saved {name}.csv ({len(df)} rows)")

    # Create manifest file
    manifest = {
        "created": datetime.now().isoformat(),
        "tables": {name: len(df) for name, df in tables.items()},
        "version": "1.0",
    }

    manifest_path = os.path.join(UNIFIED_DB_DIR, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    logger.info(f"✅ Unified database created with {len(tables)} tables")


# =============================================================================
# MAIN
# =============================================================================


def main():
    """Main execution function."""
    print("=" * 70)
    print("  UNIFIED DATABASE BUILDER FOR SGA")
    print("  Sistema de Gestión de Almacén - SAP Integration")
    print("=" * 70)
    print()

    # Check for SAP sync flag
    with_sap = "--with-sap" in sys.argv

    try:
        # Step 1: Load source data
        print("\n📂 STEP 1: Loading source data...")
        print("-" * 40)

        df_products_raw = load_master_products()
        df_h_statements = load_h_statements()
        df_p_statements = load_p_statements()
        barcode_data = load_barcode_mappings()

        # Step 2: Transform data
        print("\n🔄 STEP 2: Transforming data...")
        print("-" * 40)

        products_master = build_products_master(df_products_raw)
        product_hazards = build_product_hazards(df_products_raw)
        product_precautions = build_product_precautions(df_products_raw)
        product_pictograms = build_product_pictograms(df_products_raw)
        pictograms = build_pictograms_master()
        product_variants = build_product_variants(barcode_data)

        # Step 3: SAP Sync (optional)
        sap_sync = pd.DataFrame()

        if with_sap:
            print("\n🔗 STEP 3: SAP HANA Sync...")
            print("-" * 40)

            import getpass

            username = input("SAP Username: ").strip()
            password = getpass.getpass("SAP Password: ")

            sap_sync = sync_with_sap_hana(products_master, username, password)

            # Update products_master with SAP MATNR
            if not sap_sync.empty:
                matnr_map = dict(zip(sap_sync["product_id"], sap_sync["sap_matnr"]))
                products_master["sap_matnr"] = (
                    products_master["product_id"].map(matnr_map).fillna("")
                )
                products_master["sap_sync_date"] = datetime.now().isoformat()

        # Step 4: Save unified database
        print("\n💾 STEP 4: Saving unified database...")
        print("-" * 40)

        tables = {
            "products_master": products_master,
            "h_statements": df_h_statements,
            "p_statements": df_p_statements,
            "product_hazards": product_hazards,
            "product_precautions": product_precautions,
            "product_pictograms": product_pictograms,
            "pictograms": pictograms,
            "product_variants": product_variants,
        }

        if not sap_sync.empty:
            tables["sap_material_sync"] = sap_sync

        save_unified_database(tables)

        # Summary
        print("\n" + "=" * 70)
        print("  ✅ UNIFIED DATABASE BUILD COMPLETE")
        print("=" * 70)
        print(f"\n📁 Output directory: {UNIFIED_DB_DIR}")
        print("\n📊 Table Summary:")
        for name, df in tables.items():
            print(f"   • {name}: {len(df)} records")

        print("\n🔜 Next Steps:")
        print("   1. Review data in unified_db/ directory")
        print("   2. Run with --with-sap to sync material numbers")
        print("   3. Import into GHS Label System via SmartLabelManager")

    except FileNotFoundError as e:
        logger.error(f"❌ Required file not found: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
