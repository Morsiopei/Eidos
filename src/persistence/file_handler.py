```python
# src/persistence/file_handler.py
from PySide6.QtWidgets import QFileDialog, QMessageBox
import os
import json # For specific error catching

from src.persistence.serializer import serialize_scene, deserialize_scene

def save_file_dialog(parent, scene_data, current_filepath=None, default_dir=""):
    """
    Opens save dialog, serializes data, and writes to file.
    Returns the saved filepath or None if cancelled/error.
    """
    if not default_dir: default_dir = os.path.expanduser("~")
    suggested_path = current_filepath or os.path.join(default_dir, "untitled_eidos_model.json")

    filepath, selected_filter = QFileDialog.getSaveFileName(
        parent,
        "Save Eidos Model",
        suggested_path,
        "Eidos Model Files (*.json);;All Files (*)"
    )

    if filepath:
        # Ensure the extension is .json if filter was selected or no extension given
        if not filepath.lower().endswith(".json") and selected_filter.startswith("Eidos"):
             filepath += ".json"

        print(f"Attempting to save to: {filepath}")
        json_data = serialize_scene(scene_data)
        if json_data:
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(json_data)
                print(f"Scene saved successfully to {filepath}")
                return filepath # Return the path saved to
            except IOError as e:
                errmsg = f"Could not save file:\n{e}"
                print(f"Error saving file: {errmsg}")
                QMessageBox.critical(parent, "Save Error", errmsg)
            except Exception as e: # Catch other potential errors
                 errmsg = f"An unexpected error occurred during saving:\n{e}"
                 print(f"Error saving file: {errmsg}")
                 QMessageBox.critical(parent, "Save Error", errmsg)
        else:
             errmsg = "Failed to serialize scene data. Check console for details."
             print(f"Error: {errmsg}")
             QMessageBox.critical(parent, "Save Error", errmsg)

    return None # No path saved or error occurred

def load_file_dialog(parent, default_dir=""):
    """
    Opens load dialog, reads file, and deserializes data.
    Returns (scene_data, filepath) tuple or (None, None) if cancelled/error.
    """
    if not default_dir: default_dir = os.path.expanduser("~")
    filepath, _ = QFileDialog.getOpenFileName(
        parent,
        "Load Eidos Model",
        default_dir,
        "Eidos Model Files (*.json);;All Files (*)"
    )

    if filepath:
        print(f"Attempting to load from: {filepath}")
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                json_string = f.read()

            scene_data = deserialize_scene(json_string)

            if scene_data:
                print(f"Scene loaded successfully from {filepath}")
                return scene_data, filepath # Return data and path
            else:
                # Deserialization handled error reporting internally? Or report here?
                errmsg = "Failed to parse the file content. Check console."
                print(f"Error: {errmsg}")
                QMessageBox.critical(parent, "Load Error", errmsg)

        except FileNotFoundError:
            errmsg = f"File not found:\n{filepath}"
            print(f"Error: {errmsg}")
            QMessageBox.critical(parent, "Load Error", errmsg)
        except IOError as e:
            errmsg = f"Could not read file:\n{e}"
            print(f"Error loading file: {errmsg}")
            QMessageBox.critical(parent, "Load Error", errmsg)
        except json.JSONDecodeError as e:
            errmsg = f"Invalid JSON format in file:\n{e}"
            print(f"Deserialization Error: {errmsg}")
            QMessageBox.critical(parent, "Load Error", errmsg)
        except Exception as e: # Catch other potential errors
            errmsg = f"An unexpected error occurred during loading:\n{e}"
            print(f"Error loading file: {errmsg}")
            QMessageBox.critical(parent, "Load Error", errmsg)

    return None, None # No data loaded or error occurred

```
 
