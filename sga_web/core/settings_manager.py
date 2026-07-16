import json
import os
import copy
import pandas as pd
from typing import Dict, Any, Optional, Tuple


class SettingsManager:
    """
    Manages loading of warehouse configurations and barcode resolution.
    Allows extending the Master Data with local overrides.
    """

    def __init__(
        self, config_file: str, barcode_db_file: str = None, excel_db_path: str = None
    ):
        """
        Args:
            config_file: Path to the warehouse specific config (e.g. config_retail.json)
            barcode_db_file: Path to the barcode mapping database
            excel_db_path: Path to the Excel database with variant details (PESO TARA, etc.)
        """
        self.config_data = self._load_json(config_file) or {}
        self.barcode_data = self._load_json(barcode_db_file) if barcode_db_file else {}

        # Ensure structure
        self.overrides = self.config_data.get("product_overrides", {})
        self.settings = self.config_data.get("print_settings", {})

        self.barcode_map = self.barcode_data.get("mappings", {})
        self.variant_info = self.barcode_data.get("variants", {})

        self.sql_engine = None
        try:
            from database_client import DatabaseClient

            client = DatabaseClient()
            if client.connect():
                self.sql_engine = client.get_sql_engine()
        except Exception:
            pass

        # Load from SQL if available to override files
        if self.sql_engine:
            try:
                import pandas as pd

                df_vars = pd.read_sql(
                    "SELECT * FROM product_variants", con=self.sql_engine
                )
                for _, row in df_vars.iterrows():
                    prefix = str(row["prefix_variant"])
                    self.barcode_map[prefix] = str(row["product_id"])
                    self.variant_info[prefix] = {
                        "name_suffix": str(row.get("description", "")),
                        "unit": str(row.get("uom", "")),
                        "multiplier": float(row.get("pack_size", 1.0)),
                    }
                print(f"✅ Loaded {len(df_vars)} barcode variants from SQL.")
            except Exception as e:
                print(f"⚠️ Error loading variants from SQL: {e}")

        # Load Peso Tara and other variant data from Excel
        self.peso_tara_map = {}  # Maps CODIGO VARIANTE -> PESO TARA
        self.peso_neto_map = {}  # Maps (Father ID, PESO NETO) -> PESO TARA
        if excel_db_path and os.path.exists(excel_db_path):
            self._load_peso_tara_from_excel(excel_db_path)

    def _load_json(self, path: str) -> Optional[Dict]:
        if not path or not os.path.exists(path):
            print(f"Warning: Config file not found {path}")
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading JSON {path}: {e}")
            return None

    def _load_peso_tara_from_excel(self, excel_path: str):
        """Load Peso Tara data from Excel file and populate peso_tara_map and peso_neto_map"""
        try:
            df = pd.read_excel(excel_path)
            for _, row in df.iterrows():
                # Map by CODIGO VARIANTE
                codigo_variante = str(row.get("CODIGO VARIANTE", "")).strip()
                peso_tara = row.get("PESO TARA", 0)
                if (
                    codigo_variante
                    and codigo_variante != "nan"
                    and pd.notna(codigo_variante)
                ):
                    self.peso_tara_map[codigo_variante] = (
                        float(peso_tara) if pd.notna(peso_tara) else 0.0
                    )

                # Also map by (Father ID, PESO NETO) for SAP imports
                codigo_interno = str(row.get("Codigo interno ", "")).strip()
                peso_neto = row.get("PESO NETO", None)
                if codigo_interno and pd.notna(peso_neto) and pd.notna(peso_tara):
                    key = (codigo_interno, float(peso_neto))
                    self.peso_neto_map[key] = float(peso_tara)

            print(
                f"Loaded {len(self.peso_tara_map)} variants with Peso Tara data from Excel"
            )
            print(f"Created {len(self.peso_neto_map)} Father ID + Peso Neto mappings")
        except Exception as e:
            print(f"Error loading Peso Tara from Excel {excel_path}: {e}")

    def get_peso_tara(self, variant_id: str) -> float:
        """Get Peso Tara for a given variant code"""
        return self.peso_tara_map.get(variant_id, 0.0)

    def get_peso_tara_by_quantity(self, father_id: str, quantity: float) -> float:
        """Get Peso Tara for a given Father ID and quantity (PESO NETO)"""
        key = (father_id, float(quantity))
        return self.peso_neto_map.get(key, 0.0)

    def resolve_barcode(self, scanned_code: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Resolves a scanned code to (Father_ID, Variant_Code / Son_Barcode).

        Returns:
            (father_id, variant_id_or_none)
        """
        scanned_code = str(scanned_code).strip()

        # 1. Is it a mapped Son Barcode?
        if scanned_code in self.barcode_map:
            father_id = self.barcode_map[scanned_code]
            return father_id, scanned_code

        # 2. Assume it's a Father ID (Internal Code) directly
        # Verification would happen against the Master DB, but here we just pass it back
        return scanned_code, None

    def apply_overrides(
        self, product_data: Dict[str, Any], father_id: str, variant_id: str = None
    ) -> Dict[str, Any]:
        """
        Merges master product data with:
        1. Father-level overrides (from config_retail.json)
        2. Variant-level info (from barcode database or config)
        """
        if not product_data:
            return product_data

        merged = copy.deepcopy(product_data)

        # --- Level 1: Father Overrides (Warehouse Config) ---
        if father_id in self.overrides:
            ov = self.overrides[father_id]
            print(f"   [Config] Applying overrides for {father_id}")

            if "signal_word_override" in ov:
                merged["signal_word"] = ov["signal_word_override"]

            if "add_h_statements" in ov:
                merged["h_statements"].extend(ov["add_h_statements"])

            if "custom_text" in ov:
                # We can inject this into the name or a new field
                merged["name"] = f"{merged['name']} ({ov['custom_text']})"

        # --- Level 2: Variant Info (Son Barcode) ---
        if variant_id and variant_id in self.variant_info:
            v_info = self.variant_info[variant_id]
            print(f"   [Scanner] Applying variant info: {v_info.get('description')}")

            # Append pack size to name
            if "pack_size" in v_info:
                merged["name"] = f"{merged['name']} - {v_info['pack_size']}"

        # Add Peso Tara to merged data
        # First try to get variant_code from variant_info, otherwise use variant_id directly
        if variant_id:
            variant_code = None
            if variant_id in self.variant_info:
                variant_code = self.variant_info[variant_id].get("variant_code")

            # If no variant_code mapping, try variant_id directly
            peso_tara = self.get_peso_tara(variant_code if variant_code else variant_id)
            merged["peso_tara"] = peso_tara
        else:
            # No variant_id, initialize to 0 (will be set by quantity-based lookup in GUI)
            merged["peso_tara"] = 0.0

        return merged
