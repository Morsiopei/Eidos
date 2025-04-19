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

---

**`Eidos/src/ui/node_properties_dialog.py`** (Manual - Includes Multimodal fields)

```python
# src/ui/node_properties_dialog.py
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QTextEdit, QColorDialog, QFileDialog,
                               QComboBox, QGroupBox, QSizePolicy) # Added more widgets
from PySide6.QtGui import QColor, QIcon # Added QIcon
from PySide6.QtCore import Slot # Added Slot
import os

from src.core.data_model import NodeData # Import data model
from src.utils.helpers import resource_path # For icons


class NodePropertiesDialog(QDialog):
    """ Dialog for editing properties of a NodeData object. """
    def __init__(self, node_data: NodeData, parent=None):
        super().__init__(parent)
        self.node_data = node_data # Store reference to the live data object
        self.setWindowTitle(f"Properties: {node_data.label}")
        # Store original values to check for actual changes? Not strictly necessary if using Undo command later
        # self.original_data = copy.deepcopy(node_data) # Need deep copy

        # Use config if available (passed from MainWindow -> Scene -> NodeItem?)
        self.config = getattr(parent, 'config', None) # Basic check for config on parent

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # --- Core Properties ---
        core_group = QGroupBox("Core Properties")
        core_layout = QVBoxLayout(core_group)

        # Label
        h_label = QHBoxLayout()
        h_label.addWidget(QLabel("Label:"))
        self.label_edit = QLineEdit(node_data.label)
        h_label.addWidget(self.label_edit)
        core_layout.addLayout(h_label)

        # Node Type
        h_type = QHBoxLayout()
        h_type.addWidget(QLabel("Node Type:"))
        self.type_combo = QComboBox()
        # TODO: Make types configurable?
        self.type_combo.addItems(["Default", "Start", "Decision", "Process", "AI_Eval", "DataStore", "Terminal"])
        self.type_combo.setCurrentText(node_data.node_type)
        h_type.addWidget(self.type_combo)
        core_layout.addLayout(h_type)
        layout.addWidget(core_group)

        # --- Execution Logic ---
        exec_group = QGroupBox("Execution Logic")
        exec_layout = QVBoxLayout(exec_group)
        # Process Code
        exec_layout.addWidget(QLabel("Process Code (Restricted Python):"))
        self.process_edit = QTextEdit(node_data.process_code)
        self.process_edit.setToolTip(
            "Enter RESTRICTED Python code.\n"
            "Access input via 'input_data'. Assign output to '_result'.\n"
            "Use '_print_(...)' for logging. Limited built-ins allowed."
            )
        self.process_edit.setAcceptRichText(False)
        self.process_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        exec_layout.addWidget(self.process_edit)

        # Transition Specs
        exec_layout.addWidget(QLabel("Transition Specs (AI Rules/Prompt):"))
        self.transition_edit = QTextEdit(node_data.transition_specs)
        self.transition_edit.setToolTip("Rules or prompt hints for the AI to decide the NEXT step.\nLeave blank for default AI behavior.")
        self.transition_edit.setAcceptRichText(False)
        self.transition_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        exec_layout.addWidget(self.transition_edit)
        layout.addWidget(exec_group)


        # --- Display Properties ---
        display_group = QGroupBox("Display")
        display_layout = QVBoxLayout(display_group)
        h_color = QHBoxLayout()
        h_color.addWidget(QLabel("Node Color:"))
        self.color_button = QPushButton()
        self.color_button.setMinimumWidth(80)
        self.selected_color_name = node_data.display_properties.get('color', 'skyblue') # Store name
        self._update_color_button(self.selected_color_name)
        self.color_button.clicked.connect(self.select_color)
        h_color.addWidget(self.color_button)
        h_color.addStretch()
        display_layout.addLayout(h_color)
        # TODO: Add Radius/Size editor?
        layout.addWidget(display_group)

        # --- Multimodal Data ---
        mm_group = QGroupBox("Multimodal Data")
        mm_layout = QVBoxLayout(mm_group)
        mm_data = node_data.custom_data # Shortcut

        # Text Data
        mm_layout.addWidget(QLabel("Associated Text:"))
        self.mm_text_edit = QTextEdit(mm_data.text or "") # Use QTextEdit for potentially longer text
        self.mm_text_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)
        self.mm_text_edit.setMaximumHeight(60) # Limit height
        mm_layout.addWidget(self.mm_text_edit)

        # Image File
        mm_layout.addLayout(self._create_file_row("Image", "image", mm_data.image_ref,
                                                  "Select Image File", "Image Files (*.png *.jpg *.jpeg *.bmp *.gif)"))
        # Audio File
        mm_layout.addLayout(self._create_file_row("Audio", "audio", mm_data.audio_ref,
                                                  "Select Audio File", "Audio Files (*.wav *.mp3 *.ogg *.flac)"))
        # Video File
        mm_layout.addLayout(self._create_file_row("Video", "video", mm_data.video_ref,
                                                  "Select Video File", "Video Files (*.mp4 *.avi *.mov *.mkv)"))
        # Generic URL
        h_url = QHBoxLayout()
        h_url.addWidget(QLabel("Web URL:"))
        self.mm_url_edit = QLineEdit(mm_data.generic_url or "")
        self.mm_url_edit.setPlaceholderText("https://example.com")
        h_url.addWidget(self.mm_url_edit)
        mm_layout.addLayout(h_url)

        # TODO: Structured Data Editor (Complex - maybe show JSON string for now)
        # mm_layout.addWidget(QLabel("Structured Data (JSON):"))
        # self.mm_struct_edit = QTextEdit(json.dumps(mm_data.structured_data, indent=2))
        # mm_layout.addWidget(self.mm_struct_edit)

        layout.addWidget(mm_group)

        # --- OK / Cancel Buttons ---
        button_box = QHBoxLayout()
        ok_button = QPushButton("OK")
        ok_button.setDefault(True)
        cancel_button = QPushButton("Cancel")
        button_box.addStretch()
        button_box.addWidget(ok_button)
        button_box.addWidget(cancel_button)
        layout.addLayout(button_box)

        # Connect signals
        ok_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)

        self.resize(500, 650) # Adjust initial size

    def _create_file_row(self, label_text, field_prefix, current_ref, dialog_title, file_filter):
        """ Helper to create a Label + Path Display + Browse + Clear row. """
        layout = QHBoxLayout()

        # Store label and ref attribute name for easy access in slots
        path_label = QLabel(f"{label_text}: None")
        path_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        path_label.setWordWrap(True) # Wrap long paths if needed
        setattr(self, f"mm_{field_prefix}_label", path_label)
        setattr(self, f"mm_{field_prefix}_ref_attr", f"{field_prefix}_ref")

        if current_ref:
             path_label.setText(f"{label_text}: ...{os.path.basename(current_ref)}") # Show only filename initially
             path_label.setToolTip(current_ref) # Full path/ref in tooltip
        else:
             path_label.setToolTip(f"No {label_text.lower()} selected")

        # Use icons for buttons if available
        icon_folder = resource_path("assets/icons") # Assuming helper works
        browse_icon = QIcon.fromTheme("document-open", QIcon(os.path.join(icon_folder, 'open_file.png')))
        clear_icon = QIcon.fromTheme("edit-clear", QIcon(os.path.join(icon_folder, 'delete.png'))) # Use delete icon?

        btn_browse = QPushButton(browse_icon, "")
        btn_browse.setToolTip(f"Browse for {label_text} file")
        btn_clear = QPushButton(clear_icon, "")
        btn_clear.setToolTip(f"Clear {label_text} selection")

        # Connect signals using lambda to pass context
        btn_browse.clicked.connect(lambda: self.browse_file(field_prefix, dialog_title, file_filter))
        btn_clear.clicked.connect(lambda: self.clear_file(field_prefix))

        layout.addWidget(path_label)
        layout.addWidget(btn_browse)
        layout.addWidget(btn_clear)
        return layout

    @Slot()
    def select_color(self):
        """ Opens color dialog to select node color. """
        initial_color = QColor(self.selected_color_name)
        color = QColorDialog.getColor(initial_color, self, "Select Node Color")
        if color.isValid():
            self.selected_color_name = color.name() # Store hex name #RRGGBB
            self._update_color_button(self.selected_color_name)

    def _update_color_button(self, color_name):
        """ Updates the color button's appearance. """
        qcolor = QColor(color_name)
        self.color_button.setStyleSheet(f"background-color: {qcolor.name()}; border: 1px solid grey;")
        # Optionally set text color for contrast
        # luminance = (0.299 * qcolor.red() + 0.587 * qcolor.green() + 0.114 * qcolor.blue()) / 255
        # text_color = "white" if luminance < 0.5 else "black"
        # self.color_button.setStyleSheet(f"background-color: {qcolor.name()}; color: {text_color}; border: 1px solid grey;")
        self.color_button.setText(color_name) # Show hex code


    @Slot()
    def browse_file(self, field_prefix, dialog_title, file_filter):
        """ Opens file dialog to select a media file reference. """
        current_ref_attr = getattr(self, f"mm_{field_prefix}_ref_attr")
        current_ref = getattr(self.node_data.custom_data, current_ref_attr, None)
        # Try to determine starting directory
        start_dir = os.path.dirname(current_ref) if current_ref and os.path.isabs(current_ref) else os.path.expanduser("~")

        filepath, _ = QFileDialog.getOpenFileName(self, dialog_title, start_dir, file_filter)

        if filepath:
            # Get model directory context (needs access, passed from main window?)
            model_dir = None
            if self.parent() and hasattr(self.parent(), 'current_filepath') and self.parent().current_filepath:
                 model_dir = os.path.dirname(self.parent().current_filepath)
            elif self.parent() and hasattr(self.parent(), 'scene') and hasattr(self.parent().scene, 'get_model_directory'):
                 model_dir = self.parent().scene.get_model_directory()


            # Determine if relative path is preferred (from config?)
            prefer_relative = True # Default
            if self.config:
                 prefer_relative = self.config.getboolean('Defaults', 'PREFER_RELATIVE_PATHS', fallback=True)

            # Use the set_media_ref method from MultiModalData
            setter_method = getattr(self.node_data.custom_data, f"set_{field_prefix}_ref", None)
            if setter_method:
                 setter_method(filepath, model_dir, prefer_relative)
            else:
                 # Fallback: Set attribute directly (less robust path handling)
                 setattr(self.node_data.custom_data, current_ref_attr, filepath)

            # Update label
            new_ref = getattr(self.node_data.custom_data, current_ref_attr)
            path_label = getattr(self, f"mm_{field_prefix}_label")
            path_label.setText(f"{field_prefix.capitalize()}: ...{os.path.basename(filepath)}") # Show filename
            path_label.setToolTip(new_ref) # Show full stored ref in tooltip

    @Slot()
    def clear_file(self, field_prefix):
        """ Clears the selected media file reference. """
        ref_attr = getattr(self, f"mm_{field_prefix}_ref_attr")
        setattr(self.node_data.custom_data, ref_attr, None) # Clear data model
        # Update label
        path_label = getattr(self, f"mm_{field_prefix}_label")
        path_label.setText(f"{field_prefix.capitalize()}: None")
        path_label.setToolTip(f"No {field_prefix.lower()} selected")

    # Override accept to update the data model object BEFORE closing
    # This allows the NodeItem to compare old/new state for the Undo command
    def accept(self):
        """ Updates the NodeData object with values from the dialog fields. """
        print("Updating NodeData on Dialog Accept...")
        self.node_data.label = self.label_edit.text()
        self.node_data.node_type = self.type_combo.currentText()
        self.node_data.process_code = self.process_edit.toPlainText()
        self.node_data.transition_specs = self.transition_edit.toPlainText()
        self.node_data.display_properties['color'] = self.selected_color_name
        # Multimodal data
        self.node_data.custom_data.text = self.mm_text_edit.toPlainText() or None
        self.node_data.custom_data.generic_url = self.mm_url_edit.text() or None
        # File refs are updated directly by browse/clear methods

        # TODO: Parse and update structured data if editor exists
        # try:
        #     self.node_data.custom_data.structured_data = json.loads(self.mm_struct_edit.toPlainText())
        # except json.JSONDecodeError:
        #     QMessageBox.warning(self, "Input Error", "Invalid JSON in Structured Data field.")
        #     return # Prevent closing if JSON is invalid? Or save as string?

        super().accept() # Call the base class accept() which closes the dialog
``` 
