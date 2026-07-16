import sys
import os
import io

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import create_app
import traceback


def test():
    app = create_app("development")
    with app.app_context():
        # Let's test the queue add logic
        from routes.labels import get_batch_and_tare

        try:
            code = "PRUEBAS"
            smart_label = app.smart_label
            product_data = smart_label.get_product_data(code)
            print("Product Data:", product_data)

            db_tara, db_batch, db_date, db_vencimiento = get_batch_and_tare(code, 1)
            print("Batch and Tare:", db_tara, db_batch, db_date, db_vencimiento)
        except Exception:
            traceback.print_exc()


if __name__ == "__main__":
    test()
