```python
# src/ai/ai_manager.py
import os
import openai # Requires 'pip install openai'
import time # For simulating delay in worker example
import base64
import mimetypes
from PySide6.QtCore import QObject, Signal, Slot, QThread

from src.core.data_model import MultiModalData
from .prompt_builder import build_transition_prompt
from .workers import AIWorker # Import worker from its own file

# Use dotenv if storing key in .env (pip install python-dotenv)
# from dotenv import load_dotenv
# load_dotenv()

class AIManager:
    """
    Manages interactions with AI models, including asynchronous requests.
    """
    def __init__(self, config):
        self.config = config
        self.api_key = os.getenv('OPENAI_API_KEY', config.get('API', 'OPENAI_API_KEY', fallback=None))
        self.client = None
        self.default_model = config.get('API', 'DEFAULT_MODEL', fallback='gpt-3.5-turbo')

        if not self.api_key:
            print("WARNING: OpenAI API Key not found. AI features will be disabled.")
        else:
            try:
                # Ensure you have the correct version of openai library installed (v1.x+)
                self.client = openai.OpenAI(api_key=self.api_key)
                # Test connection? Optional.
                # self.client.models.list()
                print(f"OpenAI client initialized for model: {self.default_model}")
            except ImportError:
                 print("ERROR: OpenAI library not installed (`pip install openai`). AI features disabled.")
            except Exception as e:
                print(f"ERROR: Failed to initialize OpenAI client: {e}. AI features disabled.")
                self.client = None

    def _prepare_multimodal_input_for_vision(self, data: MultiModalData) -> list:
         """ Prepares input for vision models like GPT-4 Vision. Returns list of message content parts. """
         content = []
         text_parts = []
         if data.text: text_parts.append(data.text)
         if data.structured_data: text_parts.append(f"\nStructured Data:\n{str(data.structured_data)}")
         if text_parts:
              content.append({"type": "text", "text": "\n".join(text_parts)})

         if data.image_ref: # Requires model_file_dir context to resolve path
              # TODO: This needs the model_file_dir context! Pass it down from ExecutionEngine?
              # For now, assume image_ref might be usable directly (e.g., URL or already resolved)
              image_path_or_url = data.image_ref # Placeholder - Needs proper resolution
              if image_path_or_url and image_path_or_url.startswith(('http://', 'https://')):
                   print("Info: Using image URL for AI Vision.")
                   content.append({"type": "image_url", "image_url": {"url": image_path_or_url}})
              elif image_path_or_url and os.path.exists(image_path_or_url): # Check if it's a valid path AFTER resolution
                   print(f"Info: Encoding image {os.path.basename(image_path_or_url)} for AI Vision.")
                   try:
                        mime_type, _ = mimetypes.guess_type(image_path_or_url)
                        if mime_type and mime_type.startswith("image/"):
                            with open(image_path_or_url, "rb") as image_file:
                                base64_image = base64.b64encode(image_file.read()).decode('utf-8')
                            content.append({
                                "type": "image_url",
                                "image_url": {"url": f"data:{mime_type};base64,{base64_image}", "detail": "low"} # Use low detail?
                            })
                        else:
                             print(f"Warning: Could not determine valid image type for {image_path_or_url}")
                   except Exception as e:
                        print(f"Error encoding image {image_path_or_url}: {e}")
              elif image_path_or_url:
                   print(f"Warning: Image reference '{image_path_or_url}' is not a valid URL or existing file path.")

         # TODO: Handle audio/video if model supports
         if data.audio_ref: content.append({"type": "text", "text": f"[Audio Ref: {data.audio_ref}]"})
         if data.video_ref: content.append({"type": "text", "text": f"[Video Ref: {data.video_ref}]"})

         # If no text/image, add a placeholder text part
         if not content or all(c['type'] != 'text' for c in content):
              content.insert(0, {"type": "text", "text": "(No primary text provided)"})

         return content


    def decide_next_step_async(self, current_node_label, current_node_id, node_output_data, potential_next_nodes, user_specs, model_file_dir):
        """ Builds prompt and returns worker/thread pair for async AI call. """
        if not self.client:
            print("AI Client not initialized. Cannot start async decision.")
            return None, None

        # --- Determine if multimodal input preparation is needed ---
        # TODO: Make model selection dynamic, check capabilities
        is_vision_model = "vision" in self.default_model # Simple check
        prompt_text_content = ""
        multimodal_content = []

        if is_vision_model:
             # Simpler main prompt text, details are in the multimodal content
             prompt_text_content = build_transition_prompt(
                 current_node_label,
                 "(See multimodal input for output data details)", # Placeholder text
                 potential_next_nodes,
                 user_specs
             )
             # Prepare the multimodal parts (needs model_file_dir for path resolution!)
             multimodal_content = self._prepare_multimodal_input_for_vision(node_output_data)
             # Ensure the main instruction text is added as a text part
             multimodal_content.insert(0, {"type": "text", "text": prompt_text_content})
        else:
             # Use text-based preparation for standard LLMs
             output_text = self._prepare_multimodal_input_text_summary(node_output_data, model_file_dir)
             prompt_text_content = build_transition_prompt(
                 current_node_label,
                 output_text,
                 potential_next_nodes,
                 user_specs
             )
             multimodal_content = None # No separate multimodal parts


        # Create worker and thread
        thread = QThread()
        # Pass necessary arguments to the worker
        worker = AIWorker(self.client, self.default_model, prompt_text_content, multimodal_content, potential_next_nodes)
        worker.moveToThread(thread)

        # Connect signals for cleanup
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        # Connect the thread's started signal to the worker's run slot
        thread.started.connect(worker.run)

        print(f"    AI Manager: Created async worker for transition from '{current_node_label}'.")
        return worker, thread


    def _prepare_multimodal_input_text_summary(self, data: MultiModalData, model_file_dir: Optional[str]) -> str:
         """ Basic conversion of multimodal data to a text summary for non-vision models. """
         parts = []
         if data.text: parts.append(f"Text: {data.text}")
         if data.image_ref: parts.append(f"Image Reference: {data.image_ref} [Content not directly viewable]")
         if data.audio_ref: parts.append(f"Audio Reference: {data.audio_ref} [Content not directly viewable]")
         if data.video_ref: parts.append(f"Video Reference: {data.video_ref} [Content not directly viewable]")
         if data.structured_data: parts.append(f"Structured Data: {str(data.structured_data)}")
         if data.generic_url: parts.append(f"URL Reference: {data.generic_url}")
         return "\n".join(parts) if parts else "(No specific output data)"
```
 
