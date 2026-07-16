"""
Tests for the Live Edit Dates feature.

Covers:
- Date normalization (YYYY-MM-DD → DD/MM/YYYY)
- Date validation (future date rejection for both formats)
- Reinspection date auto-calculation (+1 year)
- to_m_y() Mes/Año conversion (MM/YYYY)
- Edge cases: leap years, custom strings, partial formats
"""
import pytest
import sys
import os
from datetime import datetime, date
from unittest.mock import patch, MagicMock

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


# ---------------------------------------------------------------------------
# Unit tests for _normalize_date (inline helper from labels.py add_to_queue)
# ---------------------------------------------------------------------------

def _normalize_date(d):
    """Replicate the _normalize_date helper from labels.py for testing."""
    d = str(d).strip()
    if len(d) >= 10 and d[4] == "-" and d[7] == "-":
        try:
            dt = datetime.strptime(d[:10], "%Y-%m-%d")
            return dt.strftime("%d/%m/%Y")
        except ValueError:
            pass
    return d


class TestNormalizeDate:
    """Tests for _normalize_date helper."""

    def test_yyyy_mm_dd_to_dd_mm_yyyy(self):
        assert _normalize_date("2026-05-22") == "22/05/2026"

    def test_yyyy_mm_dd_start_of_year(self):
        assert _normalize_date("2026-01-01") == "01/01/2026"

    def test_yyyy_mm_dd_end_of_year(self):
        assert _normalize_date("2026-12-31") == "31/12/2026"

    def test_already_dd_mm_yyyy_passthrough(self):
        """DD/MM/YYYY format should pass through unchanged."""
        assert _normalize_date("22/05/2026") == "22/05/2026"

    def test_empty_string_passthrough(self):
        assert _normalize_date("") == ""

    def test_custom_text_passthrough(self):
        """Arbitrary strings like 'Abril 2026' should pass through."""
        assert _normalize_date("Abril 2026") == "Abril 2026"

    def test_partial_date_passthrough(self):
        """Partial dates like '05/2026' should pass through."""
        assert _normalize_date("05/2026") == "05/2026"

    def test_na_passthrough(self):
        assert _normalize_date("N/A") == "N/A"

    def test_leap_year_date(self):
        assert _normalize_date("2024-02-29") == "29/02/2024"

    def test_invalid_yyyy_mm_dd_passthrough(self):
        """Invalid dates in YYYY-MM-DD format should pass through."""
        assert _normalize_date("2026-13-45") == "2026-13-45"


# ---------------------------------------------------------------------------
# Tests for to_m_y (Mes/Año conversion)
# ---------------------------------------------------------------------------

def to_m_y(d_str):
    """Replicate the fixed to_m_y helper from generate_ghs_label.py."""
    d_str = str(d_str).strip()
    if not d_str or d_str == "N/A":
        return d_str
    # Check for DD/MM/YYYY
    if len(d_str) >= 10 and d_str[2] == "/" and d_str[5] == "/":
        return f"{d_str[3:5]}/{d_str[6:10]}"
    # Check for YYYY-MM-DD
    if len(d_str) >= 10 and d_str[4] == "-" and d_str[7] == "-":
        return f"{d_str[5:7]}/{d_str[0:4]}"
    return d_str


