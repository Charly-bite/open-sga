from smart_label import SmartLabelManager
from generate_ghs_label import GHSLabelGenerator
from settings_manager import SettingsManager


def simulate_workflow(scanned_code):
    print(f"\n📢 --- STARTING WORKFLOW FOR SCAN: {scanned_code} ---")

    # 1. Initialize Systems
    base_dir = "/home/quimicab/Base_datos/original_data"

    # Logic Engine
    smart_label = SmartLabelManager(base_dir)

    # Config Engine (Retail Context)
    settings_mgr = SettingsManager(
        config_file="/home/quimicab/Base_datos/config_retail_sample.json",
        barcode_db_file="/home/quimicab/Base_datos/mock_barcode_db.json",
    )

    # Label Generator
    generator = GHSLabelGenerator(base_dir)

    # 2. Resolve Barcode
    father_id, variant_id = settings_mgr.resolve_barcode(scanned_code)
    print(f"✅ Barcode Resolved: Father='{father_id}', Variant='{variant_id}'")

    # 3. Fetch Master Data
    master_data = smart_label.get_product_data(father_id)
    if not master_data:
        print(f"❌ Error: Product ID {father_id} not found in Master Database.")
        return

    print(f"   Found Master Data: {master_data['name']}")

    # 4. Apply Configuration/Overrides
    final_data = settings_mgr.apply_overrides(master_data, father_id, variant_id)

    # 5. Generate Label
    output_filename = f"/home/quimicab/Base_datos/label_{scanned_code}.pdf"

    print("   Generating PDF...")
    try:
        generator = GHSLabelGenerator(base_dir)
        generator.generate_label(final_data, output_filename)
        print(f"✅ Success! Label saved to {output_filename}")
    except Exception as e:
        print(f"❌ Error generating PDF: {e}")


if __name__ == "__main__":
    # Simulate scanning a Son Barcode (1L Menta) - 2 pictograms
    simulate_workflow("750100000001")

    # Test with a product that has 4 pictograms (ASFIER 100)
    simulate_workflow("KAO-QB00001")

    # Test with a product that has 5 pictograms (GLUTARALDEHIDO)
    simulate_workflow("VAR-QB00104")
