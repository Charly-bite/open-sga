#!/usr/bin/env python3
"""
SGA - Sistema de Gestión de Almacén
SAP Business One → GHS Label Generation Integration

This module provides the core workflow for warehouse operations:
1. Receive order notification from SAP B1
2. Queue items for label printing
3. Match items with GHS safety data
4. Generate compliant labels
5. Track batch/lot information

Usage:
    # Interactive mode
    python sga_controller.py

    # Direct order processing
    python sga_controller.py --order 10168

    # Batch mode (process multiple orders)
    python sga_controller.py --orders 10168,10169,10170
"""

import os
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
import logging

# Local imports
from sap_connector import SAPHanaConnector
from smart_label import SmartLabelManager
from generate_ghs_label import GHSLabelGenerator
from shared_file_manager import SharedFileManager

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "original_data")
UNIFIED_DB_DIR = os.path.join(BASE_DIR, "unified_db")
OUTPUT_DIR = os.path.join(BASE_DIR, "generated_labels")
QUEUE_FILE = os.path.join(BASE_DIR, "data", "label_queue.json")

# Default supplier info for labels
DEFAULT_SUPPLIER = {
    "name": "QUIMICABOSS S.A. de C.V.",
    "address": "Ciudad de México, México",
    "phone": "01 800 002 1400",
}


# =============================================================================
# DATA CLASSES
# =============================================================================


class ItemStatus(Enum):
    """Status of items in the print queue."""

    PENDING = "pending"
    MATCHED = "matched"
    NO_GHS_DATA = "no_ghs_data"
    PRINTED = "printed"
    ERROR = "error"


@dataclass
class QueueItem:
    """Represents an item in the label print queue."""

    # SAP Order Info
    order_number: int
    line_number: int
    item_code: str
    description: str
    quantity: float
    unit: str
    warehouse: str

    # GHS Matching
    ghs_product_id: Optional[str] = None
    ghs_matched: bool = False

    # Processing Info
    status: str = ItemStatus.PENDING.value
    labels_to_print: int = 1
    batch_date: str = ""
    batch_number: str = ""

    # Metadata
    queued_at: str = ""
    printed_at: str = ""
    output_file: str = ""

    def __post_init__(self):
        if not self.queued_at:
            self.queued_at = datetime.now().isoformat()
        if not self.batch_date:
            self.batch_date = datetime.now().strftime("%Y-%m-%d")


@dataclass
class PrintQueue:
    """The main print queue containing all pending items."""

    items: List[QueueItem] = field(default_factory=list)
    created_at: str = ""
    last_modified: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        self.last_modified = datetime.now().isoformat()

    def add_item(self, item: QueueItem):
        """Add an item to the queue."""
        self.items.append(item)
        self.last_modified = datetime.now().isoformat()

    def get_pending(self) -> List[QueueItem]:
        """Get all pending items."""
        return [
            i
            for i in self.items
            if i.status in [ItemStatus.PENDING.value, ItemStatus.MATCHED.value]
        ]

    def get_by_order(self, order_number: int) -> List[QueueItem]:
        """Get items for a specific order."""
        return [i for i in self.items if i.order_number == order_number]

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "items": [asdict(item) for item in self.items],
            "created_at": self.created_at,
            "last_modified": self.last_modified,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "PrintQueue":
        """Create from dictionary."""
        queue = cls(
            created_at=data.get("created_at", ""),
            last_modified=data.get("last_modified", ""),
        )
        for item_data in data.get("items", []):
            queue.items.append(QueueItem(**item_data))
        return queue


# =============================================================================
# SGA CONTROLLER
# =============================================================================