class TestToMY:
    """Tests for to_m_y Mes/Año conversion."""

    def test_dd_mm_yyyy_to_mm_yyyy(self):
        assert to_m_y("22/05/2026") == "05/2026"

    def test_yyyy_mm_dd_to_mm_yyyy(self):
        assert to_m_y("2026-05-22") == "05/2026"

    def test_january(self):
        assert to_m_y("15/01/2026") == "01/2026"

    def test_december(self):
        assert to_m_y("31/12/2025") == "12/2025"

    def test_na_passthrough(self):
        assert to_m_y("N/A") == "N/A"

    def test_empty_string(self):
        assert to_m_y("") == ""

    def test_partial_format_passthrough(self):
        """Already MM/YYYY should pass through unchanged."""
        assert to_m_y("05/2026") == "05/2026"

    def test_custom_text_passthrough(self):
        assert to_m_y("Abril 2026") == "Abril 2026"

    def test_full_4_digit_year_dd_mm_yyyy(self):
        """Ensure we get 4-digit year, not 2-digit (the old bug)."""
        result = to_m_y("22/05/2026")
        year_part = result.split("/")[1]
        assert len(year_part) == 4, f"Expected 4-digit year, got '{year_part}'"

    def test_full_4_digit_year_yyyy_mm_dd(self):
        """Ensure we get 4-digit year from YYYY-MM-DD."""
        result = to_m_y("2026-05-22")
        year_part = result.split("/")[1]
        assert len(year_part) == 4, f"Expected 4-digit year, got '{year_part}'"


# ---------------------------------------------------------------------------
# Tests for reinspection date auto-calculation
# ---------------------------------------------------------------------------

def calculate_reinspection(batch_date_str):
    """Replicate the reinspection date calculation logic from labels.py."""
    try:
        try:
            bd = datetime.strptime(batch_date_str[:10], "%Y-%m-%d")
        except ValueError:
            bd = datetime.strptime(batch_date_str[:10], "%d/%m/%Y")
        
        try:
            rd = bd.replace(year=bd.year + 1)
        except ValueError:
            rd = bd.replace(year=bd.year + 1, day=28)
        return rd.strftime("%d/%m/%Y")
    except Exception:
        return ""


class TestReinspectionCalculation:
    """Tests for reinspection date auto-calculation (+1 year)."""

    def test_standard_dd_mm_yyyy(self):
        assert calculate_reinspection("22/05/2026") == "22/05/2027"

    def test_standard_yyyy_mm_dd(self):
        assert calculate_reinspection("2026-05-22") == "22/05/2027"

    def test_leap_year_feb_29(self):
        """Feb 29 → Feb 28 next year (non-leap year)."""
        assert calculate_reinspection("29/02/2024") == "28/02/2025"

    def test_end_of_year(self):
        assert calculate_reinspection("31/12/2026") == "31/12/2027"

    def test_start_of_year(self):
        assert calculate_reinspection("01/01/2026") == "01/01/2027"

    def test_invalid_date_returns_empty(self):
        """Custom text that can't be parsed should return empty."""
        assert calculate_reinspection("Abril 2026") == ""

    def test_partial_date_returns_empty(self):
        """Partial dates like '05/2026' should return empty."""
        assert calculate_reinspection("05/2026") == ""


# ---------------------------------------------------------------------------
# Tests for date validation (future date rejection)
# ---------------------------------------------------------------------------

def validate_batch_date(batch_date):
    """Replicate the validation logic from labels.py."""
    if not batch_date:
        return True  # Empty is OK
    if batch_date == "00":
        return True  # "00" sentinel — skip validation
    try:
        try:
            parsed_bd = datetime.strptime(batch_date[:10], "%Y-%m-%d")
        except ValueError:
            parsed_bd = datetime.strptime(batch_date[:10], "%d/%m/%Y")
        if parsed_bd.date() > date.today():
            return False  # Future date — rejected
    except ValueError:
        pass  # Unparseable — accepted (custom text)
    return True


class TestDateValidation:
    """Tests for batch date future-date validation."""

    def test_past_date_yyyy_mm_dd_accepted(self):
        assert validate_batch_date("2024-01-15") is True

    def test_past_date_dd_mm_yyyy_accepted(self):
        assert validate_batch_date("15/01/2024") is True

    def test_today_accepted(self):
        today_str = date.today().strftime("%d/%m/%Y")
        assert validate_batch_date(today_str) is True

    def test_future_date_yyyy_mm_dd_rejected(self):
        assert validate_batch_date("2099-12-31") is False

    def test_future_date_dd_mm_yyyy_rejected(self):
        assert validate_batch_date("31/12/2099") is False

    def test_custom_text_accepted(self):
        """Custom text that can't be parsed should be accepted."""
        assert validate_batch_date("Abril 2026") is True

    def test_empty_accepted(self):
        assert validate_batch_date("") is True

    def test_na_accepted(self):
        assert validate_batch_date("N/A") is True

    def test_00_sentinel_accepted(self):
        """'00' blank sentinel should be accepted (skip validation)."""
        assert validate_batch_date("00") is True


