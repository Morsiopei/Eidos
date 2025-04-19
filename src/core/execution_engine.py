 ```python
# src/core/execution_engine.py
import time
import traceback
from PySide6.QtCore import QObject, Slot, QTimer, QThread # Added QObject for potential signals later
from PySide6.QtWidgets import QMessageBox # For error dialogs

from src.core.data_model import MultiModalData
from src.ai.ai_manager import AIManager # Need this to call AI

# --- Sandboxing Imports ---
try:
    from RestrictedPython import compile_restricted, safe_builtins, utility_builtins
    from RestrictedPython.Guards import guarded_iter_unpack_sequence, guarded_unpack_sequence
    _RESTRICTED_PYTHON_AVAILABLE = True
except ImportError:
    print("WARNING: RestrictedPython not found (`pip install RestrictedPython`). Sandboxing disabled - VERY UNSAFE!")
    _RESTRICTED_PYTHON_AVAILABLE = False

# --- Default Safe Globals for RestrictedPython ---
def safe_log(*args, **kwargs):
    """A safe logging function for restricted code."""
    # Limit message length? Sanitize input? Convert args to string safely?
    str_args = [str(a) for a in args]
    str_kwargs = {k: str(v) for k, v in kwargs.items()}
    print("RestrictedLog:", *str_args, **str_kwargs)

DEFAULT_SAFE_GLOBALS = {
    "__builtins__": safe_builtins if _RESTRICTED_PYTHON_AVAILABLE else {},
    "_print_": safe_log,
    "_getiter_": guarded_iter_unpack_sequence if _RESTRICTED_PYTHON_AVAILABLE else lambda x: iter(x), # Fallback iter
    "_iter_unpack_sequence_": guarded_unpack_sequence if _RESTRICTED_PYTHON_AVAILABLE else None, # No easy fallback
    "True": True, "False": False, "None": None,
    # Add specific safe math functions if needed, avoid importing 'math' directly
    # 'safe_pow': pow, # Example, if pow is deemed safe enough
}
# --- End Sandboxing Setup ---


class ExecutionEngine(QObject): # Inherit QObject to use signals if needed later
    # Signal to indicate execution has finished (successfully or with error)
    executionFinished = Signal()
    # Signal to potentially update UI about current node (optional)
    # currentNodeChanged = Signal(str) # Emits ID of current node

    def __init__(self, scene, ai_manager: AIManager, config):
        super().__init__() # Initialize QObject
        self.scene = scene # Reference to DiagramScene
        self.ai_manager = ai_manager
        self.config = config
        self.is_running = False
        self.stop_requested = False
        self.max_depth = config.getint('Defaults', 'MAX_EXECUTION_DEPTH', fallback=25)

        # State for asynchronous AI calls
        self.execution_paused = False
        self.paused_tasks = {} # Store state for multiple concurrent pauses {node_id: state_tuple}

        # Active AI Threads/Workers (manage cleanup)
        self.active_ai_threads = {} # {worker_obj: thread_obj}

    def run_flow(self, start_node_item):
        """Starts the execution flow from the given node."""
        if self.is_running:
            print("Execution already in progress.")
            self._show_error_dialog("Execution Error", "An execution flow is already running.")
            return
        if not start_node_item:
            print("Error: Cannot start flow without a start node.")
            return

        # Reset state
        self.is_running = True
        self.stop_requested = False
        self.execution_paused = False
        self.paused_tasks.clear()
        self._cleanup_threads() # Clean up any previous threads

        print("--- Starting Execution Flow ---")
        try:
            # Initial data: Use the node's own custom_data as starting point
            initial_data = start_node_item.node_data.custom_data
            if not isinstance(initial_data, MultiModalData):
                 initial_data = MultiModalData() # Ensure it's the right type
                 print("Warning: Start node had invalid custom_data, using empty.")

            # Begin recursive execution
            self._execute_step(start_node_item, initial_data, visited=set(), depth=0)

        except Exception as e:
            print(f"!!! Execution Error during setup: {e}")
            traceback.print_exc()
            self._show_error_dialog("Execution Error", f"An unexpected error occurred during setup: {e}")
            self._finish_execution() # Ensure cleanup on error

        # If the very first step didn't pause, finish immediately
        if self.is_running and not self.execution_paused:
             self._check_and_finish_execution()

    def stop_execution(self):
        """Requests the execution flow to stop gracefully."""
        if not self.is_running:
            return
        print("--- Requesting Execution Stop ---")
        self.stop_requested = True

        # Cancel any pending AI tasks
        for worker, thread in list(self.active_ai_threads.items()):
             if thread.isRunning():
                 print(f"    Requesting cancellation for AI worker...")
                 if hasattr(worker, 'cancel'):
                      worker.cancel()
                 # Don't wait here, let finished signal handle thread cleanup

        # If execution wasn't paused, mark as finished immediately
        if not self.execution_paused:
             self._finish_execution()
        # If paused, the flow will stop when AI task finishes or errors out

    def _execute_step(self, current_node_item, input_data, visited, depth):
        """Recursive method to execute a single node step."""
        if not self.is_running or self.stop_requested:
             self._check_and_finish_execution() # Stop requested or finished elsewhere
             return

        node_data = current_node_item.node_data
        node_id = node_data.id

        # --- Check stopping conditions ---
        if node_id in visited:
            print(f"{'  ' * depth}Stopping at '{node_data.label}': Already Visited in this path.")
            self._check_and_finish_execution()
            return
        if depth > self.max_depth:
            print(f"{'  ' * depth}Stopping at '{node_data.label}': Max Depth ({self.max_depth}) Reached.")
            self._check_and_finish_execution()
            return

        visited.add(node_id)
        # self.currentNodeChanged.emit(node_id) # Optional signal for UI highlight

        print(f"{'  ' * depth}Executing Node: '{node_data.label}' ({node_id})")
        if isinstance(input_data, MultiModalData):
             # Avoid printing huge base64 data etc.
             print(f"{'  ' * depth}  Input: Text='{input_data.text}', Struct={input_data.structured_data}, "
                   f"Img='{input_data.image_ref}', Audio='{input_data.audio_ref}', Video='{input_data.video_ref}'")
        else:
             print(f"{'  ' * depth}  Input Data: {input_data}") # Fallback

        # --- 1. Execute Node's Internal Process (Sandboxed) ---
        node_output_data = MultiModalData(structured_data={"error": "Node process failed or did not produce output"}) # Default
        execution_globals = DEFAULT_SAFE_GLOBALS.copy() # Use sandboxing globals

        try:
            execution_globals['input_data'] = input_data # Inject input
            execution_globals['_result'] = None # User must assign here

            if _RESTRICTED_PYTHON_AVAILABLE:
                byte_code = compile_restricted(node_data.process_code, '<node_process>', 'exec')
                exec(byte_code, execution_globals, execution_globals)
            else: # Fallback to UNSAFE eval if RestrictedPython not installed
                print("!!! RUNNING UNSAFE EVAL !!!")
                # Try to make eval slightly safer by only allowing expressions? No, need assignment.
                # This is highly insecure.
                exec(node_data.process_code, execution_globals, execution_globals)


            raw_result = execution_globals.get('_result', None)
            # Convert result to MultiModalData
            if isinstance(raw_result, MultiModalData): node_output_data = raw_result
            elif isinstance(raw_result, dict): node_output_data = MultiModalData(**raw_result)
            elif raw_result is not None: node_output_data = MultiModalData(text=str(raw_result))
            else:
                 print(f"{'  ' * depth}  Warning: Node '{node_data.label}' process did not assign to '_result'.")
                 node_output_data = MultiModalData() # Empty output is valid

            print(f"{'  ' * depth}  Node Output: (Text='{node_output_data.text}', Struct={node_output_data.structured_data}, ...)")

        except Exception as e:
            err_type = type(e).__name__
            print(f"{'  ' * depth}  !!! Error in node process '{node_data.label}' ({err_type}): {e}")
            node_output_data = MultiModalData(structured_data={"error": f"{err_type}: {e}"})
            # Optionally stop execution on node error? Or continue? Continue for now.

        # --- Check for stop request AFTER node execution ---
        if self.stop_requested:
             self._finish_execution()
             return

        # --- 2. AI Decides Next Step(s) (Asynchronously) ---
        outgoing_edges = current_node_item.edges_out
        if not outgoing_edges:
            print(f"{'  ' * depth}Node '{node_data.label}' is terminal.")
            self._check_and_finish_execution()
            return # End this path

        try:
            potential_next = {}
            for edge in outgoing_edges:
                if edge.end_item:
                     end_node = edge.end_item.node_data
                     potential_next[end_node.id] = { # Use ID as key for AI result mapping
                         "label": end_node.label,
                         "description": end_node.process_code[:100] + "...",
                         "type": end_node.node_type
                     }

            print(f"{'  ' * depth}  Requesting AI decision (async) for '{node_data.label}'...")

            # Get model file directory context if available (needed for resolving media paths)
            model_dir = self.scene.get_model_directory() # Scene needs this method

            worker, thread = self.ai_manager.decide_next_step_async(
                current_node_label=node_data.label,
                current_node_id=node_data.id,
                node_output_data=node_output_data, # Pass the result from step 1
                potential_next_nodes=potential_next,
                user_specs=node_data.transition_specs,
                model_file_dir=model_dir # Pass context
            )

            if worker and thread:
                 # --- Pause This Path ---
                 self.execution_paused = True
                 # Store state needed to resume *this specific path*
                 self.paused_tasks[node_id] = (current_node_item, node_output_data, visited, depth)

                 # Connect signals for this specific task
                 # Use lambda to pass identifier back if needed, or rely on sender()
                 worker.result_ready.connect(self._handle_ai_result)
                 worker.error_occurred.connect(self._handle_ai_error)
                 worker.finished.connect(lambda w=worker: self._ai_task_finished(w)) # Track finished tasks

                 # Store thread/worker references for potential cancellation/cleanup
                 self.active_ai_threads[worker] = thread

                 # Start the AI task
                 thread.start()
                 print(f"{'  ' * depth}  AI task started for node {node_id}. Execution path paused.")
                 # --- Stop processing this path until AI result ---

            else:
                 print(f"{'  ' * depth}  AI task could not be started. Stopping this execution path.")
                 self._check_and_finish_execution()

        except Exception as e:
             print(f"{'  ' * depth}  !!! Error during AI transition setup: {e}")
             traceback.print_exc()
             self._check_and_finish_execution()

    # --- Slot to handle successful AI result ---
    @Slot(list)
    def _handle_ai_result(self, chosen_node_ids):
        worker = self.sender() # Get the worker that emitted the signal
        if not worker or not self.is_running:
            print("Received AI result but sender unknown or execution stopped.")
            return

        # Find the paused state associated with this worker (need to link worker back to node_id)
        # This requires a more robust way than assuming only one pause...
        # For simplicity, let's assume the last paused node's state corresponds,
        # OR modify worker/signal to pass back the originating node_id.
        # Let's modify worker to store originating node_id and pass it back.
        # --- Modification required in AIWorker/AIManager to pass originating node_id ---
        # --- Assuming chosen_node_ids is accompanied by originating_node_id ---
        # Temp solution: Find which paused task it might be (less robust)
        originating_node_id = None
        for task_id, state_tuple in self.paused_tasks.items():
             # Need a way to know which worker corresponds to which task_id
             # Add worker reference to paused_tasks?
             # Let's assume for now we retrieve the correct state
             # This part NEEDS refinement for multiple concurrent AI calls
             if self.active_ai_threads.get(worker): # Check if this worker is active
                  originating_node_id = task_id # Assume it's this one
                  break

        if not originating_node_id or originating_node_id not in self.paused_tasks:
             print(f"Error: Could not find paused state for AI result {chosen_node_ids}.")
             return # Or handle differently

        # Retrieve paused state
        paused_node_item, paused_output_data, paused_visited, paused_depth = self.paused_tasks.pop(originating_node_id)
        print(f"{'  ' * paused_depth}  AI Result Received for '{paused_node_item.node_data.label}': {chosen_node_ids}")

        # --- Resume Execution ---
        # self.execution_paused is True if other tasks are still paused
        self.execution_paused = len(self.paused_tasks) > 0

        if self.stop_requested:
             print(f"{'  ' * paused_depth} Stop requested, not resuming path from '{paused_node_item.node_data.label}'.")
             self._check_and_finish_execution()
             return

        next_node_items_to_execute = []
        # Find corresponding NodeItem objects from IDs
        outgoing_edges = paused_node_item.edges_out
        for edge in outgoing_edges:
            if edge.end_item and edge.end_item.get_id() in chosen_node_ids:
                 next_node_items_to_execute.append(edge.end_item)

        if not next_node_items_to_execute:
             print(f"{'  ' * paused_depth}No valid next step chosen by AI or available from '{paused_node_item.node_data.label}'.")

        # Recursively Execute Chosen Next Nodes
        resumed_count = 0
        for next_node_item in next_node_items_to_execute:
            print(f"{'  ' * paused_depth}Resuming execution -> '{next_node_item.node_data.label}'")
            # Pass the output of the paused node as input to the next
            self._execute_step(next_node_item,
                               paused_output_data, # Data produced before pause
                               paused_visited.copy(), # Pass copy of visited set
                               paused_depth + 1)
            resumed_count += 1

        if resumed_count == 0 and next_node_items_to_execute:
             print(f"{'  ' * paused_depth}AI chose paths, but none could be executed further from '{paused_node_item.node_data.label}'.")

        # Check if overall execution finished after this path potentially ended
        self._check_and_finish_execution()

    # --- Slot to handle AI error ---
    @Slot(str)
    def _handle_ai_error(self, error_msg):
        worker = self.sender()
        if not worker or not self.is_running: return

        # Find originating task (needs refinement as above)
        originating_node_id = None
        for task_id in list(self.paused_tasks.keys()): # Iterate over copy
              # Need better mapping worker -> task_id
              if self.active_ai_threads.get(worker):
                  originating_node_id = task_id
                  break

        if originating_node_id and originating_node_id in self.paused_tasks:
             _, _, _, paused_depth = self.paused_tasks.pop(originating_node_id)
             print(f"{'  ' * paused_depth}!!! AI Task Error: {error_msg}")
             self._show_error_dialog("AI Error", error_msg)
             self.execution_paused = len(self.paused_tasks) > 0 # Update paused status
             print(f"{'  ' * paused_depth}Stopping execution path due to AI error.")
        else:
            print(f"Received AI error, but couldn't find originating paused task: {error_msg}")

        # Always check if overall execution might be finished after an error
        self._check_and_finish_execution()


    # --- Slot to clean up finished AI threads ---
    @Slot()
    def _ai_task_finished(self, worker=None):
        # Get worker that finished (sender() might work if connected directly)
        actual_worker = worker or self.sender()
        if actual_worker in self.active_ai_threads:
            print(f"    Cleaning up finished AI task/thread for worker {id(actual_worker)}...")
            thread = self.active_ai_threads.pop(actual_worker)
            # Thread/worker should deleteLater via their own finished signals
        else:
             # This might happen if task finished after stop_execution or error handling already cleaned up
             pass
             # print(f"Warning: Received finished signal from unknown or already cleaned worker {id(actual_worker)}")

        # Check if this was the last pending task
        self._check_and_finish_execution()


    def _check_and_finish_execution(self):
         """Checks if execution should finish (no running threads, no paused tasks)."""
         # Only finish if running, not paused, and no active AI threads remain
         if self.is_running and not self.execution_paused and not self.active_ai_threads:
              # Double check paused_tasks is also empty
              if not self.paused_tasks:
                   self._finish_execution()


    def _finish_execution(self):
         """Cleans up and marks execution as finished."""
         if not self.is_running: return # Already stopped
         print("--- Execution Flow Finished ---")
         self.is_running = False
         self.stop_requested = False
         self.execution_paused = False
         self.paused_tasks.clear()
         self._cleanup_threads()
         self.executionFinished.emit() # Emit signal

    def _cleanup_threads(self):
         """Force cleanup of any remaining tracked threads."""
         print("Cleaning up any residual AI threads...")
         for worker, thread in list(self.active_ai_threads.items()):
              if thread.isRunning():
                   print(f"    Forcibly quitting AI thread for worker {id(worker)}...")
                   if hasattr(worker, 'cancel'): worker.cancel()
                   thread.quit()
                   thread.wait(500) # Short wait
              # Remove from tracking dict
              del self.active_ai_threads[worker]


    def _show_error_dialog(self, title, message):
         """ Safely shows an error message box. """
         try:
              parent_window = None
              if self.scene and self.scene.views():
                   parent_window = self.scene.views()[0].window()
              QMessageBox.critical(parent_window, title, message)
         except Exception as e:
              print(f"Error displaying dialog: {e}") # Fallback
              print(f"Original Error: {title} - {message}")

```

