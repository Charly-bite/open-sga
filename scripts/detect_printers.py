import sys

try:
    import win32print
    import win32ui
    import win32con
except ImportError:
    print("Error: El módulo 'pywin32' no está instalado.")
    print("El script requiere esta librería para consultar las impresoras locales.")
    print("\nPor favor instálalo ejecutando en tu entorno virtual:")
    print("    pip install pywin32")
    input("\nPresiona ENTER para salir...")
    sys.exit(1)


def detect_printer_dpi():
    """
    Enumera todas las impresoras locales e intenta obtener su resolución (DPI).
    """
    print("Buscando impresoras configuradas localmente...\n")
    try:
        printers = win32print.EnumPrinters(
            win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
        )
    except Exception as e:
        print(f"Error enumerando impresoras: {e}")
        return

    if not printers:
        print("No se encontraron impresoras instaladas en este sistema.")
        return

    for printer in printers:
        flags, description, name, comment = printer
        print(f"Impresora: {name}")

        try:
            # Crear Device Context (DC) para la impresora
            hdc = win32ui.CreateDC()
            hdc.CreatePrinterDC(name)

            # Consultar capacidades de dispositivo
            dpi_x = hdc.GetDeviceCaps(win32con.LOGPIXELSX)
            dpi_y = hdc.GetDeviceCaps(win32con.LOGPIXELSY)

            print(f"  - Resolución reportada: {dpi_x}x{dpi_y} DPI")

            if dpi_x == 203:
                print("  - Recomendación SGA Web: Establece 'Print DPI' a 203.")
            elif dpi_x == 300:
                print("  - Recomendación SGA Web: Establece 'Print DPI' a 300.")
            elif dpi_x >= 600:
                print("  - Recomendación SGA Web: Establece 'Print DPI' a 600.")
            else:
                print(
                    f"  - Recomendación SGA Web: Establece 'Print DPI' al más cercano ({dpi_x})."
                )

            # Limpiar DC
            hdc.DeleteDC()
        except Exception:
            print("  - No se pudo consultar la resolución de esta impresora.")

        print("-" * 50)


if __name__ == "__main__":
    print("=" * 60)
    print(" SGA Web - Analizador de Resolución de Impresoras (DPI)")
    print("=" * 60)
    print("Este script analiza las impresoras instaladas en Windows")
    print("para determinar la calidad de impresión (DPI) nativa correcta.")
    print("=" * 60)
    print()

    detect_printer_dpi()

    print("\nPuedes configurar la resolución detectada en la interfaz web.")
    print("O ve a 'Dispositivos e impresoras' > 'Preferencias' si crees")
    print("que el driver está limitando la resolución artificialmente.")
    input("\nPresiona ENTER para cerrar el analizador...")
