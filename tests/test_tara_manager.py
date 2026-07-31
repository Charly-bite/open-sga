from unittest.mock import MagicMock
from tara_weight_manager import TaraWeightManager


def test_tara_manager_initialization_caching():
    """
    Test that the TaraWeightManager correctly caches the initialization
    process so it doesn't run the expensive auto-classification algorithm
    on every single request.
    """
    # Create an instance of the manager
    manager = TaraWeightManager()

    # Mock the internal load and classify methods to track how many times they are called
    manager._load_classifications = MagicMock()
    manager.auto_classify_all = MagicMock()

    # Ensure starting state is not initialized
    assert manager._is_initialized is False

    # First call: Should perform full initialization
    manager.initialize_classifications()

    assert manager._load_classifications.call_count == 1
    assert manager.auto_classify_all.call_count == 1
    assert manager._is_initialized is True

    # Second call: Should return early from cache without calling the expensive methods
    manager.initialize_classifications()

    assert manager._load_classifications.call_count == 1
    assert manager.auto_classify_all.call_count == 1
    assert manager._is_initialized is True


def test_tara_manager_force_initialization():
    """
    Test that the TaraWeightManager forces a re-initialization if the
    force flag is provided, even if it's already initialized.
    """
    manager = TaraWeightManager()
    manager._is_initialized = True

    manager._load_classifications = MagicMock()
    manager.auto_classify_all = MagicMock()

    # Force initialization
    manager.initialize_classifications(force=True)

    assert manager._load_classifications.call_count == 1
    assert manager.auto_classify_all.call_count == 1


def test_tara_update_liquid_light():
    """
    Verify that resolving tara for a liquid/light product with typical
    weights behaves correctly:
    - frasco is reverted to 0.09 kg
    - tambo_plastico is updated to 1.0 kg for 11-20 kg range, but stays 0.90 kg for other weights (like 10.0 and 200.0 kg).
    """
    manager = TaraWeightManager()
    
    # 1. Test frasco tara is 0.09 kg
    frasco = manager._get_container_by_id("frasco")
    assert frasco is not None
    assert frasco["tara_kg"] == 0.09
    
    # 2. Test tambo_plastico tara is 1.0 kg in the catalog
    tambo = manager._get_container_by_id("tambo_plastico")
    assert tambo is not None
    assert tambo["tara_kg"] == 1.0
    
    # 3. Test suggestion lists for frasco return 0.09 for 1.0 kg
    suggestions_1 = manager.get_smart_suggestions(1.0, "ANY_PRODUCT")
    frasco_suggestions = [s for s in suggestions_1 if s["id"] == "frasco"]
    assert len(frasco_suggestions) > 0
    assert frasco_suggestions[0]["tara_kg"] == 0.09
    
    # 4. Test suggestion lists for tambo_plastico return 1.0 for 15.0 kg
    suggestions_15 = manager.get_smart_suggestions(15.0, "ANY_PRODUCT")
    tambo_suggestions_15 = [s for s in suggestions_15 if s["id"] == "tambo_plastico"]
    assert len(tambo_suggestions_15) > 0
    assert tambo_suggestions_15[0]["tara_kg"] == 1.0

    # 5. Test suggestion lists for tambo_plastico return 0.90 for 10.0 kg (outside range)
    suggestions_10 = manager.get_smart_suggestions(10.0, "ANY_PRODUCT")
    tambo_suggestions_10 = [s for s in suggestions_10 if s["id"] == "tambo_plastico"]
    assert len(tambo_suggestions_10) > 0
    assert tambo_suggestions_10[0]["tara_kg"] == 0.90

    # 6. Test suggestion lists for tambo_plastico return 0.90 for 200.0 kg (outside range)
    suggestions_200 = manager.get_smart_suggestions(200.0, "ANY_PRODUCT")
    tambo_suggestions_200 = [s for s in suggestions_200 if s["id"] == "tambo_plastico"]
    assert len(tambo_suggestions_200) > 0
    assert tambo_suggestions_200[0]["tara_kg"] == 0.90

