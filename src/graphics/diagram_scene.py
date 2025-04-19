```python
# src/graphics/diagram_scene.py
from PySide6.QtWidgets import (QGraphicsScene, QGraphicsItem, QMenu,
                               QGraphicsSceneContextMenuEvent, QMessageBox) # Added context menu event
from PySide6.QtGui import QMouseEvent, QTransform, QKeyEvent, QPen, QColor # Added Pen/Color
from PySide6.QtCore import Qt, QPointF, QLineF
import uuid
import os # For path manipulation needed by get_model_directory

# Import project components
from src.graphics.node_item import NodeItem
from src.graphics.edge_item import EdgeItem
from src.core.data_model import NodeData, EdgeData, MultiModalData
from src.core.execution_engine import ExecutionEngine # Required
from src.ai.ai_manager import AIManager             # Required
from src.core.commands import (AddNodeCommand, DeleteItemsCommand, # Import Commands
                               LinkNodesCommand, MoveNodesCommand,
                               ChangePropertiesCommand)

class DiagramScene(QGraphicsScene):
    """ Manages graphics items, interaction modes, and context menus. """
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.current_mode = "select"
        self.link_start_item = None
        self.temp_link_line = None
        self.items_map = {} # {item_id: QGraphicsItem}

        # Store reference to undo stack (needs to be set from MainWindow)
        self.undo_stack = None

        # Store reference to the currently loaded model file path
        self._current_model_filepath = None

        # Initialize core components (passed during setup or lazy loaded?)
        # For simplicity, assume AI/Exec engines are created here for now
        self.ai_manager = AIManager(config)
        self.execution_engine = ExecutionEngine(self, self.ai_manager, config)

        # Movement tracking for MoveNodesCommand
        self._move_origins = {} # {item_id: original_QPointF}

        # Set scene defaults
        # self.setSceneRect(-2000, -1500, 4000, 3000) # Set in View now
        self.setBackgroundBrush(QColor(240, 240, 240)) # Light grey background

    def set_undo_stack(self, undo_stack):
        """Sets the undo stack reference provided by the MainWindow."""
        self.undo_stack = undo_stack

    def set_model_filepath(self, filepath):
        """Stores the path of the currently loaded/saved model file."""
        self._current_model_filepath = filepath

    def get_model_directory(self):
        """Returns the directory containing the current model file, or None."""
        if self._current_model_filepath:
            return os.path.dirname(self._current_model_filepath)
        return None

    def set_mode(self, mode: str):
        """Sets the current interaction mode."""
        self.current_mode = mode
        self.link_start_item = None
        if self.temp_link_line:
            self.removeItem(self.temp_link_line)
            self.temp_link_line = None
        # TODO: Signal mode change to MainWindow for status bar/cursor updates

    def add_node(self, position: QPointF, data: NodeData = None) -> Optional[NodeItem]:
        """Adds a node graphics item to the scene based on NodeData."""
        if data is None: # Should be created by command usually
            print("Warning: add_node called without data. Use AddNodeCommand.")
            return None
        if data.id in self.items_map:
             print(f"Warning: Node with ID {data.id} already exists.")
             return self.items_map[data.id] # Return existing item

        # Use position from data if available and valid
        node_pos = QPointF(data.position[0], data.position[1]) if data.position else position
        data.position = (node_pos.x(), node_pos.y()) # Ensure data matches position

        node_item = NodeItem(data)
        node_item.setPos(node_pos) # Set position explicitly
        self.addItem(node_item)
        self.items_map[data.id] = node_item
        print(f"Scene: Added node '{data.label}' ({data.id})")
        return node_item

    def add_edge(self, data: EdgeData) -> Optional[EdgeItem]:
        """Adds an edge graphics item to the scene based on EdgeData."""
        if data.id in self.items_map:
            print(f"Warning: Edge with ID {data.id} already exists.")
            return self.items_map[data.id] # Return existing item

        start_node_item = self.items_map.get(data.start_node_id)
        end_node_item = self.items_map.get(data.end_node_id)

        if start_node_item and end_node_item and isinstance(start_node_item, NodeItem) and isinstance(end_node_item, NodeItem):
            edge_item = EdgeItem(data, start_node_item, end_node_item)
            self.addItem(edge_item)
            self.items_map[data.id] = edge_item
            # Add references TO the nodes (NodeItem needs these methods)
            start_node_item.add_edge_ref(edge_item, is_outgoing=True)
            end_node_item.add_edge_ref(edge_item, is_outgoing=False)
            print(f"Scene: Added edge ({data.id}) from '{start_node_item.node_data.label}' to '{end_node_item.node_data.label}'")
            return edge_item
        else:
            print(f"Error adding edge {data.id}: Start ({data.start_node_id}) or End ({data.end_node_id}) node not found or invalid.")
            return None

    def remove_item_by_id(self, item_id):
        """Removes a single item (node or edge) and its references."""
        item = self.items_map.get(item_id)
        if not item:
            print(f"Warning: Cannot remove item, ID not found: {item_id}")
            return False

        if isinstance(item, NodeItem):
            print(f"Scene: Removing node '{item.node_data.label}' ({item_id})")
            # Remove connected edges FIRST to clean node references correctly
            edges_to_remove = item.edges_in[:] + item.edges_out[:] # Copy list
            for edge in edges_to_remove:
                 self.remove_item_by_id(edge.get_id()) # Recursive call for edges
            self.removeItem(item) # Remove node item itself
        elif isinstance(item, EdgeItem):
            print(f"Scene: Removing edge ({item_id})")
            item.destroy() # Calls remove_edge_ref on nodes and removeItem(self)
        else:
             print(f"Warning: Attempted to remove unknown item type for ID {item_id}")
             self.removeItem(item) # Try generic removal

        # Remove from map
        if item_id in self.items_map:
            del self.items_map[item_id]
            return True
        return False # Should have been removed if found

    def remove_items_by_ids(self, id_list):
        """Removes multiple items, handling nodes and edges."""
        print(f"Scene: Removing items by IDs: {id_list}")
        # Separate nodes and edges to ensure edges are removed first if node is also removed
        node_ids_to_remove = set()
        edge_ids_to_remove = set()
        for item_id in id_list:
             item = self.items_map.get(item_id)
             if isinstance(item, NodeItem): node_ids_to_remove.add(item_id)
             elif isinstance(item, EdgeItem): edge_ids_to_remove.add(item_id)

        # Add edges connected to nodes being removed (if not already in list)
        affected_edges = set()
        for node_id in node_ids_to_remove:
             node_item = self.items_map.get(node_id)
             if node_item:
                  for edge in node_item.edges_in + node_item.edges_out:
                       if edge.get_id() not in edge_ids_to_remove:
                            affected_edges.add(edge.get_id())

        edge_ids_to_remove.update(affected_edges)

        # Remove edges first
        for edge_id in edge_ids_to_remove:
            self.remove_item_by_id(edge_id)
        # Then remove nodes
        for node_id in node_ids_to_remove:
            self.remove_item_by_id(node_id)

    # --- Mouse Events for Interaction ---
    def mousePressEvent(self, event: QMouseEvent):
        pos = event.scenePos()
        item = self.itemAt(pos, QTransform())

        if event.button() == Qt.MouseButton.LeftButton:
            if self.current_mode == "link":
                if isinstance(item, NodeItem):
                    if self.link_start_item is None:
                        self.link_start_item = item
                        self.temp_link_line = self.addLine(QLineF(item.scenePos(), pos), QPen(Qt.gray, 1, Qt.PenStyle.DashLine))
                        print(f"Link started from: {item.node_data.label}")
                    else:
                        if item != self.link_start_item:
                            # Create EdgeData and push LinkNodesCommand
                            edge_id = generate_uuid() # Use helper from data_model
                            edge_data = EdgeData(id=edge_id,
                                                 start_node_id=self.link_start_item.get_id(),
                                                 end_node_id=item.get_id())
                            if self.undo_stack:
                                 cmd = LinkNodesCommand(self, edge_data)
                                 self.undo_stack.push(cmd)
                            else: # Execute directly if no undo stack
                                 self.add_edge(edge_data)
                            print(f"Link command created: {self.link_start_item.node_data.label} -> {item.node_data.label}")
                        else:
                            print("Cannot link node to itself.")
                        # Reset linking state
                        if self.temp_link_line: self.removeItem(self.temp_link_line); self.temp_link_line = None
                        self.link_start_item = None
                else: # Clicked empty space
                    if self.temp_link_line: self.removeItem(self.temp_link_line); self.temp_link_line = None
                    self.link_start_item = None
                    print("Link cancelled.")

            elif self.current_mode == "execute":
                if isinstance(item, NodeItem):
                    print(f"\n--- Requesting Execution Start from '{item.node_data.label}' ---")
                    if self.execution_engine.is_running:
                         QMessageBox.warning(self.views()[0].window(), "Execution Busy", "An execution flow is already running.")
                    else:
                         # Run in foreground for now, consider QThread for engine later
                         self.execution_engine.run_flow(start_node_item=item)
                else:
                    print("Execution mode: Click on a node to start.")

            elif self.current_mode == "select":
                if isinstance(item, NodeItem):
                    # Store original positions for MoveNodesCommand on release
                    self._move_origins.clear()
                    for sel_item in self.selectedItems():
                         if isinstance(sel_item, NodeItem):
                              self._move_origins[sel_item.get_id()] = sel_item.pos() # Store initial pos
                super().mousePressEvent(event) # Default selection/move start

        elif event.button() == Qt.MouseButton.RightButton:
             # Let contextMenuEvent handle right-clicks
             super().mousePressEvent(event)


    def mouseMoveEvent(self, event: QMouseEvent):
        if self.current_mode == "link" and self.link_start_item and self.temp_link_line:
            new_line = QLineF(self.link_start_item.scenePos(), event.scenePos())
            self.temp_link_line.setLine(new_line)
        else:
            super().mouseMoveEvent(event) # Default drag move

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self.current_mode == "select" and self._move_origins:
            # --- Create Move Command ---
            move_data = {}
            for item_id, old_pos in self._move_origins.items():
                 item = self.items_map.get(item_id)
                 # Check if position actually changed
                 if item and isinstance(item, NodeItem) and item.pos() != old_pos:
                      move_data[item_id] = {'item': item, 'old_pos': old_pos, 'new_pos': item.pos()}

            if move_data and self.undo_stack:
                 cmd = MoveNodesCommand(self, move_data)
                 self.undo_stack.push(cmd)
            self._move_origins.clear() # Clear origin tracking

        super().mouseReleaseEvent(event) # Default selection/move end


    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Delete or event.key() == Qt.Key.Key_Backspace:
            selected = self.selectedItems()
            if selected:
                # Use DeleteItemsCommand
                if self.undo_stack:
                     cmd = DeleteItemsCommand(self, selected)
                     self.undo_stack.push(cmd)
                else: # Execute directly
                     ids_to_remove = [item.get_id() for item in selected if hasattr(item, 'get_id')]
                     self.remove_items_by_ids(ids_to_remove)
        else:
            super().keyPressEvent(event)

    # --- Context Menu ---
    def contextMenuEvent(self, event: QGraphicsSceneContextMenuEvent):
        item = self.itemAt(event.scenePos(), QTransform())
        menu = QMenu()
        action_triggered = False # Flag to check if any action was taken

        if isinstance(item, NodeItem):
            props_action = menu.addAction("Properties...")
            delete_action = menu.addAction("Delete Node")
            # --- Connections ---
            props_action.triggered.connect(lambda: self._context_show_properties(item))
            delete_action.triggered.connect(lambda: self._context_delete_items([item]))
            action_triggered = True
        elif isinstance(item, EdgeItem):
            delete_action = menu.addAction("Delete Link")
            # --- Connections ---
            delete_action.triggered.connect(lambda: self._context_delete_items([item]))
            action_triggered = True
        else: # Background clicked
            add_node_action = menu.addAction("Add Node Here")
            # --- Connections ---
            add_node_action.triggered.connect(lambda: self._context_add_node(event.scenePos()))
            action_triggered = True

        if action_triggered:
             menu.exec(event.screenPos())
        else: # Pass event up if no relevant item clicked
             super().contextMenuEvent(event)

    # --- Context Menu Helper Methods (using Undo Commands) ---
    def _context_show_properties(self, node_item):
        # Need ChangePropertiesCommand if dialog makes changes
        # For now, just open dialog - Command should be pushed on Dialog Accept
        # Store old state BEFORE opening dialog
        old_props_dict = node_item.get_properties_dict() # NodeItem needs this method
        node_item.trigger_properties_dialog() # NodeItem needs this method

        # TODO: How to get the "new properties" after dialog closes to create command?
        # Option 1: Dialog emits signal with old/new data -> Scene connects -> Scene pushes command
        # Option 2: NodeItem handles command creation internally after dialog.accept()

    def _context_add_node(self, pos):
        node_id = generate_uuid()
        # Use default node data for context menu add
        node_data = NodeData(id=node_id, position=(pos.x(), pos.y()))
        if self.undo_stack:
            cmd = AddNodeCommand(self, node_data)
            self.undo_stack.push(cmd)
        else:
            self.add_node(pos, data=node_data)

    def _context_delete_items(self, items_list):
        if self.undo_stack:
            cmd = DeleteItemsCommand(self, items_list)
            self.undo_stack.push(cmd)
        else:
            ids = [item.get_id() for item in items_list if hasattr(item, 'get_id')]
            self.remove_items_by_ids(ids)

    # --- Data Management ---
    def get_data_for_save(self) -> dict:
        """Extracts serializable data from all items."""
        nodes = []
        edges = []
        for item in self.items_map.values():
             if isinstance(item, NodeItem):
                  nodes.append(item.node_data)
             elif isinstance(item, EdgeItem):
                  edges.append(item.edge_data)
        # Important: Deep copy data to avoid modifying original objects if needed?
        # For now, assume NodeData/EdgeData are passed directly.
        # Serialization should handle converting dataclasses to dicts.
        return {"nodes": nodes, "edges": edges}

    def load_data(self, scene_data_dict):
        """Clears scene and loads from deserialized dictionary data."""
        self.clear_scene() # Clear graphics and map
        print("Loading scene data...")
        nodes_list = scene_data_dict.get("nodes", [])
        edges_list = scene_data_dict.get("edges", [])

        # Load nodes (converting dicts back to dataclass instances)
        loaded_nodes = {}
        for node_dict in nodes_list:
            try:
                # Handle nested MultiModalData if it's a dict
                mm_data_dict = node_dict.get('custom_data', {})
                if isinstance(mm_data_dict, dict):
                    node_dict['custom_data'] = MultiModalData(**mm_data_dict)
                # Create NodeData instance
                node_data = NodeData(**node_dict)
                node_item = self.add_node(QPointF(), data=node_data) # add_node uses position from data
                if node_item:
                    loaded_nodes[node_data.id] = node_item
            except TypeError as e:
                 print(f"Error creating NodeData from dict: {e} - Data: {node_dict}")
            except Exception as e:
                 print(f"Unexpected error loading node: {e} - Data: {node_dict}")


        # Load edges (converting dicts back to dataclass instances)
        for edge_dict in edges_list:
             try:
                  edge_data = EdgeData(**edge_dict)
                  # Check if start/end nodes were loaded successfully
                  if edge_data.start_node_id in loaded_nodes and edge_data.end_node_id in loaded_nodes:
                       self.add_edge(data=edge_data)
                  else:
                       print(f"Warning: Skipping edge {edge_data.id} due to missing start/end node.")
             except TypeError as e:
                  print(f"Error creating EdgeData from dict: {e} - Data: {edge_dict}")
             except Exception as e:
                  print(f"Unexpected error loading edge: {e} - Data: {edge_dict}")
        print("Scene loading complete.")


    def clear_scene(self):
        """Removes all graphics items and clears the internal map."""
        # Need to remove items correctly to avoid issues
        items_to_remove = list(self.items()) # Iterate over copy
        for item in items_to_remove:
            # Let remove_item_by_id handle cleanup if possible (for nodes/edges)
            if hasattr(item, 'get_id') and item.get_id() in self.items_map:
                pass # It will be removed when map is cleared below
            else:
                 # Remove generic items added directly (like temp line)
                 self.removeItem(item)

        # Clear map and references, letting garbage collection handle items?
        # Or explicitly remove via ID
        ids_to_clear = list(self.items_map.keys())
        for item_id in ids_to_clear:
             self.remove_item_by_id(item_id) # Use robust removal

        self.items_map.clear()
        self.link_start_item = None
        self.temp_link_line = None # Ensure temp line ref is cleared
        print("Scene cleared.")

``` 
