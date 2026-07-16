import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "sga_web")))

from app import create_app
import time

app = create_app()

with app.test_client() as client:
    app.config["LOGIN_DISABLED"] = True
    client.application.login_manager.anonymous_user = type(
        "MockUser",
        (),
        {
            "is_authenticated": True,
            "username": "admin",
            "is_active": True,
            "is_admin": lambda self: True,
            "get_id": lambda self: "1",
        },
    )

    # First search
    start_time = time.time()
    response = client.get("/control/api/products?page=1&per_page=50&search=Prueba")
    end_time = time.time()

    print(f"Status 1: {response.status_code}")
    print(f"Time taken 1st: {end_time - start_time:.4f} seconds")

    # Second search
    start_time = time.time()
    response = client.get("/control/api/products?page=1&per_page=50&search=Prueba2")
    end_time = time.time()

    print(f"Status 2: {response.status_code}")
    print(f"Time taken 2nd: {end_time - start_time:.4f} seconds")

    # Filter by type
    start_time = time.time()
    response = client.get(
        "/control/api/products?page=1&per_page=50&product_type=liquido"
    )
    end_time = time.time()

    print(f"Status 3: {response.status_code}")
    print(f"Time taken 3rd: {end_time - start_time:.4f} seconds")
