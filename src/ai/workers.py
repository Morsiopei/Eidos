```python
# src/ai/workers.py
import time
from PySide6.QtCore import QObject, Signal, Slot
import openai # Import needed library here too

class AIWorker(QObject):
    """ Worker object to run AI API calls in a separate thread. """
    result_ready = Signal(list)      # Emits list of chosen next node IDs
    error_occurred = Signal(str)     # Emits error message string
    finished = Signal()              # Emitted when run() completes

    def __init__(self, client, model_name, prompt_text, multimodal_content=None, potential_nodes=None):
        super().__init__()
        self.client = client # Pass the initialized OpenAI client
        self.model_name = model_name
        self.prompt_text = prompt_text # The core text instructions
        self.multimodal_content = multimodal_content # List for vision models, None otherwise
        self.potential_nodes = potential_nodes or {} # Needed for parsing/validation
        self._is_cancelled = False

    @Slot()
    def run(self):
        """ Executes the AI query and emits results/errors. """
        start_time = time.time()
        chosen_ids = []
        error_msg = None

        if not self.client:
             error_msg = "AI client not available in worker."
        elif self._is_cancelled:
             error_msg = "Operation cancelled before starting."
        else:
            try:
                print(f"    AI Worker: Starting query for model {self.model_name}...")
                # --- Construct Messages ---
                messages = []
                system_prompt = ("You are a simulation controller deciding the next step in a process flow graph. "
                                 "Respond ONLY with the chosen node ID(s) separated by commas, or NONE.")
                messages.append({"role": "system", "content": system_prompt})

                if self.multimodal_content:
                     # Vision model: content includes text and potentially images
                     # The prompt_text is already included within multimodal_content[0] usually
                     messages.append({"role": "user", "content": self.multimodal_content})
                     print(f"    AI Worker: Using multimodal input structure.")
                else:
                     # Text model: content is just the prompt text
                     messages.append({"role": "user", "content": self.prompt_text})
                     print(f"    AI Worker: Using text-only input.")
                     print(f"    AI Worker Prompt (first 300 chars): {self.prompt_text[:300]}...")


                # --- Make the API Call ---
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    max_tokens=50, # Keep response focused on IDs
                    temperature=0.1 # Low temp for more deterministic ID selection
                )
                ai_response_text = response.choices[0].message.content.strip()
                duration = time.time() - start_time
                print(f"    AI Worker: Query successful ({duration:.2f}s). Raw Response: '{ai_response_text}'")

                # --- Parse Response ---
                if not ai_response_text or ai_response_text.upper() == "NONE":
                    chosen_ids = []
                else:
                    # Simple comma separation
                    raw_chosen_items = [item.strip() for item in ai_response_text.split(',') if item.strip()]
                    valid_potential_ids = set(self.potential_nodes.keys())

                    # Validate against potential node IDs passed to the worker
                    validated_ids = []
                    unknown_items = []
                    for item in raw_chosen_items:
                         # Check if the item returned by AI is a valid potential ID
                         if item in valid_potential_ids:
                             if item not in validated_ids: # Avoid duplicates
                                 validated_ids.append(item)
                         else:
                             unknown_items.append(item)

                    if unknown_items:
                        print(f"    Warning: AI suggested unknown/invalid IDs: {unknown_items}")

                    chosen_ids = validated_ids # Return only valid, unique IDs

            except openai.APIConnectionError as e:
                 error_msg = f"OpenAI API Connection Error: {e}"
            except openai.RateLimitError as e:
                 error_msg = f"OpenAI Rate Limit Error: {e}"
            except openai.APIStatusError as e:
                 error_msg = f"OpenAI API Status Error (HTTP {e.status_code}): {e.response}"
            except openai.APIError as e:
                 error_msg = f"OpenAI API Error: {e}"
            except Exception as e:
                 error_msg = f"AI Worker Error during API call or parsing: {e}"

            if error_msg:
                 print(f"    {error_msg}")

        # --- Emit Signals ---
        if not self._is_cancelled:
            if error_msg:
                self.error_occurred.emit(error_msg)
            else:
                self.result_ready.emit(chosen_ids) # Emit the list of chosen IDs

        self.finished.emit() # Signal completion

    def cancel(self):
        """ Sets the cancellation flag. """
        print("    AI Worker: Cancellation requested.")
        self._is_cancelled = True

``` 