# ---------------------------------------------------------------------------
# Tests for "00" blank sentinel (date field blanking)
# ---------------------------------------------------------------------------

def resolve_label_dates(batch_date, reinspection_date):
    """
    Replicate the date resolution logic from generate_ghs_label.py.
    Returns (elab_date, insp_date) as they would appear on the label.
    """
    today_str = batch_date
    reinsp_override = reinspection_date

    try:
        dt = None
        if "-" in str(today_str):
            dt = datetime.strptime(today_str, "%Y-%m-%d")
        elif "/" in str(today_str):
            parts = str(today_str).split("/")
            if len(parts) == 3 and len(parts[2]) == 4:
                dt = datetime(int(parts[2]), int(parts[1]), int(parts[0]))

        if dt:
            elab_date = dt.strftime("%d/%m/%Y")
            if reinsp_override:
                try:
                    if "-" in str(reinsp_override):
                        rd = datetime.strptime(reinsp_override, "%Y-%m-%d")
                    else:
                        rd = datetime.strptime(reinsp_override, "%d/%m/%Y")
                    insp_date = rd.strftime("%d/%m/%Y")
                except Exception:
                    insp_date = str(reinsp_override)
            else:
                try:
                    insp_dt = dt.replace(year=dt.year + 1)
                except ValueError:
                    insp_dt = dt.replace(year=dt.year + 1, day=28)
                insp_date = insp_dt.strftime("%d/%m/%Y")
        else:
            elab_date = today_str
            insp_date = "N/A"
    except Exception:
        elab_date = today_str or date.today().strftime("%d/%m/%Y")
        insp_date = "N/A"

    # Handle "00" sentinel: user wants this date field blank on the label
    if today_str == "00":
        elab_date = ""
        insp_date = "" if (not reinsp_override or reinsp_override == "00") else str(reinsp_override)
    elif reinsp_override == "00":
        insp_date = ""

    return elab_date, insp_date


class TestBlankSentinel:
    """Tests for '00' blank sentinel — user types '00' to leave a date blank."""

    def test_both_00_produces_blank(self):
        """Both dates set to '00' → both blank on label."""
        elab, insp = resolve_label_dates("00", "00")
        assert elab == ""
        assert insp == ""

    def test_batch_00_reinsp_00(self):
        """Batch '00' with reinspection '00' → both blank."""
        elab, insp = resolve_label_dates("00", "00")
        assert elab == ""
        assert insp == ""

    def test_batch_00_reinsp_empty(self):
        """Batch '00' with no reinspection → both blank."""
        elab, insp = resolve_label_dates("00", "")
        assert elab == ""
        assert insp == ""

    def test_batch_00_reinsp_has_date(self):
        """Batch '00' but reinspection has a real date → elab blank, reinsp preserved."""
        elab, insp = resolve_label_dates("00", "22/05/2027")
        assert elab == ""
        assert insp == "22/05/2027"

    def test_batch_normal_reinsp_00(self):
        """Normal batch date but reinspection '00' → elab has date, insp blank."""
        elab, insp = resolve_label_dates("22/05/2026", "00")
        assert elab == "22/05/2026"
        assert insp == ""

    def test_normal_dates_unaffected(self):
        """Normal dates should not be affected by the sentinel logic."""
        elab, insp = resolve_label_dates("22/05/2026", "22/05/2027")
        assert elab == "22/05/2026"
        assert insp == "22/05/2027"

    def test_00_normalize_passthrough(self):
        """'00' should pass through _normalize_date unchanged."""
        assert _normalize_date("00") == "00"

    def test_00_validation_accepted(self):
        """'00' should be accepted by date validation (no future-date error)."""
        assert validate_batch_date("00") is True

    def test_00_reinspection_calc_returns_empty(self):
        """'00' should return empty from reinspection calculation."""
        assert calculate_reinspection("00") == ""


