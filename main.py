```python
# main.py - Main application entry point
import sys
from PySide6.QtWidgets import QApplication
from src.ui.main_window import MainWindow
from src.core.config_manager import load_config

def main():
    # Configure high DPI scaling (optional but recommended)
    try:
        from PySide6.QtCore import Qt, QCoreApplication
        QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling)
        QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)
    except Exception as e:
        print(f"Could not set High DPI attributes: {e}")


    # Load configuration early
    config = load_config() # Uses default path 'settings.ini'

    # Create the application instance
    # Pass sys.argv for command line arguments Qt might use
    app = QApplication(sys.argv)
    app.setOrganizationName("YourCompanyNameOrName") # Optional: for QSettings etc.
    app.setApplicationName("Eidos Modeler")

    # Create and show the main window
    window = MainWindow(config=config) # Pass config
    window.show()

    # Start the Qt event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

``` 