---

**`Eidos/src/core/commands.py`** (Manual - Undo/Redo Logic, complex parts marked TODO)

```python
# src/core/commands.py
from PySide6.QtWidgets import QUndoCommand
from PySide6.QtCore import QPointF

# Import necessary classes (adjust paths if needed)
from src.graphics.diagram_scene import DiagramScene # Type hinting
from src.graphics.node_item import NodeItem
from src.graphics.edge_item import EdgeItem
from src.core.data_model import NodeData, EdgeData

# --- Add Node Command ---
class AddNodeCommand(QUndoCommand):
    def __init__(self, scene: DiagramScene, node_data: NodeData, description="Add Node"):
        super().__init__(description)
        self.scene = scene
        # Store a copy of the data, not the original object if it might change elsewhere
        self.node_data = NodeData(**node_data.__dict__) # Basic copy assuming simple fields
        # Copy nested data too
        if isinstance(node_data.custom_data, MultiModalData):
             self.node_data.custom_data = MultiModalData(**node_data.custom_data.__dict__)
        self.node_id = self.node_data.id # Store ID for removal

    def redo(self):
        # Re-add node using scene method
        # add_node returns the item, store it if needed, but rely on ID primarily
        node_item = self.scene.add_node(QPointF(), data=self.node_data)
        if not node_item:
             self.setObsolete(True)
             print(f"Error redoing AddNodeCommand for {self.node_id}")

    def undo(self):
        # Remove by ID using scene method
        removed = self.scene.remove_item_by_id(self.node_id)
        if not removed:
             # If removal failed, command might be out of sync
             print(f"Error undoing AddNodeCommand: Could not remove node {self.node_id}")
             self.setObsolete(True) # Mark as problematic

# --- Delete Items Command ---
class DeleteItemsCommand(QUndoCommand):
    # TODO: This is complex! Needs careful handling of dependencies,
    # especially edges connected to deleted nodes that weren't selected themselves.
    def __init__(self, scene: DiagramScene, items_to_delete: list, description="Delete Items"):
        super().__init__(description)
        self.scene = scene
        self.nodes_data = []
        self.edges_data = []
        self.affected_edges_data = {} # Store edges connected to deleted nodes: {edge_id: EdgeData}

        # Separate selected nodes and edges
        selected_node_ids = set()
        selected_edge_ids = set()
        for item in items_to_delete:
            if isinstance(item, NodeItem):
                self.nodes_data.append(NodeData(**item.node_data.__dict__)) # Store copy
                selected_node_ids.add(item.get_id())
            elif isinstance(item, EdgeItem):
                self.edges_data.append(EdgeData(**item.edge_data.__dict__)) # Store copy
                selected_edge_ids.add(item.get_id())

        # Find affected edges (connected to deleted nodes but not deleted themselves)
        for node_data in self.nodes_data:
            node_item = self.scene.items_map.get(node_data.id)
            if node_item:
                 # Check incoming edges
                 for edge in node_item.edges_in:
                      if edge.get_id() not in selected_edge_ids and edge.get_id() not in self.affected_edges_data:
                           self.affected_edges_data[edge.get_id()] = EdgeData(**edge.edge_data.__dict__)
                 # Check outgoing edges
                 for edge in node_item.edges_out:
                      if edge.get_id() not in selected_edge_ids and edge.get_id() not in self.affected_edges_data:
                           self.affected_edges_data[edge.get_id()] = EdgeData(**edge.edge_data.__dict__)

    def redo(self):
        # Remove selected nodes, selected edges, and affected edges by ID
        ids_to_remove = ([n.id for n in self.nodes_data] +
                         [e.id for e in self.edges_data] +
                         list(self.affected_edges_data.keys()))
        # Assumes scene has a robust method for this
        self.scene.remove_items_by_ids(ids_to_remove)

    def undo(self):
        # Add back nodes first (order matters less here)
        for node_data in self.nodes_data:
            if node_data.id not in self.scene.items_map: # Avoid re-adding if already exists
                self.scene.add_node(QPointF(), data=node_data)

        # Add back affected edges (these nodes should exist now)
        for edge_data in self.affected_edges_data.values():
             if edge_data.id not in self.scene.items_map:
                 self.scene.add_edge(data=edge_data)

        # Add back selected edges (these nodes should exist now)
        for edge_data in self.edges_data:
             if edge_data.id not in self.scene.items_map:
                 self.scene.add_edge(data=edge_data)

        # TODO: Verify connections are properly restored in NodeItem edge lists

# --- Move Nodes Command ---
class MoveNodesCommand(QUndoCommand):
    def __init__(self, scene: DiagramScene, move_data: dict, description="Move Nodes"):
        # move_data = {node_id: {'item': node_item, 'old_pos': QPointF, 'new_pos': QPointF}}
        super().__init__(description)
        self.scene = scene
        self.move_data = move_data
        # Store positions as tuples for serialization safety if needed later
        self.positions = {
            nid: {
                'old': (data['old_pos'].x(), data['old_pos'].y()),
                'new': (data['new_pos'].x(), data['new_pos'].y())
            } for nid, data in move_data.items()
        }

    def redo(self):
        for node_id, pos_data in self.positions.items():
            item = self.scene.items_map.get(node_id)
            if item and isinstance(item, NodeItem):
                new_qpoint = QPointF(pos_data['new'][0], pos_data['new'][1])
                item.setPos(new_qpoint) # This triggers itemChange to update node_data and edges

    def undo(self):
        for node_id, pos_data in self.positions.items():
            item = self.scene.items_map.get(node_id)
            if item and isinstance(item, NodeItem):
                old_qpoint = QPointF(pos_data['old'][0], pos_data['old'][1])
                item.setPos(old_qpoint)

# --- Link Nodes Command ---
class LinkNodesCommand(QUndoCommand):
    def __init__(self, scene: DiagramScene, edge_data: EdgeData, description="Link Nodes"):
        super().__init__(description)
        self.scene = scene
        self.edge_data = EdgeData(**edge_data.__dict__) # Store copy
        self.edge_id = self.edge_data.id

    def redo(self):
        # Re-add edge using scene method
        edge_item = self.scene.add_edge(data=self.edge_data)
        if not edge_item:
            self.setObsolete(True)
            print(f"Error redoing LinkNodesCommand for {self.edge_id}")

    def undo(self):
        # Remove by ID using scene method
        removed = self.scene.remove_item_by_id(self.edge_id)
        if not removed:
            print(f"Error undoing LinkNodesCommand: Could not remove edge {self.edge_id}")
            self.setObsolete(True)

# --- Change Properties Command ---
class ChangePropertiesCommand(QUndoCommand):
    def __init__(self, scene: DiagramScene, node_id: str, old_data: dict, new_data: dict, description="Change Properties"):
        # old_data/new_data should contain only the changed fields (label, color, code, etc.)
        super().__init__(description)
        self.scene = scene
        self.node_id = node_id
        self.old_props = old_data # Dict of old property values
        self.new_props = new_data # Dict of new property values

    def _apply_properties(self, props_to_apply):
        node_item = self.scene.items_map.get(self.node_id)
        if node_item and isinstance(node_item, NodeItem):
            node_data = node_item.node_data
            needs_repaint = False
            for key, value in props_to_apply.items():
                 if hasattr(node_data, key):
                      setattr(node_data, key, value)
                      if key in ['label', 'display_properties']: # Check fields affecting appearance
                           needs_repaint = True
                 elif key in node_data.display_properties:
                      node_data.display_properties[key] = value
                      needs_repaint = True
                      if key == 'color': # Update brush directly
                            node_item.setBrush(QBrush(QColor(value)))
                 elif hasattr(node_data.custom_data, key):
                       setattr(node_data.custom_data, key, value)
                       needs_repaint = True # Assume custom data change needs indicator repaint
                 # Add more specific handling as needed

            if needs_repaint:
                 node_item.update() # Request repaint
        else:
             print(f"Error applying properties: Node {self.node_id} not found.")
             self.setObsolete(True)

    def redo(self):
        self._apply_properties(self.new_props)

    def undo(self):
        self._apply_properties(self.old_props)

```
