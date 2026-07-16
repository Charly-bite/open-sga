import sys
import os
import io

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import create_app
from flask import session


def test():
    app = create_app("development")
    app.config["LOGIN_DISABLED"] = True

    with app.test_request_context(
        "/labels/queue/add", method="POST", json={"code": "PRUEBA-01", "quantity": 1}
    ):
        session["print_queue"] = []

        # We need to bypass the current_user.can_print_labels() check.
        # Let's mock current_user on the flask_login module level.
        import flask_login

        class MockUser:
            @property
            def is_authenticated(self):
                return True

            def can_print_labels(self):
                return True

            @property
            def is_active(self):
                return True

        flask_login.utils._get_user = lambda: MockUser()

        from routes.labels import add_to_queue

        try:
            response = add_to_queue()
            print("Response:", response)
            if hasattr(response, "get_data"):
                print("Data:", response.get_data(as_text=True))
        except Exception:
            import traceback

            traceback.print_exc()


if __name__ == "__main__":
    test()
