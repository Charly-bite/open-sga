"""
Routes package for SGA Web
"""

from routes.auth import auth_bp
from routes.main import main_bp
from routes.labels import labels_bp
from routes.products import products_bp
from routes.orders import orders_bp
from routes.api import api_bp
from routes.templates import templates_bp

__all__ = [
    "auth_bp",
    "main_bp",
    "labels_bp",
    "products_bp",
    "orders_bp",
    "api_bp",
    "templates_bp",
]
