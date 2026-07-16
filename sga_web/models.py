"""
User model for Flask-Login integration
Wraps existing UserManager functionality
"""

from flask_login import UserMixin
from user_manager import UserRole


class User(UserMixin):
    """User model compatible with Flask-Login"""

    def __init__(self, user_data: dict):
        self.id = user_data.get("username")
        self.username = user_data.get("username")
        self.full_name = user_data.get("full_name", "")
        self.email = user_data.get("email", "")
        self.role = UserRole(user_data.get("role", "viewer"))
        self.is_active_flag = user_data.get("is_active", True)
        self.must_change_password = user_data.get("must_change_password", False)
        self.last_login = user_data.get("last_login")
        self.warehouse = user_data.get("warehouse", "")

    def get_id(self):
        return self.username

    @property
    def is_active(self):
        return self.is_active_flag

    def is_admin(self):
        return self.role == UserRole.ADMIN

    def is_operator(self):
        return self.role in [UserRole.ADMIN, UserRole.OPERATOR]

    def has_role(self, role: UserRole):
        """Check if user has at least this role level"""
        role_hierarchy = {UserRole.VIEWER: 0, UserRole.OPERATOR: 1, UserRole.ADMIN: 2}
        return role_hierarchy.get(self.role, 0) >= role_hierarchy.get(role, 0)

    def can_print_labels(self):
        return self.role in [UserRole.ADMIN, UserRole.OPERATOR]

    def can_add_products(self):
        """Operators and Admins can add new products"""
        return self.role in [UserRole.ADMIN, UserRole.OPERATOR]

    def can_edit_products(self):
        return self.role == UserRole.ADMIN

    def can_manage_users(self):
        return self.role == UserRole.ADMIN


class PrintQueueItem:
    """Represents an item in the print queue"""

    def __init__(self, data: dict):
        self.code = data.get("code", "")
        self.father_id = data.get("father_id", "")
        self.variant_id = data.get("variant_id", "")
        self.product_name = data.get("product_name", "")
        self.quantity = data.get("quantity", 1)
        self.peso_tara = data.get("peso_tara", 0)
        self.peso_bruto = data.get("peso_bruto", 0)
        self.batch_number = data.get("batch_number", "")
        self.batch_date = data.get("batch_date", "")
        self.product_data = data.get("product_data", {})

    def to_dict(self):
        return {
            "code": self.code,
            "father_id": self.father_id,
            "variant_id": self.variant_id,
            "product_name": self.product_name,
            "quantity": self.quantity,
            "peso_tara": self.peso_tara,
            "peso_bruto": self.peso_bruto,
            "batch_number": self.batch_number,
            "batch_date": self.batch_date,
        }