class SGAController:
    """
    Main controller for the SGA (Sistema de Gestión de Almacén).
    Orchestrates the flow from SAP orders to printed GHS labels.
    """

    def __init__(self, sap_username: str = None, sap_password: str = None):
        """
        Initialize the SGA controller.

        Args:
            sap_username: SAP HANA username
            sap_password: SAP HANA password
        """
        self.sap_username = sap_username
        self.sap_password = sap_password
        self.sap_connector: Optional[SAPHanaConnector] = None
        self.label_manager: Optional[SmartLabelManager] = None
        self.label_generator: Optional[GHSLabelGenerator] = None
        self.queue: PrintQueue = PrintQueue()

        # Ensure output directory exists
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        # Load existing queue if present
        self._load_queue()

    def _load_queue(self):
        """Load the print queue from disk using SharedFileManager."""
        try:
            file_manager = SharedFileManager()
            data = file_manager.read_json(QUEUE_FILE)
            if data:
                self.queue = PrintQueue.from_dict(data)
                logger.info(f"Loaded queue with {len(self.queue.items)} items")
            else:
                self.queue = PrintQueue()
        except Exception as e:
            logger.warning(f"Could not load queue: {e}")
            self.queue = PrintQueue()

    def _save_queue(self):
        """Save the print queue to disk using SharedFileManager."""
        try:
            file_manager = SharedFileManager()
            file_manager.write_json(QUEUE_FILE, self.queue.to_dict())
            logger.debug("Queue saved to disk using SharedFileManager")
        except Exception as e:
            logger.error(f"Could not save queue: {e}")

    def connect_sap(self, username: str = None, password: str = None) -> bool:
        """
        Connect to SAP HANA.

        Args:
            username: Override username
            password: Override password

        Returns:
            True if connection successful
        """
        user = username or self.sap_username
        pwd = password or self.sap_password

        # Initialize connector with defaults or provided vals
        self.sap_connector = SAPHanaConnector()

        # Check if we have credentials either from args, controller state, or connector defaults
        if (
            not user
            and not pwd
            and (not self.sap_connector.username or not self.sap_connector.password)
        ):
            raise ValueError("SAP credentials required")

        try:
            self.sap_connector.connect(user, pwd)
        except Exception as e:
            logger.error(f"Failed to connect to SAP: {e}")

        return getattr(self.sap_connector, "connected", False)

    def init_label_system(self):
        """Initialize the label manager and generator."""
        if not self.label_manager:
            self.label_manager = SmartLabelManager(DATA_DIR)

        if not self.label_generator:
            self.label_generator = GHSLabelGenerator(DATA_DIR)

    def fetch_order(self, order_number: int) -> Optional[Dict]:
        """
        Fetch order details from SAP Business One.

        Args:
            order_number: SAP B1 DocNum

        Returns:
            Order data dictionary or None
        """
        if not self.sap_connector or not self.sap_connector.connected:
            raise ConnectionError("Not connected to SAP. Call connect_sap() first.")

        try:
            return self.sap_connector.get_order_details(order_number)
        except Exception as e:
            logger.error(f"Failed to fetch order {order_number} from SAP: {e}")
            return None

    def queue_order(self, order_number: int) -> List[QueueItem]:
        """
        Fetch an order from SAP and add its items to the print queue.

        Args:
            order_number: SAP B1 DocNum

        Returns:
            List of queued items
        """
        logger.info(f"Fetching order {order_number} from SAP...")

        try:
            order_data = self.fetch_order(order_number)

            if not order_data:
                logger.warning(
                    f"Order {order_number} not found in SAP or error fetching"
                )
                return []

            header = order_data["header"]
            items = order_data["items"]

            logger.info(
                f"Order {order_number}: {header['customer_name']} - {len(items)} items"
            )

            queued_items = []

            for item in items:
                queue_item = QueueItem(
                    order_number=header["order_number"],
                    line_number=item["line_number"],
                    item_code=item["item_code"],
                    description=item["description"],
                    quantity=item["quantity"],
                    unit=item["unit"],
                    warehouse=item["warehouse"],
                    labels_to_print=1,  # Default: 1 label per item, can be adjusted
                )

                self.queue.add_item(queue_item)
                queued_items.append(queue_item)
                logger.info(f"  + Queued: {item['item_code']} - {item['description']}")

            self._save_queue()

            return queued_items
        except Exception as e:
            logger.error(f"Error queueing order {order_number}: {e}")
            return []

    def match_ghs_data(self) -> Dict[str, int]:
        """
        Match all pending items in the queue with GHS product data.

        Returns:
            Statistics dict with matched/unmatched counts
        """
        self.init_label_system()

        stats = {"matched": 0, "no_data": 0, "already_matched": 0}

        for item in self.queue.items:
            if item.status == ItemStatus.PRINTED.value:
                continue

            if item.ghs_matched:
                stats["already_matched"] += 1
                continue

            # Try to find GHS data by item code
            product_data = self.label_manager.get_product_data(item.item_code)

            if product_data:
                item.ghs_product_id = product_data["internal_code"]
                item.ghs_matched = True
                item.status = ItemStatus.MATCHED.value
                stats["matched"] += 1
                logger.info(f"✅ Matched: {item.item_code} -> {product_data['name']}")
            else:
                item.status = ItemStatus.NO_GHS_DATA.value
                stats["no_data"] += 1
                logger.warning(f"⚠️ No GHS data: {item.item_code} - {item.description}")

        self._save_queue()

        return stats

    def generate_label(
        self, item: QueueItem, batch_number: str = None
    ) -> Optional[str]:
        """
        Generate a GHS label for a single queue item.

        Args:
            item: The queue item
            batch_number: Optional batch/lot number

        Returns:
            Path to generated PDF or None
        """
        self.init_label_system()

        if not item.ghs_matched:
            logger.warning(
                f"Cannot generate label for unmatched item: {item.item_code}"
            )
            return None

        # Get full product data
        product_data = self.label_manager.get_product_data(item.ghs_product_id)

        if not product_data:
            logger.error(f"GHS data not found for {item.ghs_product_id}")
            item.status = ItemStatus.ERROR.value
            return None

        # Add batch info
        if batch_number:
            item.batch_number = batch_number

        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"label_{item.order_number}_{item.item_code}_{timestamp}.pdf"
        output_path = os.path.join(OUTPUT_DIR, filename)

        # Generate the label
        try:
            self.label_generator.generate_label(
                product_data,
                output_filename=output_path,
                supplier_info=DEFAULT_SUPPLIER,
            )

            item.output_file = output_path
            item.printed_at = datetime.now().isoformat()
            item.status = ItemStatus.PRINTED.value

            logger.info(f"📄 Generated: {filename}")

            self._save_queue()

            return output_path

        except Exception as e:
            logger.error(f"Label generation failed: {e}")
            item.status = ItemStatus.ERROR.value
            return None

    def print_selected(
        self, indices: List[int], batch_number: str = None
    ) -> Dict[str, Any]:
        """
        Generate labels for selected items from the queue.

        Args:
            indices: List of queue indices to print (1-based)
            batch_number: Optional batch number to apply

        Returns:
            Results summary
        """
        results = {"success": [], "failed": [], "skipped": []}

        pending = self.queue.get_pending()

        for idx in indices:
            if idx < 1 or idx > len(pending):
                results["skipped"].append(f"Invalid index: {idx}")
                continue

            item = pending[idx - 1]

            if not item.ghs_matched:
                results["skipped"].append(f"{item.item_code}: No GHS data")
                continue

            # Generate label (multiple copies if needed)
            for copy_num in range(item.labels_to_print):
                output = self.generate_label(item, batch_number)

                if output:
                    results["success"].append(
                        {
                            "item_code": item.item_code,
                            "description": item.description,
                            "file": output,
                        }
                    )
                else:
                    results["failed"].append(item.item_code)

        return results

    def print_all_matched(self, batch_number: str = None) -> Dict[str, Any]:
        """
        Generate labels for all matched items.

        Args:
            batch_number: Optional batch number

        Returns:
            Results summary
        """
        matched = [i for i in self.queue.items if i.status == ItemStatus.MATCHED.value]

        if not matched:
            logger.info("No matched items to print")
            return {"success": [], "failed": [], "skipped": []}

        indices = list(range(1, len(self.queue.get_pending()) + 1))
        return self.print_selected(indices, batch_number)

    def get_queue_summary(self) -> Dict[str, Any]:
        """Get a summary of the current queue status."""
        items = self.queue.items

        return {
            "total": len(items),
            "pending": len([i for i in items if i.status == ItemStatus.PENDING.value]),
            "matched": len([i for i in items if i.status == ItemStatus.MATCHED.value]),
            "no_ghs_data": len(
                [i for i in items if i.status == ItemStatus.NO_GHS_DATA.value]
            ),
            "printed": len([i for i in items if i.status == ItemStatus.PRINTED.value]),
            "errors": len([i for i in items if i.status == ItemStatus.ERROR.value]),
        }

    def display_queue(self):
        """Display the current queue in a formatted table."""
        pending = self.queue.get_pending()

        if not pending:
            print("\n📭 Queue is empty")
            return

        print(f"\n📋 PRINT QUEUE ({len(pending)} items)")
        print("=" * 100)
        print(
            f"{'#':<4} {'Order':<8} {'Item Code':<15} {'Description':<30} {'Qty':<8} {'Status':<12} {'GHS':<5}"
        )
        print("-" * 100)

        for i, item in enumerate(pending, 1):
            ghs = "✅" if item.ghs_matched else "❌"
            status = item.status.upper()
            desc = (
                item.description[:28] + ".."
                if len(item.description) > 30
                else item.description
            )

            print(
                f"{i:<4} {item.order_number:<8} {item.item_code:<15} {desc:<30} {item.quantity:<8} {status:<12} {ghs:<5}"
            )

        print("=" * 100)

    def clear_queue(self):
        """Clear all items from the queue."""
        self.queue = PrintQueue()
        self._save_queue()
        logger.info("Queue cleared")

    def clear_printed(self):
        """Remove printed items from the queue."""
        self.queue.items = [
            i for i in self.queue.items if i.status != ItemStatus.PRINTED.value
        ]
        self._save_queue()
        logger.info("Printed items removed from queue")

    def disconnect(self):
        """Clean up connections."""
        if self.sap_connector:
            self.sap_connector.disconnect()
