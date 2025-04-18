```python
# src/core/data_model.py
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import os
import urllib.parse
import uuid # Import uuid for default ID generation

@dataclass
class MultiModalData:
    """
    Represents potentially diverse data associated with a node or passed between nodes.
    Focuses on storing references (paths, URLs) rather than embedding large data by default.
    """
    text: Optional[str] = None
    structured_data: Dict[str, Any] = field(default_factory=dict)
    image_ref: Optional[str] = None
    audio_ref: Optional[str] = None
    video_ref: Optional[str] = None
    generic_url: Optional[str] = None

    def _get_ref_type(self, ref: Optional[str]) -> Optional[str]:
        """Determines the type of reference (relative, absolute, url)."""
        if not ref: return None
        try:
            parsed = urllib.parse.urlparse(ref)
            if parsed.scheme in ['http', 'https']: return 'url'
            if parsed.scheme == 'file': return 'absolute_path' # file:/// URIs
            if os.path.isabs(ref): return 'absolute_path'
            if ref: return 'relative_path' # Assume relative if not absolute/url
        except Exception: # Handle potential parsing errors
            pass
        return None

    def _resolve_path(self, ref: Optional[str], model_file_dir: Optional[str]) -> Optional[str]:
        """Resolves a reference to a usable absolute path or URL."""
        ref_type = self._get_ref_type(ref)
        if ref_type == 'url': return ref
        if ref_type == 'absolute_path':
            # Normalize file:/// URIs if needed
            if ref.startswith('file:///'):
                try:
                    # Correctly handle path conversion from file URI
                    from urllib.request import url2pathname
                    # Remove 'file://' and decode %-escapes, handle Windows drive letters
                    path = url2pathname(ref[len('file://'):])
                    # On Windows, url2pathname might add leading / like /C:/... Remove it.
                    if os.name == 'nt' and path.startswith('/') and path[2] == ':':
                        path = path[1:]
                    return os.path.abspath(path)
                except Exception as e:
                    print(f"Warning: Failed to convert file URI '{ref}': {e}")
                    return ref # Return original URI on error
            # Simple absolute path
            return os.path.abspath(ref) # Normalize path separators
        if ref_type == 'relative_path':
            if not model_file_dir or not os.path.isdir(model_file_dir):
                print(f"Warning: Cannot resolve relative path '{ref}'. Invalid context: '{model_file_dir}'")
                return None
            try:
                abs_path = os.path.abspath(os.path.join(model_file_dir, ref))
                # Optional: Check if the resolved path actually exists?
                # if not os.path.exists(abs_path):
                #    print(f"Warning: Resolved relative path does not exist: {abs_path}")
                #    return None # Or return path anyway? Decide policy.
                return abs_path
            except Exception as e:
                print(f"Error resolving relative path '{ref}' in '{model_file_dir}': {e}")
                return None
        return None

    def get_image_path(self, model_file_dir: Optional[str]) -> Optional[str]:
        return self._resolve_path(self.image_ref, model_file_dir)

    def get_audio_path(self, model_file_dir: Optional[str]) -> Optional[str]:
        return self._resolve_path(self.audio_ref, model_file_dir)

    def get_video_path(self, model_file_dir: Optional[str]) -> Optional[str]:
        return self._resolve_path(self.video_ref, model_file_dir)

    def get_url(self) -> Optional[str]:
         return self.generic_url

    def set_media_ref(self, field_prefix: str, filepath: str, model_file_dir: Optional[str], prefer_relative: bool = True):
        """Sets media reference, converting to relative if possible/desired."""
        ref_attr = f"{field_prefix}_ref"
        if not hasattr(self, ref_attr): return

        final_ref = os.path.normpath(filepath) # Clean up path initially

        if prefer_relative and model_file_dir and os.path.isdir(model_file_dir) and os.path.isabs(final_ref):
            try:
                # Ensure both paths are absolute before calculating relpath
                abs_filepath = os.path.abspath(final_ref)
                abs_model_dir = os.path.abspath(model_file_dir)
                # Check if paths are on the same drive (Windows)
                if os.path.splitdrive(abs_filepath)[0] == os.path.splitdrive(abs_model_dir)[0]:
                     relative_path = os.path.relpath(abs_filepath, start=abs_model_dir)
                     # Basic check: avoid overly complex relative paths like ../../../...
                     if not relative_path.startswith(('..', os.sep)): # Simple check if it's likely within or below
                          final_ref = relative_path
                     else:
                           print(f"Info: Relative path '{relative_path}' seems too complex. Using absolute.")
                           final_ref = abs_filepath # Use clean absolute path
                else:
                    print(f"Info: File '{abs_filepath}' is on a different drive than model '{abs_model_dir}'. Using absolute path.")
                    final_ref = abs_filepath # Use clean absolute path

            except ValueError: # Cannot make relative (e.g., should not happen if drives checked)
                print(f"Info: Could not make path '{filepath}' relative to '{model_file_dir}'. Using absolute path.")
                final_ref = os.path.abspath(final_ref)
            except Exception as e:
                print(f"Error calculating relative path: {e}. Using provided path.")
                final_ref = os.path.normpath(filepath) # Use original cleaned path

        elif os.path.isabs(final_ref):
             # If not preferring relative, still ensure it's a clean absolute path
             final_ref = os.path.abspath(final_ref)

        setattr(self, ref_attr, final_ref)
        print(f"Set {ref_attr} to: {final_ref} (Type: {self._get_ref_type(final_ref)})")

    def set_image_ref(self, filepath: str, model_file_dir: Optional[str], prefer_relative: bool = True):
        self.set_media_ref('image', filepath, model_file_dir, prefer_relative)

    def set_audio_ref(self, filepath: str, model_file_dir: Optional[str], prefer_relative: bool = True):
        self.set_media_ref('audio', filepath, model_file_dir, prefer_relative)

    def set_video_ref(self, filepath: str, model_file_dir: Optional[str], prefer_relative: bool = True):
        self.set_media_ref('video', filepath, model_file_dir, prefer_relative)


# Using default_factory for unique IDs
def generate_uuid():
    return str(uuid.uuid4())

@dataclass
class NodeData:
    """ Holds the data associated with a node in the model. """
    id: str = field(default_factory=generate_uuid)
    label: str = "Node"
    position: tuple[float, float] = (0.0, 0.0)
    process_code: str = "# Assign output to _result\n# Access input via input_data\n_result = input_data"
    transition_specs: str = ""
    node_type: str = "Default"
    display_properties: Dict[str, Any] = field(default_factory=lambda: {"color": "skyblue", "radius": 40})
    custom_data: MultiModalData = field(default_factory=MultiModalData)

@dataclass
class EdgeData:
    """ Holds the data associated with an edge (link) in the model. """
    id: str = field(default_factory=generate_uuid)
    start_node_id: str = "" # Must be set
    end_node_id: str = ""   # Must be set
    edge_type: str = "Directed"
    display_properties: Dict[str, Any] = field(default_factory=lambda: {"color": "black", "width": 2})
    condition: Optional[str] = None # Optional simple condition string
``` 