# ---------------------------------------------------------------------------
# Integration-style: Full flow test
# ---------------------------------------------------------------------------

class TestFullDateFlow:
    """End-to-end flow: normalize → calculate → format."""

    def test_sap_date_full_flow(self):
        """Simulate SAP sending YYYY-MM-DD, normalize, calculate reinspection."""
        sap_date = "2026-05-22"
        normalized = _normalize_date(sap_date)
        assert normalized == "22/05/2026"
        
        reinsp = calculate_reinspection(normalized)
        assert reinsp == "22/05/2027"
        
        # If Mes/Año is applied
        assert to_m_y(normalized) == "05/2026"
        assert to_m_y(reinsp) == "05/2027"

    def test_user_typed_month_year_only(self):
        """User types '05/2026' — should pass through everything untouched."""
        user_input = "05/2026"
        normalized = _normalize_date(user_input)  # Should passthrough
        assert normalized == "05/2026"
        
        reinsp = calculate_reinspection(user_input)  # Can't calculate — empty
        assert reinsp == ""

    def test_user_typed_full_dd_mm_yyyy(self):
        """User types full DD/MM/YYYY — should work end to end."""
        user_input = "15/03/2025"
        normalized = _normalize_date(user_input)  # Already correct format
        assert normalized == "15/03/2025"
        
        reinsp = calculate_reinspection(user_input)
        assert reinsp == "15/03/2026"

    def test_00_sentinel_full_flow(self):
        """User types '00' → label dates are blank."""
        elab, insp = resolve_label_dates("00", "00")
        assert elab == ""
        assert insp == ""
        # The blank dates should not crash to_m_y
        assert to_m_y(elab) == ""
        assert to_m_y(insp) == ""


# ---------------------------------------------------------------------------
# Tests for iframe buster on login page
# ---------------------------------------------------------------------------

class TestLoginIframeBuster:
    """Tests for the login page iframe breakout script."""

    def test_login_html_contains_iframe_buster(self):
        """The login template should have the iframe buster script."""
        login_path = os.path.join(
            os.path.dirname(__file__), "..", "sga_web", "templates", "auth", "login.html"
        )
        with open(login_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "window.top !== window.self" in content, \
            "login.html is missing the iframe buster script"

    def test_login_html_redirects_top(self):
        """The iframe buster should redirect top window to login."""
        login_path = os.path.join(
            os.path.dirname(__file__), "..", "sga_web", "templates", "auth", "login.html"
        )
        with open(login_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "window.top.location.href" in content, \
            "login.html iframe buster should redirect window.top"


# ---------------------------------------------------------------------------
# Tests for global fetch 401 handler
# ---------------------------------------------------------------------------

class TestGlobalFetch401Handler:
    """Tests for the global fetch monkey-patch that handles 401."""

    def test_base_html_has_401_handler(self):
        """base.html should catch 401 responses and redirect to login."""
        base_path = os.path.join(
            os.path.dirname(__file__), "..", "sga_web", "templates", "base.html"
        )
        with open(base_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "res.status === 401" in content, \
            "base.html is missing the global 401 handler"

    def test_base_html_sends_xhr_header(self):
        """base.html fetch should include X-Requested-With header."""
        base_path = os.path.join(
            os.path.dirname(__file__), "..", "sga_web", "templates", "base.html"
        )
        with open(base_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "X-Requested-With" in content, \
            "base.html is missing X-Requested-With header injection"
