```python
# src/persistence/serializer.py
import json
import dataclasses # Use the dataclasses module helper

# Import your specific data classes
from src.core.data_model import NodeData, EdgeData, MultiModalData

def serialize_scene(scene_data: dict) -> Optional[str]:
    """Converts scene data (dict with lists of NodeData/EdgeData) to a JSON string."""

    # Custom serializer function to handle dataclasses
    def default_serializer(obj):
        if dataclasses.is_dataclass(obj):
            # Convert dataclass instance to dictionary
            return dataclasses.asdict(obj)
        # Add handling for other non-standard types if necessary (e.g., datetime)
        # elif isinstance(obj, datetime.datetime):
        #     return obj.isoformat()
        raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

    try:
        # Pass the scene_data dict directly, default handles nested dataclasses
        return json.dumps(scene_data, indent=4, default=default_serializer)
    except TypeError as e:
        print(f"Serialization Error: {e}")
        # Optionally log the problematic object structure if possible
        return None
    except Exception as e:
        print(f"Unexpected Serialization Error: {e}")
        return None

def deserialize_scene(json_string: str) -> Optional[dict]:
    """
    Converts a JSON string back into scene data dictionary.
    Note: Currently returns dicts, dataclass reconstruction happens in scene.load_data.
    """
    try:
        # Load JSON string into Python dictionary structure
        data = json.loads(json_string)
        # Perform basic validation if needed (e.g., check for 'nodes', 'edges' keys)
        if not isinstance(data, dict) or "nodes" not in data or "edges" not in data:
             print("Error: Deserialized data missing 'nodes' or 'edges' key.")
             return None
        return data
    except json.JSONDecodeError as e:
        print(f"Deserialization Error: Invalid JSON format - {e}")
        return None
    except Exception as e:
        print(f"Unexpected Deserialization Error: {e}")
        return None

```
 
