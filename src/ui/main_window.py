```python
# src/ui/main_window.py
import sys
import os
from PySide6.QtWidgets import (QMainWindow, QToolBar, QStatusBar, QMessageBox,
                               QUndoStack, QUndoView, QDockWidget) # Added Undo/Redo, Dock
from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtCore import Slot, Qt # Added Qt for DockWidgetArea

from src.ui.view import DiagramView
from src.graphics.diagram_scene import DiagramScene
from src.persistence.file_handler import save_file_dialog, load_file_dialog
from src.core.config_manager import load_config
from src.utils.helpers import resource_path # For icons

class MainWindow(QMainWindow):
    """ Main application window containing the scene view, menus, toolbars. """
    def __init__(self, config=None, parent=None):
        super().__init__(parent)
        self.config = config if config else load_config()
        self.current_filepath = None # Path of the currently open file

        self.setWindowTitle("Eidos - Abstract System Modeler")
        self.resize(1200, 800)

        # --- Core Components ---
        self.undo_stack = QUndoStack(self)
        self.scene = DiagramScene(self.config)
        self.scene.set_undo_stack(self.undo_stack) # Provide undo stack to scene
        self.view = DiagramView(self.scene, self)

        self.setCentralWidget(self.view)

        # --- UI Setup ---
        self.create_actions()
        self.create_menus()
        self.create_toolbars()
        self.create_status_bar()
        self.create_undo_view_dock() # Optional Undo history view

        self.set_mode("select") # Set initial interaction mode
        self._update_save_action_state() # Disable save initially

        # Connect scene signals if needed (e.g., for status updates)
        # self.scene.some_signal.connect(self.handle_scene_signal)


    def create_actions(self):
        """ Creates QActions for menus and toolbars. """
        icon_folder = resource_path('assets/icons')

        # --- File Actions ---
        self.new_action = QAction(QIcon(os.path.join(icon_folder, 'new_file.png')), "&New", self)
        self.new_action.setShortcut(QKeySequence.StandardKey.New)
        self.new_action.setStatusTip("Create a new model file")
        self.new_action.triggered.connect(self.on_new_file)

        self.open_action = QAction(QIcon(os.path.join(icon_folder, 'open_file.png')), "&Open...", self)
        self.open_action.setShortcut(QKeySequence.StandardKey.Open)
        self.open_action.setStatusTip("Open an existing model file")
        self.open_action.triggered.connect(self.on_open_file)

        self.save_action = QAction(QIcon(os.path.join(icon_folder, 'save_file.png')), "&Save", self)
        self.save_action.setShortcut(QKeySequence.StandardKey.Save)
        self.save_action.setStatusTip("Save the current model file")
        self.save_action.triggered.connect(self.on_save_file)

        self.save_as_action = QAction("Save &As...", self)
        self.save_as_action.setShortcut(QKeySequence.StandardKey.SaveAs)
        self.save_as_action.setStatusTip("Save the current model file with a new name")
        self.save_as_action.triggered.connect(self.on_save_as_file)

        self.exit_action = QAction("E&xit", self)
        # Use standard platform quit shortcut
        self.exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        self.exit_action.setStatusTip("Exit the application")
        self.exit_action.triggered.connect(self.close) # Use QMainWindow's close

        # --- Edit Actions ---
        self.undo_action = self.undo_stack.createUndoAction(self, "&Undo")
        self.undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self.undo_action.setStatusTip("Undo the last action")

        self.redo_action = self.undo_stack.createRedoAction(self, "&Redo")
        self.redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        self.redo_action.setStatusTip("Redo the last undone action")

        self.delete_action = QAction(QIcon.fromTheme("edit-delete", QIcon(os.path.join(icon_folder, 'delete.png'))), "&Delete", self) # Example with fallback icon
        self.delete_action.setShortcut(QKeySequence.StandardKey.Delete)
        self.delete_action.setStatusTip("Delete selected items")
        self.delete_action.triggered.connect(self._trigger_scene_delete) # Connect to scene logic

        # TODO: Add Cut/Copy/Paste actions and connect them

        # --- Tool Actions ---
        self.select_action = QAction(QIcon(os.path.join(icon_folder, 'select.png')), "Select/Move", self)
        self.select_action.setCheckable(True)
        self.select_action.setStatusTip("Select, move, and edit items (Default mode)")
        self.select_action.triggered.connect(lambda checked: self.set_mode("select") if checked else None)

        self.add_node_action = QAction(QIcon(os.path.join(icon_folder, 'add_node.png')), "Add Node", self)
        self.add_node_action.setStatusTip("Add a new node to the center of the view")
        self.add_node_action.triggered.connect(self.on_add_node_trigger) # Momentary action

        self.link_nodes_action = QAction(QIcon(os.path.join(icon_folder, 'link_nodes.png')), "Link Nodes", self)
        self.link_nodes_action.setCheckable(True)
        self.link_nodes_action.setStatusTip("Click start node, then end node to create a link")
        self.link_nodes_action.triggered.connect(lambda checked: self.set_mode("link") if checked else None)

        self.run_flow_action = QAction(QIcon(os.path.join(icon_folder, 'run_flow.png')), "Execute Flow", self)
        self.run_flow_action.setCheckable(True)
        self.run_flow_action.setStatusTip("Click a node to start executing the process flow from it")
        self.run_flow_action.triggered.connect(lambda checked: self.set_mode("execute") if checked else None)

        # --- Action Group for Modes ---
        self.mode_action_group = QActionGroup(self)
        self.mode_action_group.addAction(self.select_action)
        self.mode_action_group.addAction(self.link_nodes_action)
        self.mode_action_group.addAction(self.run_flow_action)
        self.mode_action_group.setExclusive(True)

        # Connect undo stack signals to update action states
        self.undo_stack.cleanChanged.connect(self._update_window_title)
        self.undo_stack.cleanChanged.connect(self._update_save_action_state)


    def create_menus(self):
        """ Creates the main menu bar. """
        # --- File Menu ---
        file_menu = self.menuBar().addMenu("&File")
        file_menu.addAction(self.new_action)
        file_menu.addAction(self.open_action)
        file_menu.addSeparator()
        file_menu.addAction(self.save_action)
        file_menu.addAction(self.save_as_action)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)

        # --- Edit Menu ---
        edit_menu = self.menuBar().addMenu("&Edit")
        edit_menu.addAction(self.undo_action)
        edit_menu.addAction(self.redo_action)
        edit_menu.addSeparator()
        # TODO: Add Cut/Copy/Paste
        edit_menu.addAction(self.delete_action)

        # --- View Menu (Example) ---
        view_menu = self.menuBar().addMenu("&View")
        # Example: Action to toggle Undo History dock
        self.toggle_undo_view_action = self.undo_dock_widget.toggleViewAction()
        self.toggle_undo_view_action.setText("Undo History")
        self.toggle_undo_view_action.setStatusTip("Show/Hide the Undo History panel")
        view_menu.addAction(self.toggle_undo_view_action)
        # TODO: Add Zoom actions (Zoom In, Zoom Out, Zoom Fit) connected to view methods

        # --- Tools Menu (Optional - could hold mode actions) ---
        # tools_menu = self.menuBar().addMenu("&Tools")
        # tools_menu.addAction(self.select_action)
        # ...

    def create_toolbars(self):
        """ Creates the main application toolbar. """
        # --- File Toolbar ---
        file_toolbar = QToolBar("File Tools")
        file_toolbar.setIconSize(QSize(24, 24)) # Example size
        self.addToolBar(file_toolbar)
        file_toolbar.addAction(self.new_action)
        file_toolbar.addAction(self.open_action)
        file_toolbar.addAction(self.save_action)

        # --- Edit Toolbar ---
        edit_toolbar = QToolBar("Edit Tools")
        edit_toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(edit_toolbar)
        edit_toolbar.addAction(self.undo_action)
        edit_toolbar.addAction(self.redo_action)
        edit_toolbar.addAction(self.delete_action)

        # --- Mode Toolbar ---
        mode_toolbar = QToolBar("Mode Tools")
        mode_toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(mode_toolbar)
        mode_toolbar.addAction(self.select_action)
        mode_toolbar.addAction(self.add_node_action) # Add node is momentary
        mode_toolbar.addAction(self.link_nodes_action)
        mode_toolbar.addSeparator()
        mode_toolbar.addAction(self.run_flow_action)

    def create_status_bar(self):
        """ Creates the application status bar. """
        self.statusBar().showMessage("Ready")

    def create_undo_view_dock(self):
        """ Creates the dock widget for the QUndoView (optional). """
        self.undo_view = QUndoView(self.undo_stack)
        self.undo_view.setWindowTitle("Undo History")
        self.undo_dock_widget = QDockWidget("Undo History", self)
        self.undo_dock_widget.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.undo_dock_widget.setWidget(self.undo_view)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.undo_dock_widget)
        # Hide it initially?
        self.undo_dock_widget.setVisible(False)


    # --- Slots for Actions ---
    @Slot(str)
    def set_mode(self, mode):
        """ Sets the interaction mode in the scene and updates UI. """
        self.scene.set_mode(mode)
        self.statusBar().showMessage(f"Mode: {mode.capitalize()}")
        # Update checked state of toolbar buttons based on group logic
        if mode == "select": self.select_action.setChecked(True)
        elif mode == "link": self.link_nodes_action.setChecked(True)
        elif mode == "execute": self.run_flow_action.setChecked(True)
        # Update cursor in the view
        self.view.update_cursor(mode)

    @Slot()
    def on_add_node_trigger(self):
        """ Handles the momentary 'Add Node' action. """
        center_point = self.view.mapToScene(self.view.viewport().rect().center())
        # Create data and push AddNodeCommand
        node_id = generate_uuid()
        # Use default node data
        node_data = NodeData(id=node_id, position=(center_point.x(), center_point.y()))
        cmd = AddNodeCommand(self.scene, node_data)
        self.undo_stack.push(cmd)
        # Optionally switch back to select mode after adding
        self.set_mode("select")

    @Slot()
    def on_new_file(self):
        """ Handles the File -> New action. """
        if not self._check_unsaved_changes(): return # Stop if user cancels
        self.scene.clear_scene()
        self.undo_stack.clear() # Clear undo history
        self.current_filepath = None
        self.scene.set_model_filepath(None) # Clear context
        self.statusBar().showMessage("New file created")
        self._update_window_title()

    @Slot()
    def on_open_file(self):
        """ Handles the File -> Open action. """
        if not self._check_unsaved_changes(): return
        default_dir = self.config.get('Paths', 'DEFAULT_SAVE_DIR', fallback=os.path.expanduser("~"))
        scene_data, filepath = load_file_dialog(self, default_dir=default_dir)
        if scene_data and filepath:
            self.scene.clear_scene() # Clear before loading
            self.undo_stack.clear()
            self.scene.load_data(scene_data)
            self.current_filepath = filepath
            self.scene.set_model_filepath(filepath) # Set context
            self.undo_stack.setClean() # Mark as clean after load
            self.statusBar().showMessage(f"Loaded: {os.path.basename(filepath)}")
            self._update_window_title()
        elif filepath: # File chosen but loading failed (error shown by file_handler)
            self.statusBar().showMessage("File loading failed")

    @Slot()
    def on_save_file(self):
        """ Handles the File -> Save action. """
        if self.current_filepath:
            scene_data = self.scene.get_data_for_save()
            saved_path = save_file_dialog(self, scene_data, current_filepath=self.current_filepath)
            if saved_path: # Check if save was successful
                 self.undo_stack.setClean() # Mark as clean after successful save
                 self.statusBar().showMessage(f"Saved: {os.path.basename(saved_path)}")
                 self._update_window_title()
            else:
                 self.statusBar().showMessage("Save cancelled or failed")
            return saved_path is not None # Return True if saved
        else:
            return self.on_save_as_file() # Trigger Save As if no current path


    @Slot()
    def on_save_as_file(self):
        """ Handles the File -> Save As action. """
        scene_data = self.scene.get_data_for_save()
        default_dir = self.config.get('Paths', 'DEFAULT_SAVE_DIR', fallback=os.path.expanduser("~"))
        # Suggest filename based on current path or default
        suggested_path = self.current_filepath or os.path.join(default_dir, "untitled_eidos_model.json")

        filepath = save_file_dialog(self, scene_data, current_filepath=suggested_path, default_dir=os.path.dirname(suggested_path))
        if filepath:
            self.current_filepath = filepath
            self.scene.set_model_filepath(filepath) # Update context
            self.undo_stack.setClean() # Mark as clean after successful save
            self.statusBar().showMessage(f"Saved as: {os.path.basename(filepath)}")
            self._update_window_title()
            return True # Saved successfully
        else:
             self.statusBar().showMessage("Save As cancelled or failed")
             return False # Save failed or cancelled


    @Slot()
    def _trigger_scene_delete(self):
        """ Triggers deletion of selected items in the scene using Undo Command. """
        selected = self.scene.selectedItems()
        if selected:
            cmd = DeleteItemsCommand(self.scene, selected)
            self.undo_stack.push(cmd)

    # --- Internal Helper Methods ---
    def _check_unsaved_changes(self) -> bool:
        """ Checks if the document is modified and prompts the user to save. Returns True if okay to proceed. """
        if not self.undo_stack.isClean():
            reply = QMessageBox.warning(self, 'Unsaved Changes',
                     "The current model has unsaved changes.\nDo you want to save them before proceeding?",
                     QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)

            if reply == QMessageBox.StandardButton.Save:
                return self.on_save_file() # Proceed only if save succeeds
            elif reply == QMessageBox.StandardButton.Cancel:
                return False # User cancelled the operation
            # If Discard, proceed
        return True # Okay to proceed (either clean or user chose Discard)

    def _update_window_title(self):
        """ Updates the window title based on file path and modified status. """
        title = "Eidos"
        filename = os.path.basename(self.current_filepath) if self.current_filepath else "Untitled"
        modified_indicator = "" if self.undo_stack.isClean() else "[*]" # Standard modified indicator
        self.setWindowTitle(f"{filename}{modified_indicator} - {title}")

    def _update_save_action_state(self):
         """ Enables/disables the Save action based on the clean state. """
         self.save_action.setEnabled(not self.undo_stack.isClean())


    # --- Overriding closeEvent ---
    def closeEvent(self, event):
        """ Overrides the window close event to check for unsaved changes. """
        if self._check_unsaved_changes():
            # Stop execution engine gracefully if running
            if self.scene.execution_engine.is_running:
                 print("Stopping execution before closing...")
                 self.scene.execution_engine.stop_execution()
                 # TODO: Maybe wait briefly or ensure threads are stopped?

            event.accept() # Proceed with closing
        else:
            event.ignore() # User cancelled closing

```
