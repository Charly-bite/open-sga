from sga_web.routes.control_interno import _primary_lote_value, _normalize_iso_date


def test_primary_lote_value_parsing():
    """
    Test that the batch parser correctly extracts the primary batch
    from historical strings separated by commas or pipes.
    """
    # Simple case
    assert _primary_lote_value("PRUEBA-01") == "PRUEBA-01"

    # Empty cases
    assert _primary_lote_value("") == ""
    assert _primary_lote_value(None) == ""

    # Comma separated (historical format)
    assert _primary_lote_value("OLD_BATCH, PRUEBA-02") == "PRUEBA-02"
    assert _primary_lote_value("LOTE1, LOTE2, LOTE3") == "LOTE3"

    # Pipe separated
    assert _primary_lote_value("LOTE1 | LOTE2") == "LOTE2"


def test_normalize_iso_date():
    """
    Test that date normalization converts various date formats
    into the standard YYYY-MM-DD.
    """
    # Already normalized
    assert _normalize_iso_date("2026-05-18") == "2026-05-18"

    # Empty
    assert _normalize_iso_date("") == ""
    assert _normalize_iso_date(None) == ""

    # Spanish format DD-MM-YYYY
    assert _normalize_iso_date("18-05-2026") == "2026-05-18"
    assert _normalize_iso_date("18/05/2026") == "2026-05-18"

    # Fallback to string if unparseable
    assert _normalize_iso_date("INVALID_DATE") == "INVALID_DATE"
