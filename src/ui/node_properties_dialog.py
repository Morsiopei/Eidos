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
 
