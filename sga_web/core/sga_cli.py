#!/usr/bin/env python3
"""
SGA - Sistema de Gestión de Almacén
Command Line Interface
"""

import getpass
import argparse
from datetime import datetime
import logging

from sga_controller import SGAController, OUTPUT_DIR

logger = logging.getLogger(__name__)


def interactive_mode():
    """Run the SGA controller in interactive mode."""
    print("\n" + "=" * 70)
    print("  SGA - Sistema de Gestión de Almacén")
    print("  SAP Business One → GHS Label Integration")
    print("=" * 70)

    # Get credentials
    print("\n🔐 SAP HANA Connection")
    username = input("Username: ").strip()
    password = getpass.getpass("Password: ")

    # Initialize controller
    sga = SGAController()

    try:
        # Connect to SAP
        print("\n📡 Connecting to SAP HANA...")
        sga.connect_sap(username, password)
        print("✅ Connected!")

        # Initialize label system
        sga.init_label_system()
        print("✅ Label system initialized!")

        # Main loop
        while True:
            print("\n" + "-" * 50)
            summary = sga.get_queue_summary()
            print(
                f"Queue: {summary['total']} total | {summary['matched']} matched | {summary['printed']} printed"
            )
            print("-" * 50)

            print("\nCommands:")
            print("  [1] Fetch order from SAP")
            print("  [2] View queue")
            print("  [3] Match GHS data")
            print("  [4] Print selected labels")
            print("  [5] Print all matched labels")
            print("  [6] Clear printed items")
            print("  [7] Clear entire queue")
            print("  [Q] Quit")

            choice = input("\nChoice: ").strip().upper()

            if choice == "1":
                order_num = input("Enter Order Number (DocNum): ").strip()
                if order_num.isdigit():
                    items = sga.queue_order(int(order_num))
                    print(f"\n✅ Added {len(items)} items to queue")
                else:
                    print("Invalid order number")

            elif choice == "2":
                sga.display_queue()

            elif choice == "3":
                print("\n🔍 Matching items with GHS database...")
                stats = sga.match_ghs_data()
                print(f"\n✅ Matched: {stats['matched']}")
                print(f"⚠️ No GHS data: {stats['no_data']}")

            elif choice == "4":
                sga.display_queue()
                indices_str = input(
                    "\nEnter item numbers to print (e.g., 1,2,3 or 'all'): "
                ).strip()

                if indices_str.lower() == "all":
                    pending = sga.queue.get_pending()
                    indices = list(range(1, len(pending) + 1))
                else:
                    indices = [
                        int(x.strip())
                        for x in indices_str.split(",")
                        if x.strip().isdigit()
                    ]

                batch = input("Batch number (press Enter for auto): ").strip()
                if not batch:
                    batch = datetime.now().strftime("LOT-%Y%m%d-%H%M")

                print(f"\n🖨️ Generating labels with batch: {batch}")
                results = sga.print_selected(indices, batch)

                print(f"\n✅ Success: {len(results['success'])}")
                print(f"❌ Failed: {len(results['failed'])}")
                print(f"⏭️ Skipped: {len(results['skipped'])}")

                if results["success"]:
                    print(f"\n📁 Labels saved to: {OUTPUT_DIR}")

            elif choice == "5":
                batch = input("Batch number (press Enter for auto): ").strip()
                if not batch:
                    batch = datetime.now().strftime("LOT-%Y%m%d-%H%M")

                print(f"\n🖨️ Generating all matched labels with batch: {batch}")
                results = sga.print_all_matched(batch)

                print(f"\n✅ Success: {len(results['success'])}")
                print(f"❌ Failed: {len(results['failed'])}")

            elif choice == "6":
                sga.clear_printed()
                print("✅ Printed items cleared")

            elif choice == "7":
                confirm = input("Are you sure? (y/n): ").strip().lower()
                if confirm == "y":
                    sga.clear_queue()
                    print("✅ Queue cleared")

            elif choice == "Q":
                break

            else:
                print("Invalid choice")

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")

    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback

        traceback.print_exc()

    finally:
        sga.disconnect()
        print("\n👋 SGA Controller stopped")


def main():
    """Main entry point with argument handling."""
    parser = argparse.ArgumentParser(
        description="SGA - Sistema de Gestión de Almacén",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Interactive mode:
    python sga_cli.py
    
  Process single order:
    python sga_cli.py --order 10168
    
  Process multiple orders:
    python sga_cli.py --orders 10168,10169,10170
    
  Auto-print all matched items:
    python sga_cli.py --order 10168 --auto-print
        """,
    )

    parser.add_argument("--order", type=int, help="Single order number to process")
    parser.add_argument("--orders", type=str, help="Comma-separated order numbers")
    parser.add_argument(
        "--auto-print",
        action="store_true",
        help="Automatically print all matched labels",
    )
    parser.add_argument("--batch", type=str, help="Batch/lot number for labels")
    parser.add_argument("--user", type=str, help="SAP username")

    args = parser.parse_args()

    # If no arguments, run interactive mode
    if not args.order and not args.orders:
        interactive_mode()
        return

    # Command line mode
    username = args.user or input("SAP Username: ").strip()
    password = getpass.getpass("SAP Password: ")

    sga = SGAController()

    try:
        sga.connect_sap(username, password)
        sga.init_label_system()

        # Process orders
        orders = []
        if args.order:
            orders.append(args.order)
        if args.orders:
            orders.extend([int(x.strip()) for x in args.orders.split(",")])

        for order_num in orders:
            print(f"\n📦 Processing order {order_num}...")
            sga.queue_order(order_num)

        # Match GHS data
        print("\n🔍 Matching GHS data...")
        stats = sga.match_ghs_data()
        print(f"Matched: {stats['matched']} | No data: {stats['no_data']}")

        # Auto-print if requested
        if args.auto_print:
            batch = args.batch or datetime.now().strftime("LOT-%Y%m%d-%H%M")
            print(f"\n🖨️ Printing labels with batch: {batch}")
            results = sga.print_all_matched(batch)
            print(f"Generated: {len(results['success'])} labels")
            print(f"Output: {OUTPUT_DIR}")
        else:
            sga.display_queue()
            print("\nRun with --auto-print to generate labels")

    finally:
        sga.disconnect()


if __name__ == "__main__":
    main()
