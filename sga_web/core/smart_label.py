import pandas as pd
import re
import os
import glob
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from functools import lru_cache


def get_base_dir():
    """Get the base directory of the application"""
    return os.path.dirname(os.path.abspath(__file__))


class SmartLabelManager:
    """
    Manages the resolution of GHS codes to text for sticker printing.
    Implements fallback logic for dirty data (typos, composite codes, raw text).

    Now supports automatic database discovery:
    - Tries database_client connection first (network server)
    - Falls back to local unified_db
    - Uses db_connection_config.json if present
    """

    def __init__(self, data_dir: str = None):
        self.connection_mode = None
        self.sql_engine = None

        # Pictogram Image Mapping
        self.picto_map = {
            "Exclamación": "exclamacion.png",
            "Corrosión": "corrosion.png",
            "Peligro para la salud": "peligro_salud.png",
            "Calavera": "calavera.png",
            "Llama": "llama.png",
            "Ambiente": "ambiente.png",
            "Llama sobre círculo": "llama_circulo.png",
            "Bomba explotando": "bomba.png",
            "Cilindro de gas": "cilindro_gas.png",
        }

        # Auto-detect database path if not provided
        if data_dir is None:
            data_dir = self._auto_detect_database_path()

        self.data_dir = data_dir
        self.df_products = None
        self.h_defs = {}
        self.p_defs = {}
        self.last_save_error = None
        self.last_save_path = None
        self._load_data()

    def get_last_save_status(self) -> Dict[str, Any]:
        """Return latest save status for UI/API diagnostics."""
        return {
            "ok": self.last_save_error is None,
            "error": self.last_save_error,
            "path": self.last_save_path,
            "mode": self.connection_mode,
        }

    def _mark_local_pending_sync(self, changed_files: List[str]):
        """Create/update marker so fallback writes are synced after reconnect."""
        if self.connection_mode != "local":
            return

        marker_path = os.path.join(self.data_dir, ".pending_sync.json")
        payload = {
            "updated_at": datetime.now().isoformat(),
            "source_path": self.data_dir,
            "changed_files": sorted(set(changed_files)),
        }

        # Merge with existing marker to preserve previous pending files.
        if os.path.exists(marker_path):
            try:
                with open(marker_path, "r", encoding="utf-8") as f:
                    current = json.load(f)
                existing = current.get("changed_files", [])
                payload["changed_files"] = sorted(
                    set(payload["changed_files"] + existing)
                )
            except Exception:
                pass

        try:
            with open(marker_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Warning: could not write pending sync marker: {e}")

    def _auto_detect_database_path(self) -> str:
        """
        Automatically detect database path using connection system.
        Priority:
        1. Database client connection (network server or SQL)
        2. db_connection_config.json (explicit config)
        3. Local unified_db directory
        """
        base_dir = get_base_dir()

        # Try database client connection
        try:
            from database_client import DatabaseClient

            client = DatabaseClient()
            if client.connect():
                self.sql_engine = client.get_sql_engine()
                db_path = client.get_database_path()
                self.connection_mode = client.get_connection_mode()
                print(f"✅ Conectado a base de datos ({self.connection_mode})")
                client.disconnect()
                return db_path or os.path.join(base_dir, "unified_db")
        except ImportError:
            pass
        except Exception as e:
            print(f"⚠️  Error en conexión automática: {e}")

        # Try explicit config file
        config_file = os.path.join(base_dir, "db_connection_config.json")
        if os.path.exists(config_file):
            try:
                with open(config_file, "r") as f:
                    config = json.load(f)
                    db_path = config.get("database_path")
                    if db_path and os.path.exists(db_path):
                        self.connection_mode = "configured"
                        print(f"✅ Usando base de datos configurada: {db_path}")
                        return db_path
            except Exception as e:
                print(f"⚠️  Error leyendo config: {e}")

        # Fallback to local unified_db
        unified_db = os.path.join(base_dir, "unified_db")
        if os.path.exists(unified_db):
            self.connection_mode = "local"
            print(f"✅ Usando base de datos local: {unified_db}")
            return unified_db

        # Final fallback to original_data (legacy)
        original_data = os.path.join(base_dir, "original_data")
        if os.path.exists(original_data):
            self.connection_mode = "legacy"
            print(f"⚠️  Usando base de datos legacy: {original_data}")
            return original_data

        # No database found
        raise FileNotFoundError(
            "No se encontró base de datos. Opciones:\n"
            "1. Ejecute: python database_server.py --setup-server (servidor)\n"
            "2. Copie db_client_config.json y ejecute: python auto_deploy.py --install (cliente)\n"
            "3. Ejecute: python unify_for_sga.py (local)"
        )

    def _load_data(self):
        """Loads and indexes the CSV data or SQL data. If SQL, skips downloading entire tables to memory."""
        # Check if SQL connection is available
        if getattr(self, "sql_engine", None) is not None:
            try:
                self.is_normalized = True

                # We load only the dictionaries for H and P statements,
                # because they are small and frequently accessed for definition lookups.
                df_h = pd.read_sql("SELECT * FROM h_statements", con=self.sql_engine)
                df_h["h_code"] = df_h["h_code"].astype(str)
                h_text_col = (
                    "text_es" if "text_es" in df_h.columns else "description_es"
                )
                self.h_defs = self._create_lookup_dict(df_h, "h_code", h_text_col)

                df_p = pd.read_sql("SELECT * FROM p_statements", con=self.sql_engine)
                df_p["p_code"] = df_p["p_code"].astype(str)
                p_text_col = (
                    "text_es" if "text_es" in df_p.columns else "description_es"
                )
                self.p_defs = self._create_lookup_dict(df_p, "p_code", p_text_col)

                # FOR WEB COMPATIBILITY: Preload full catalogs into memory instead of being strictly lazy
                # Products browser in sga_web relies on these DataFrames
                self.df_products = pd.read_sql(
                    "SELECT * FROM products_master", con=self.sql_engine
                )
                # Normalize types to match expected CSV types
                for col in ["product_id", "cas_number"]:
                    if col in self.df_products.columns:
                        self.df_products[col] = self.df_products[col].astype(str)

                try:
                    self.df_product_pictograms = pd.read_sql(
                        "SELECT * FROM product_pictograms", con=self.sql_engine
                    )
                except Exception:
                    self.df_product_pictograms = None

                try:
                    self.df_product_hazards = pd.read_sql(
                        "SELECT * FROM product_hazards", con=self.sql_engine
                    )
                except Exception:
                    self.df_product_hazards = None

                try:
                    self.df_product_precautions = pd.read_sql(
                        "SELECT * FROM product_precautions", con=self.sql_engine
                    )
                except Exception:
                    self.df_product_precautions = None

                print(
                    f"Connected to SQL: loaded {len(self.h_defs)} H-defs, {len(self.p_defs)} P-defs, {len(self.df_products)} products."
                )
                return
            except Exception as e:
                print(f"⚠️  Error loading data from SQL, falling back to CSV: {e}")
                import traceback

                traceback.print_exc()

        # Helper to find files
        def get_file(pattern):
            files = glob.glob(os.path.join(self.data_dir, f"*{pattern}*.csv"))
            return files[0] if files else None

        # Try new normalized structure first (from unify_for_sga.py)
        products_master_path = os.path.join(self.data_dir, "products_master.csv")
        h_statements_path = os.path.join(self.data_dir, "h_statements.csv")
        p_statements_path = os.path.join(self.data_dir, "p_statements.csv")

        # Check if new structure exists
        if os.path.exists(products_master_path) and os.path.exists(h_statements_path):
            # Load from new normalized structure
            self.df_products = pd.read_csv(
                products_master_path, dtype={"product_id": str}
            )
            self.is_normalized = True  # Flag to indicate normalized format

            # Load related tables for normalized structure
            product_hazards_path = os.path.join(self.data_dir, "product_hazards.csv")
            product_precautions_path = os.path.join(
                self.data_dir, "product_precautions.csv"
            )
            product_pictograms_path = os.path.join(
                self.data_dir, "product_pictograms.csv"
            )

            if os.path.exists(product_hazards_path):
                self.df_product_hazards = pd.read_csv(
                    product_hazards_path, dtype={"product_id": str, "h_code": str}
                )
            else:
                self.df_product_hazards = pd.DataFrame(columns=["product_id", "h_code"])

            if os.path.exists(product_precautions_path):
                self.df_product_precautions = pd.read_csv(
                    product_precautions_path, dtype={"product_id": str, "p_code": str}
                )
            else:
                self.df_product_precautions = pd.DataFrame(
                    columns=["product_id", "p_code"]
                )

            if os.path.exists(product_pictograms_path):
                self.df_product_pictograms = pd.read_csv(
                    product_pictograms_path,
                    dtype={"product_id": str, "pictogram_id": str},
                )
            else:
                self.df_product_pictograms = pd.DataFrame(
                    columns=["product_id", "pictogram_id"]
                )

            # Load H Definitions - handle both column naming conventions
            df_h = pd.read_csv(h_statements_path, dtype={"h_code": str})
            h_text_col = "text_es" if "text_es" in df_h.columns else "description_es"
            self.h_defs = self._create_lookup_dict(df_h, "h_code", h_text_col)

            # Load P Definitions - handle both column naming conventions
            df_p = pd.read_csv(p_statements_path, dtype={"p_code": str})
            p_text_col = "text_es" if "text_es" in df_p.columns else "description_es"
            self.p_defs = self._create_lookup_dict(df_p, "p_code", p_text_col)

            print(
                f"Loaded {len(self.df_products)} products (Normalized), {len(self.h_defs)} H-defs, {len(self.p_defs)} P-defs."
            )

        else:
            # Fallback to legacy structure
            self.is_normalized = False
            self.df_product_hazards = None
            self.df_product_precautions = None
            self.df_product_pictograms = None

            main_path = os.path.join(self.data_dir, "Unified_GHS_Database.csv")
            h_path = get_file("Significados de H")
            p_path = get_file("Significados de P")

            if not os.path.exists(main_path):
                raise FileNotFoundError(
                    f"Base de datos no encontrada en {self.data_dir}\n"
                    f"Ejecute: python unify_for_sga.py"
                )

            # Load Products (legacy format)
            self.df_products = pd.read_csv(
                main_path,
                dtype={
                    "Codigo interno": str,
                    "H-Statements": str,
                    "Consejos (Frases P)": str,
                },
            )

            # Load H Definitions
            df_h = pd.read_csv(h_path, dtype={"H": str})
            self.h_defs = self._create_lookup_dict(df_h, "H", "Significado")

            # Load P Definitions
            df_p = pd.read_csv(p_path, dtype={"P": str})
            self.p_defs = self._create_lookup_dict(df_p, "P", "Significado")

            print(
                f"Loaded {len(self.df_products)} products (Legacy), {len(self.h_defs)} H-defs, {len(self.p_defs)} P-defs."
            )

    def reload(self):
        """[P1-04] Reload all CSV data from disk.  Call after external changes to unified_db/."""
        self._load_data()

    def get_pictogram_path(self, picto_name: str) -> Optional[str]:
        """Returns the absolute path to the pictogram image file."""
        filename = self.picto_map.get(picto_name)
        if not filename:
            return None

        # Assume assets is a sibling folder to the data folder
        # data_dir = .../Base_datos/original_data
        # assets   = .../Base_datos/assets
        assets_dir = os.path.join(
            os.path.dirname(self.data_dir.rstrip(os.sep)), "assets", "pictograms"
        )
        full_path = os.path.join(assets_dir, filename)

        if os.path.exists(full_path):
            return full_path

        # Fallback: use absolute path from resource_path module
        try:
            from resource_path import PICTOGRAMS_DIR

            fallback_path = os.path.join(PICTOGRAMS_DIR, filename)
            if os.path.exists(fallback_path):
                return fallback_path
        except ImportError:
            pass

        return None

    def _create_lookup_dict(
        self, df: pd.DataFrame, key_col: str, val_col: str
    ) -> Dict[str, str]:
        """Creates a normalized lookup dictionary."""
        lookup = {}
        for _, row in df.iterrows():
            k = str(row[key_col]).strip()
            v = str(row[val_col]).strip()
            lookup[k] = v

            # Add normalized key (no spaces) for fuzzy matching if key contains spaces
            if " " in k:
                lookup[k.replace(" ", "")] = v
        return lookup

    def normalize_code(self, code: str) -> str:
        """Cleans a code string (removes trailing dots, excessive whitespace)."""
        if not code:
            return ""

        # Remove trailing punctuation often found in typos like "H336."
        clean = code.strip().rstrip(".,;")
        return clean

    @lru_cache(maxsize=1024)
    def resolve_code(self, code: str, code_type: str) -> str:
        """
        Smart resolution logic.

        Args:
            code: The code string (e.g., "H302", "P301+P310", or "Instructions...")
            code_type: 'H' or 'P'

        Returns:
            The resolved text definition.
        """
        original_code = code.strip()
        if not original_code:
            return ""

        # 1. Exact Match
        defs = self.h_defs if code_type == "H" else self.p_defs
        if original_code in defs:
            return defs[original_code]

        # 2. Normalized Match (handling "H 301" vs "H301" or typo removal)
        normalized = self.normalize_code(original_code)
        if normalized in defs:
            return defs[normalized]

        # 3. Space-stripped Match (handling "P 301" vs "P301")
        space_stripped = normalized.replace(" ", "")
        if space_stripped in defs:
            return defs[space_stripped]

        # 4. Heuristic: Is it a code or raw text?
        # Codes usually are short (< 15 chars) and match patterns like H\d+ or P\d+
        # If it's long, assume it's raw text intended to be printed directly.
        if len(original_code) > 20:
            return original_code

        # 5. Composite Code Split Heuristic (e.g., H315 H320 -> Split and join definitions)
        # Check if it looks like multiple codes separated by space/plus but missing commas
        # Regex: matches H or P followed by digits
        matches = re.findall(r"([HP]\d+)", original_code.replace(" ", ""))
        if matches and len(matches) > 1:
            # We found multiple codes glued together (e.g. H315H320 or H315 H320)
            # Try to look them up individually
            resolved_parts = []
            for part in matches:
                part_text = self.resolve_code(part, code_type)
                if (
                    part_text == part
                ):  # Only returned the code itself, meaning not found
                    # If one part fails, maybe we shouldn't decompose?
                    # Actually, showing Code is better than nothing.
                    pass
                resolved_parts.append(f"[{part}]: {part_text}")

            return " ".join(resolved_parts)

        # 6. Fallback: Return the code itself
        return original_code

    def save_products(self) -> bool:
        """Saves current data back to CSV(s)."""
        if self.df_products is None:
            return False

        if self.is_normalized:
            return self._save_products_normalized()
        else:
            return self._save_products_legacy()

    def _save_products_legacy(self) -> bool:
        main_path = os.path.join(self.data_dir, "Unified_GHS_Database.csv")
        self.last_save_path = main_path
        self.last_save_error = None
        try:
            # Create a backup before saving
            backup_path = main_path + ".bak"
            if os.path.exists(main_path):
                import shutil

                shutil.copy2(main_path, backup_path)

            self.df_products.to_csv(main_path, index=False)
            self._mark_local_pending_sync(["Unified_GHS_Database.csv"])
            print(f"Details saved to {main_path}")
            return True
        except Exception as e:
            self.last_save_error = str(e)
            print(f"Error saving database: {e}")
            return False

    def _save_products_normalized(self) -> bool:
        if getattr(self, "sql_engine", None) is not None:
            # Real-time SQL operations bypass bulk CSV saves
            return True

        self.last_save_path = self.data_dir
        self.last_save_error = None
        try:
            import shutil

            saved_files = []

            # 1. Save Products Master (drop rows with empty product_id)
            master_path = os.path.join(self.data_dir, "products_master.csv")
            shutil.copy2(master_path, master_path + ".bak")
            # Clean ghost rows before saving
            clean_df = self.df_products[
                self.df_products["product_id"].astype(str).str.strip().ne("")
                & self.df_products["product_id"].notna()
            ]
            clean_df.to_csv(master_path, index=False)
            saved_files.append("products_master.csv")
            self.df_products = clean_df.reset_index(drop=True)

            # 2. Save Hazards
            hazards_path = os.path.join(self.data_dir, "product_hazards.csv")
            if self.df_product_hazards is not None:
                if os.path.exists(hazards_path):
                    shutil.copy2(hazards_path, hazards_path + ".bak")
                self.df_product_hazards.to_csv(hazards_path, index=False)
                saved_files.append("product_hazards.csv")

            # 3. Save Precautions
            precautions_path = os.path.join(self.data_dir, "product_precautions.csv")
            if self.df_product_precautions is not None:
                if os.path.exists(precautions_path):
                    shutil.copy2(precautions_path, precautions_path + ".bak")
                self.df_product_precautions.to_csv(precautions_path, index=False)
                saved_files.append("product_precautions.csv")

            # 4. Save Pictograms
            picto_path = os.path.join(self.data_dir, "product_pictograms.csv")
            if self.df_product_pictograms is not None:
                if os.path.exists(picto_path):
                    shutil.copy2(picto_path, picto_path + ".bak")
                self.df_product_pictograms.to_csv(picto_path, index=False)
                saved_files.append("product_pictograms.csv")

            # ------------- NEW SQL SYNC ----------------
            if getattr(self, "sql_engine", None) is not None:
                pass  # Sync is now real-time on update/add/delete

            print("Normalized database saved successfully.")
            return True
        except Exception as e:
            self.last_save_error = str(e)
            print(f"Error saving normalized database: {e}")
            return False

    def update_product(self, product_id: str, data: Dict[str, Any]) -> bool:
        """
        Updates a product with the given data dict.
        Handles mapping from frontend keys to database columns.
        """
        try:
            # Extract common fields
            chemical_name = data.get("Chemical Name")
            cas_number = data.get("CAS Number")
            signal_word = data.get("Signal Word")
            emergency_phone = data.get("Emergencia")

            # H/P Codes are passed as comma-separated strings
            h_raw = data.get("H-Statements", "")
            p_raw = data.get("Consejos (Frases P)", "")

            # Parse H/P codes into lists
            h_codes = [c.strip() for c in h_raw.split(",") if c.strip()]
            p_codes = [c.strip() for c in p_raw.split(",") if c.strip()]

            # Identify pictograms
            pictograms = []
            possible_pictograms = [
                "Exclamación",
                "Corrosión",
                "Peligro para la salud",
                "Calavera",
                "Llama",
                "Ambiente",
                "Llama sobre círculo",
                "Bomba explotando",
                "Cilindro de gas",
            ]
            for pic in possible_pictograms:
                if data.get(pic) == "X":
                    pictograms.append(pic)

            if self.is_normalized:
                return self._update_product_normalized(
                    product_id,
                    chemical_name,
                    cas_number,
                    signal_word,
                    emergency_phone,
                    h_codes,
                    p_codes,
                    pictograms,
                )
            else:
                return self._update_product_legacy(
                    product_id,
                    chemical_name,
                    cas_number,
                    signal_word,
                    emergency_phone,
                    h_raw,
                    p_raw,
                    pictograms,
                )

        except Exception as e:
            print(f"Error updating product {product_id}: {e}")
            import traceback

            traceback.print_exc()
            return False

    def _update_product_normalized(
        self, product_id, name, cas, signal, emergency, h_codes, p_codes, pictograms
    ):
        name_to_id_map = {
            "Bomba explotando": "GHS01",
            "Llama": "GHS02",
            "Llama sobre círculo": "GHS03",
            "Cilindro de gas": "GHS04",
            "Corrosión": "GHS05",
            "Calavera": "GHS06",
            "Exclamación": "GHS07",
            "Peligro para la salud": "GHS08",
            "Ambiente": "GHS09",
        }
        pic_ids = [name_to_id_map.get(p) for p in pictograms if p in name_to_id_map]

        if getattr(self, "sql_engine", None) is not None:
            from sqlalchemy import text

            try:
                with self.sql_engine.begin() as conn:
                    # Update Master
                    conn.execute(
                        text(
                            "UPDATE products_master SET chemical_name=:name, cas_number=:cas, signal_word=:signal, emergency_phone=:emergency WHERE product_id=:pid"
                        ),
                        {
                            "name": name or "",
                            "cas": cas or "",
                            "signal": signal or "",
                            "emergency": emergency or "",
                            "pid": str(product_id),
                        },
                    )
                    # Recreate relations via delete + insert
                    conn.execute(
                        text("DELETE FROM product_hazards WHERE product_id=:pid"),
                        {"pid": str(product_id)},
                    )
                    for hc in h_codes:
                        conn.execute(
                            text(
                                "INSERT INTO product_hazards (product_id, h_code) VALUES (:pid, :code)"
                            ),
                            {"pid": str(product_id), "code": str(hc)},
                        )

                    conn.execute(
                        text("DELETE FROM product_precautions WHERE product_id=:pid"),
                        {"pid": str(product_id)},
                    )
                    for pc in p_codes:
                        conn.execute(
                            text(
                                "INSERT INTO product_precautions (product_id, p_code) VALUES (:pid, :code)"
                            ),
                            {"pid": str(product_id), "code": str(pc)},
                        )

                    conn.execute(
                        text("DELETE FROM product_pictograms WHERE product_id=:pid"),
                        {"pid": str(product_id)},
                    )
                    for pic in pic_ids:
                        conn.execute(
                            text(
                                "INSERT INTO product_pictograms (product_id, pictogram_id) VALUES (:pid, :code)"
                            ),
                            {"pid": str(product_id), "code": str(pic)},
                        )
                return True
            except Exception as e:
                print(f"SQL Update Error: {e}")
                return False

        # --- CSV Fallback Data Mutate ---
        if self.df_products is None:
            return False
        # 1. Update Master Table
        mask = self.df_products["product_id"].astype(str) == str(product_id)
        if not mask.any():
            return False

        idx = self.df_products[mask].index[0]
        if name:
            self.df_products.loc[idx, "chemical_name"] = name
        if cas:
            self.df_products.loc[idx, "cas_number"] = cas
        if signal:
            self.df_products.loc[idx, "signal_word"] = signal
        if emergency:
            self.df_products.loc[idx, "emergency_phone"] = emergency

        # 2. Update Hazards
        # Remove old
        self.df_product_hazards = self.df_product_hazards[
            self.df_product_hazards["product_id"].astype(str) != str(product_id)
        ]
        # Add new
        new_hazards = pd.DataFrame(
            {"product_id": [str(product_id)] * len(h_codes), "h_code": h_codes}
        )
        self.df_product_hazards = pd.concat(
            [self.df_product_hazards, new_hazards], ignore_index=True
        )

        # 3. Update Precautions
        self.df_product_precautions = self.df_product_precautions[
            self.df_product_precautions["product_id"].astype(str) != str(product_id)
        ]
        new_precautions = pd.DataFrame(
            {"product_id": [str(product_id)] * len(p_codes), "p_code": p_codes}
        )
        self.df_product_precautions = pd.concat(
            [self.df_product_precautions, new_precautions], ignore_index=True
        )

        # 4. Update Pictograms
        new_pictograms = pd.DataFrame(
            {"product_id": [str(product_id)] * len(pic_ids), "pictogram_id": pic_ids}
        )
        self.df_product_pictograms = pd.concat(
            [self.df_product_pictograms, new_pictograms], ignore_index=True
        )

        return self.save_products()

    def _update_product_legacy(
        self, code, name, cas, signal, emergency, h_raw, p_raw, pictograms
    ):
        idx = self.df_products[
            self.df_products["Codigo interno"].astype(str) == str(code)
        ].index
        if len(idx) == 0:
            return False

        i = idx[0]
        if name:
            self.df_products.loc[i, "Chemical Name"] = name
        if cas:
            self.df_products.loc[i, "CAS Number"] = cas
        if signal:
            self.df_products.loc[i, "Signal Word"] = signal
        if emergency:
            self.df_products.loc[i, "Emergencia"] = emergency

        self.df_products.loc[i, "H-Statements"] = h_raw
        self.df_products.loc[i, "Consejos (Frases P)"] = p_raw

        # Reset pictograms
        possible_cols = [
            "Exclamación",
            "Corrosión",
            "Peligro para la salud",
            "Calavera",
            "Llama",
            "Ambiente",
            "Llama sobre círculo",
            "Bomba explotando",
            "Cilindro de gas",
        ]

        for col in possible_cols:
            full_col_name = f"{col} (PICTOGRAMA )"
            if full_col_name in self.df_products.columns:
                self.df_products.loc[i, full_col_name] = (
                    "X" if col in pictograms else ""
                )
            elif col in self.df_products.columns:
                self.df_products.loc[i, col] = "X" if col in pictograms else ""

        return self.save_products()

    def add_product(self, product_data: Dict[str, Any]) -> bool:
        """Adds a new product to the dataframe and saves it."""
        try:
            # Extract common fields
            code = product_data.get("Codigo interno", "").strip()
            name = product_data.get("Chemical Name", "").strip()
            cas = product_data.get("CAS Number", "").strip()
            signal = product_data.get("Signal Word", "").strip()
            emergency = product_data.get("Emergencia", "").strip()

            # H/P Codes are passed as comma-separated strings
            h_raw = product_data.get("H-Statements", "")
            p_raw = product_data.get("Consejos (Frases P)", "")

            # Parse H/P codes into lists
            h_codes = [c.strip() for c in h_raw.split(",") if c.strip()]
            p_codes = [c.strip() for c in p_raw.split(",") if c.strip()]

            # Identify pictograms
            pictograms = []
            possible_pictograms = [
                "Exclamación",
                "Corrosión",
                "Peligro para la salud",
                "Calavera",
                "Llama",
                "Ambiente",
                "Llama sobre círculo",
                "Bomba explotando",
                "Cilindro de gas",
            ]
            for pic in possible_pictograms:
                if product_data.get(pic) == "X":
                    pictograms.append(pic)

            if self.is_normalized:
                return self._add_product_normalized(
                    code, name, cas, signal, emergency, h_codes, p_codes, pictograms
                )
            else:
                return self._add_product_legacy(product_data)

        except Exception as e:
            print(f"Error adding product: {e}")
            import traceback

            traceback.print_exc()
            return False

    def _add_product_normalized(
        self, code, name, cas, signal, emergency, h_codes, p_codes, pictograms
    ):
        name_to_id_map = {
            "Bomba explotando": "GHS01",
            "Llama": "GHS02",
            "Llama sobre círculo": "GHS03",
            "Cilindro de gas": "GHS04",
            "Corrosión": "GHS05",
            "Calavera": "GHS06",
            "Exclamación": "GHS07",
            "Peligro para la salud": "GHS08",
            "Ambiente": "GHS09",
        }
        pic_ids = [name_to_id_map.get(p) for p in pictograms if p in name_to_id_map]
        from datetime import datetime

        last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if getattr(self, "sql_engine", None) is not None:
            from sqlalchemy import text

            try:
                with self.sql_engine.begin() as conn:
                    # 1. Add to Master Table (check if exists first if needed, though PK will throw error)
                    conn.execute(
                        text(
                            "INSERT INTO products_master (product_id, chemical_name, cas_number, signal_word, emergency_phone, is_active, last_updated) VALUES (:pid, :name, :cas, :signal, :emergency, 'Y', :last_up)"
                        ),
                        {
                            "pid": str(code),
                            "name": name or "",
                            "cas": cas or "",
                            "signal": signal or "",
                            "emergency": emergency or "",
                            "last_up": last_updated,
                        },
                    )

                    # 2. Add Hazards
                    for hc in h_codes:
                        conn.execute(
                            text(
                                "INSERT INTO product_hazards (product_id, h_code) VALUES (:pid, :code)"
                            ),
                            {"pid": str(code), "code": str(hc)},
                        )

                    # 3. Add Precautions
                    for pc in p_codes:
                        conn.execute(
                            text(
                                "INSERT INTO product_precautions (product_id, p_code) VALUES (:pid, :code)"
                            ),
                            {"pid": str(code), "code": str(pc)},
                        )

                    # 4. Add Pictograms
                    for pic in pic_ids:
                        conn.execute(
                            text(
                                "INSERT INTO product_pictograms (product_id, pictogram_id) VALUES (:pid, :code)"
                            ),
                            {"pid": str(code), "code": str(pic)},
                        )
                return True
            except Exception as e:
                print(f"SQL Add Error: {e}")
                return False

        # --- CSV Fallback Mutate ---
        if self.df_products is None:
            return False

        # 1. Add to Master Table
        # Check if exists
        if code in self.df_products["product_id"].astype(str).values:
            print(f"Error: Product {code} already exists.")
            return False

        new_row = pd.DataFrame(
            [
                {
                    "product_id": code,
                    "chemical_name": name,
                    "cas_number": cas,
                    "signal_word": signal,
                    "emergency_phone": emergency,
                    "is_active": "Y",
                    "last_updated": last_updated,
                }
            ]
        )

        self.df_products = pd.concat([self.df_products, new_row], ignore_index=True)

        # 2. Add Hazards
        if h_codes:
            new_hazards = pd.DataFrame(
                {"product_id": [str(code)] * len(h_codes), "h_code": h_codes}
            )
            if self.df_product_hazards is None:
                self.df_product_hazards = new_hazards
            else:
                self.df_product_hazards = pd.concat(
                    [self.df_product_hazards, new_hazards], ignore_index=True
                )

        # 3. Add Precautions
        if p_codes:
            new_precautions = pd.DataFrame(
                {"product_id": [str(code)] * len(p_codes), "p_code": p_codes}
            )
            if self.df_product_precautions is None:
                self.df_product_precautions = new_precautions
            else:
                self.df_product_precautions = pd.concat(
                    [self.df_product_precautions, new_precautions], ignore_index=True
                )

        # 4. Add Pictograms
        # Map names to GHS IDs (reverse mapping needed)
        name_to_id_map = {
            "Bomba explotando": "GHS01",
            "Llama": "GHS02",
            "Llama sobre círculo": "GHS03",
            "Cilindro de gas": "GHS04",
            "Corrosión": "GHS05",
            "Calavera": "GHS06",
            "Exclamación": "GHS07",
            "Peligro para la salud": "GHS08",
            "Ambiente": "GHS09",
        }

        pic_ids = [name_to_id_map.get(p) for p in pictograms if p in name_to_id_map]

        if pic_ids:
            new_pictograms = pd.DataFrame(
                {"product_id": [str(code)] * len(pic_ids), "pictogram_id": pic_ids}
            )
            if self.df_product_pictograms is None:
                self.df_product_pictograms = new_pictograms
            else:
                self.df_product_pictograms = pd.concat(
                    [self.df_product_pictograms, new_pictograms], ignore_index=True
                )

        print(
            f"DEBUG: Added normalized product {code}. Master rows: {len(self.df_products)}"
        )
        return self.save_products()

    def delete_product(self, product_id: str) -> bool:
        """Deletes a product and all its related data."""
        try:
            if self.is_normalized:
                return self._delete_product_normalized(product_id)
            else:
                return self._delete_product_legacy(product_id)
        except Exception as e:
            print(f"Error deleting product {product_id}: {e}")
            import traceback

            traceback.print_exc()
            return False

    def _delete_product_normalized(self, product_id: str) -> bool:
        """Delete product from normalized database."""
        if getattr(self, "sql_engine", None) is not None:
            from sqlalchemy import text

            try:
                with self.sql_engine.begin() as conn:
                    conn.execute(
                        text("DELETE FROM product_hazards WHERE product_id=:pid"),
                        {"pid": str(product_id)},
                    )
                    conn.execute(
                        text("DELETE FROM product_precautions WHERE product_id=:pid"),
                        {"pid": str(product_id)},
                    )
                    conn.execute(
                        text("DELETE FROM product_pictograms WHERE product_id=:pid"),
                        {"pid": str(product_id)},
                    )
                    conn.execute(
                        text("DELETE FROM products_master WHERE product_id=:pid"),
                        {"pid": str(product_id)},
                    )
                return True
            except Exception as e:
                print(f"SQL Delete Error: {e}")
                return False

        # --- CSV Fallback Mutate ---
        if self.df_products is None:
            return False

        mask = self.df_products["product_id"].astype(str) == str(product_id)
        if not mask.any():
            print(f"Product {product_id} not found for deletion.")
            return False

        # Remove from master table
        self.df_products = self.df_products[~mask].reset_index(drop=True)

        # Remove related hazards
        if self.df_product_hazards is not None and not self.df_product_hazards.empty:
            self.df_product_hazards = self.df_product_hazards[
                self.df_product_hazards["product_id"].astype(str) != str(product_id)
            ].reset_index(drop=True)

        # Remove related precautions
        if (
            self.df_product_precautions is not None
            and not self.df_product_precautions.empty
        ):
            self.df_product_precautions = self.df_product_precautions[
                self.df_product_precautions["product_id"].astype(str) != str(product_id)
            ].reset_index(drop=True)

        # Remove related pictograms
        if (
            self.df_product_pictograms is not None
            and not self.df_product_pictograms.empty
        ):
            self.df_product_pictograms = self.df_product_pictograms[
                self.df_product_pictograms["product_id"].astype(str) != str(product_id)
            ].reset_index(drop=True)

        print(
            f"DEBUG: Deleted normalized product {product_id}. Remaining: {len(self.df_products)}"
        )
        return self.save_products()

    def _delete_product_legacy(self, product_id: str) -> bool:
        """Delete product from legacy database."""
        mask = (
            self.df_products["Codigo interno"].astype(str).str.strip()
            == str(product_id).strip()
        )
        if not mask.any():
            print(f"Product {product_id} not found for deletion (legacy).")
            return False

        self.df_products = self.df_products[~mask].reset_index(drop=True)
        print(
            f"DEBUG: Deleted legacy product {product_id}. Remaining: {len(self.df_products)}"
        )
        return self.save_products()

    def _add_product_legacy(self, product_data):
        # Ensure we have a dataframe
        if self.df_products is None:
            pass

        # Align keys with dataframe columns to avoid mismatch warnings
        # Fill missing columns with default empty strings
        for col in self.df_products.columns:
            if col not in product_data:
                product_data[col] = ""

        # Create a new DataFrame for the new row
        new_row = pd.DataFrame([product_data])

        # Concatenate
        self.df_products = pd.concat([self.df_products, new_row], ignore_index=True)
        print(f"DEBUG: Added legacy product. Total rows: {len(self.df_products)}")
        return self.save_products()

    def get_product_data(self, keyword_or_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves full label data for a product by internal code or name.
        Supports both normalized and legacy database formats.
        """
        if self.is_normalized:
            return self._get_product_data_normalized(keyword_or_id)
        else:
            return self._get_product_data_legacy(keyword_or_id)

    def _get_product_data_normalized(
        self, keyword_or_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get product data from normalized database structure."""
        # --- SQL Lazy Loading Execution ---
        if getattr(self, "sql_engine", None) is not None:
            print(f"DEBUG: (SQL) Lazy searching for '{keyword_or_id}'")
            from sqlalchemy import text

            try:
                # 1. Fetch Main Product
                query_prod = text("""
                    SELECT * FROM products_master
                    WHERE product_id = :kw OR chemical_name LIKE :kw_like
                """)
                df_res = pd.read_sql(
                    query_prod,
                    con=self.sql_engine,
                    params={"kw": keyword_or_id, "kw_like": f"%{keyword_or_id}%"},
                )

                if df_res.empty:
                    return None

                row = df_res.iloc[0]
                product_id = str(row["product_id"])

                # 2. Fetch H-codes
                df_h = pd.read_sql(
                    text("SELECT h_code FROM product_hazards WHERE product_id = :pid"),
                    con=self.sql_engine,
                    params={"pid": product_id},
                )
                h_codes_list = (
                    df_h["h_code"].astype(str).tolist() if not df_h.empty else []
                )

                # 3. Fetch P-codes
                df_p = pd.read_sql(
                    text(
                        "SELECT p_code FROM product_precautions WHERE product_id = :pid"
                    ),
                    con=self.sql_engine,
                    params={"pid": product_id},
                )
                p_codes_list = (
                    df_p["p_code"].astype(str).tolist() if not df_p.empty else []
                )

                # 4. Fetch Pictograms
                df_pic = pd.read_sql(
                    text(
                        "SELECT pictogram_id FROM product_pictograms WHERE product_id = :pid"
                    ),
                    con=self.sql_engine,
                    params={"pid": product_id},
                )
                picto_ids = (
                    df_pic["pictogram_id"].astype(str).tolist()
                    if not df_pic.empty
                    else []
                )

            except Exception as e:
                print(f"Error querying SQL for product: {e}")
                return None

        # --- CSV Fallback Data Load ---
        else:
            print(
                f"DEBUG: (Normalized CSV) searching for '{keyword_or_id}' in {len(self.df_products)} rows"
            )
            mask = self.df_products["product_id"].astype(str) == keyword_or_id
            if "chemical_name" in self.df_products.columns:
                mask = mask | (
                    self.df_products["chemical_name"]
                    .astype(str)
                    .str.contains(keyword_or_id, case=False, na=False, regex=False)
                )

            results = self.df_products[mask]
            if results.empty:
                return None
            row = results.iloc[0]
            product_id = str(row["product_id"])

            h_codes_list = []
            if (
                self.df_product_hazards is not None
                and not self.df_product_hazards.empty
            ):
                h_mask = self.df_product_hazards["product_id"].astype(str) == product_id
                h_codes_list = self.df_product_hazards[h_mask]["h_code"].tolist()

            p_codes_list = []
            if (
                self.df_product_precautions is not None
                and not self.df_product_precautions.empty
            ):
                p_mask = (
                    self.df_product_precautions["product_id"].astype(str) == product_id
                )
                p_codes_list = self.df_product_precautions[p_mask]["p_code"].tolist()

            picto_ids = []
            if (
                self.df_product_pictograms is not None
                and not self.df_product_pictograms.empty
            ):
                picto_mask = (
                    self.df_product_pictograms["product_id"].astype(str) == product_id
                )
                picto_ids = self.df_product_pictograms[picto_mask][
                    "pictogram_id"
                ].tolist()

        # --- Shared Data Processing ---
        # Resolve H and P codes to text
        h_texts = [
            self.resolve_code(c, "H") for c in h_codes_list if c and str(c).strip()
        ]
        p_texts = [
            self.resolve_code(c, "P") for c in p_codes_list if c and str(c).strip()
        ]

        # Map GHS codes to pictogram names
        pictograms = []
        picto_name_map = {
            "GHS01": "Bomba explotando",
            "GHS02": "Llama",
            "GHS03": "Llama sobre círculo",
            "GHS04": "Cilindro de gas",
            "GHS05": "Corrosión",
            "GHS06": "Calavera",
            "GHS07": "Exclamación",
            "GHS08": "Peligro para la salud",
            "GHS09": "Ambiente",
        }
        for pid in picto_ids:
            if pid in picto_name_map:
                pictograms.append(picto_name_map[pid])

        return {
            "internal_code": product_id,
            "product_id": product_id,
            "name": row.get("chemical_name", ""),
            "product_name": row.get("chemical_name", ""),
            "cas": row.get("cas_number", ""),
            "signal_word": row.get("signal_word", ""),
            "emergency_phone": row.get("emergency_phone", "+52 800 123 4567"),
            "h_statements": h_texts,
            "p_statements": p_texts,
            "h_codes": h_codes_list,
            "p_codes": p_codes_list,
            "pictograms": pictograms,
        }

    def _get_product_data_legacy(self, keyword_or_id: str) -> Optional[Dict[str, Any]]:
        """Get product data from legacy database structure."""
        # Search by Codigo interno (exact) or Chemical Name (contains)
        print(f"DEBUG: searching for '{keyword_or_id}' in {len(self.df_products)} rows")

        # cast to string and strip just in case
        mask = (
            self.df_products["Codigo interno"].astype(str).str.strip()
            == str(keyword_or_id).strip()
        ) | (
            self.df_products["Chemical Name"]
            .astype(str)
            .str.contains(keyword_or_id, case=False, na=False, regex=False)
        )

        results = self.df_products[mask]

        if results.empty:
            return None

        # Take the first match
        row = results.iloc[0]

        # Process H-Statements
        h_raw = (
            str(row["H-Statements"]).split(",") if pd.notna(row["H-Statements"]) else []
        )
        h_texts = [
            self.resolve_code(c, "H")
            for c in h_raw
            if c.strip() and c.strip().lower() != "nan"
        ]

        # Process P-Statements
        p_raw = (
            str(row["Consejos (Frases P)"]).split(",")
            if pd.notna(row["Consejos (Frases P)"])
            else []
        )
        p_texts = [
            self.resolve_code(c, "P")
            for c in p_raw
            if c.strip() and c.strip().lower() != "nan"
        ]

        # Raw codes (clean whitespace)
        h_codes_list = [
            c.strip() for c in h_raw if c.strip() and c.strip().lower() != "nan"
        ]
        p_codes_list = [
            c.strip() for c in p_raw if c.strip() and c.strip().lower() != "nan"
        ]

        # Gather Pictograms (columns with 'X')
        pictograms = []
        possible_picto_cols = [
            "Exclamación",
            "Corrosión",
            "Peligro para la salud",
            "Calavera",
            "Llama",
            "Ambiente",
            "Llama sobre círculo",
            "Bomba explotando",
            "Cilindro de gas",
        ]

        # Also support legacy columns just in case
        legacy_cols = [c for c in self.df_products.columns if "(PICTOGRAMA )" in c]
        all_picto_cols = possible_picto_cols + legacy_cols

        for col in all_picto_cols:
            if col in self.df_products.columns:
                val = row[col]
                if isinstance(val, str) and val.strip().upper() == "X":
                    clean_name = col.replace(" (PICTOGRAMA )", "")
                    if clean_name not in pictograms:
                        pictograms.append(clean_name)

        return {
            "internal_code": row["Codigo interno"],
            "name": row["Chemical Name"],
            "cas": row["CAS Number"],
            "signal_word": row["Signal Word"],
            "emergency_phone": row["Emergencia"],
            "h_statements": h_texts,
            "p_statements": p_texts,
            "h_codes": h_codes_list,
            "p_codes": p_codes_list,
            "pictograms": pictograms,
        }


# --- Test Block ---
if __name__ == "__main__":
    manager = SmartLabelManager("/home/quimicab/Base_datos/original_data")

    print("\n--- Testing Resolution Logic ---")
    test_cases = [
        ("H302", "H"),  # Standard
        ("H336.", "H"),  # Typo: Trailing dot
        ("361", "H"),  # Missing Prefix (Might fail lookup, verify behavior)
        ("P301 + P310", "P"),  # Composite
        ("P 308", "P"),  # Extra space
        ("Long instruction text...", "P"),  # Fallback to raw
    ]

    # inject dummy long text for test if not in definitions
    long_text = "Ojos: Busque atención médica inmediatamente."

    for code, ctype in test_cases:
        res = manager.resolve_code(
            code if code != "Long instruction text..." else long_text, ctype
        )
        print(f"Code: '{code}' -> Result: {res[:60]}...")

    print("\n--- Testing Product Lookup ---")
    # Test with a known product from previous read
    product = manager.get_product_data("IFF-QB00122")  # "1181-D MENTA"
    if product:
        print(f"Product: {product['name']}")
        print(f"H-Statements resolved: {len(product['h_statements'])}")
        for h in product["h_statements"]:
            print(f" - {h[:80]}...")
        print(f"Pictograms: {product['pictograms']}")
    else:
        print("Product not found.")
