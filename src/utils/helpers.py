```python
# src/utils/helpers.py
import sys
import os

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
        # print(f"Accessing resource from MEIPASS: {base_path}") # Debugging line
    except Exception:
        # _MEIPASS not defined, so running in normal Python environment
        # Assume helpers.py is in src/utils, go up two levels for project root
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        # print(f"Accessing resource from development path: {base_path}") # Debugging line

    return os.path.join(base_path, relative_path)

# Add other general utility functions here if needed
# Example: Function to generate unique IDs (though data models use uuid directly now)
# import uuid
# def generate_id():
#     return str(uuid.uuid4())

``` 
