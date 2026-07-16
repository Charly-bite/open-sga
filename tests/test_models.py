"""Tests for sga_web/models.py - User and PrintQueueItem models."""

from models import User
from user_manager import UserRole
from models import PrintQueueItem


def test_user_init_defaults():
    u = User({"username": "alice"})
    assert u.id == "alice"
    assert u.username == "alice"
    assert u.full_name == ""
    assert u.email == ""
    assert u.role == UserRole.VIEWER
    assert u.is_active is True
    assert u.must_change_password is False
    assert u.last_login is None
    assert u.warehouse == ""


def test_user_init_full():
    data = {
        "username": "bob",
        "full_name": "Bob Builder",
        "email": "bob@example.com",
        "role": "admin",
        "is_active": False,
        "must_change_password": True,
        "last_login": "2026-01-01 00:00:00",
        "warehouse": "WH-01",
    }
    u = User(data)
    assert u.full_name == "Bob Builder"
    assert u.role == UserRole.ADMIN
    assert u.is_active is False
    assert u.must_change_password is True
    assert u.warehouse == "WH-01"


def test_user_get_id():
    assert User({"username": "charlie"}).get_id() == "charlie"


def test_user_is_admin():
    assert User({"username": "a", "role": "admin"}).is_admin() is True
    assert User({"username": "b", "role": "operator"}).is_admin() is False
    assert User({"username": "c", "role": "viewer"}).is_admin() is False


def test_user_is_operator():
    assert User({"username": "a", "role": "admin"}).is_operator() is True
    assert User({"username": "b", "role": "operator"}).is_operator() is True
    assert User({"username": "c", "role": "viewer"}).is_operator() is False


def test_user_has_role_hierarchy():
    admin = User({"username": "a", "role": "admin"})
    operator = User({"username": "b", "role": "operator"})
    viewer = User({"username": "c", "role": "viewer"})
    assert admin.has_role(UserRole.ADMIN) is True
    assert operator.has_role(UserRole.OPERATOR) is True
    assert operator.has_role(UserRole.ADMIN) is False
    assert viewer.has_role(UserRole.VIEWER) is True
    assert viewer.has_role(UserRole.OPERATOR) is False


def test_user_can_print_labels():
    assert User({"username": "a", "role": "admin"}).can_print_labels() is True
    assert User({"username": "b", "role": "operator"}).can_print_labels() is True
    assert User({"username": "c", "role": "viewer"}).can_print_labels() is False


def test_user_can_add_products():
    assert User({"username": "a", "role": "admin"}).can_add_products() is True
    assert User({"username": "b", "role": "operator"}).can_add_products() is True
    assert User({"username": "c", "role": "viewer"}).can_add_products() is False


def test_user_can_edit_products():
    assert User({"username": "a", "role": "admin"}).can_edit_products() is True
    assert User({"username": "b", "role": "operator"}).can_edit_products() is False


def test_user_can_manage_users():
    assert User({"username": "a", "role": "admin"}).can_manage_users() is True
    assert User({"username": "b", "role": "operator"}).can_manage_users() is False


def test_print_queue_item_defaults():
    item = PrintQueueItem({})
    assert item.code == ""
    assert item.quantity == 1
    assert item.peso_tara == 0
    assert item.product_data == {}


def test_print_queue_item_full():
    data = {
        "code": "P001",
        "father_id": "F001",
        "variant_id": "V001",
        "product_name": "Acetone",
        "quantity": 5,
        "peso_tara": 1.5,
        "peso_bruto": 10.0,
        "batch_number": "LOT-2026",
        "batch_date": "2026-01-15",
        "product_data": {"cas": "67-64-1"},
    }
    item = PrintQueueItem(data)
    assert item.code == "P001"
    assert item.quantity == 5


def test_print_queue_item_to_dict():
    data = {
        "code": "P001",
        "father_id": "F001",
        "variant_id": "V001",
        "product_name": "Acetone",
        "quantity": 5,
        "peso_tara": 1.5,
        "peso_bruto": 10.0,
        "batch_number": "LOT-2026",
        "batch_date": "2026-01-15",
        "product_data": {"cas": "67-64-1"},
    }
    d = PrintQueueItem(data).to_dict()
    assert d["code"] == "P001"
    assert "product_data" not in d
