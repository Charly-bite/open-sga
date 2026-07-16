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
