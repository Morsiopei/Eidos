```python
# src/graphics/node_item.py
import os
from PySide6.QtWidgets import (QGraphicsEllipseItem, QGraphicsItem, QStyleOptionGraphicsItem,
                               QMainWindow) # Import QMainWindow for finding parent
from PySide6.QtGui import (QPainter, QColor, QBrush, QPen, QFontMetrics, QFont,
                           QPixmap, QMouseEvent, QIcon) # Added QMouseEvent, QIcon
from PySide6.QtCore import Qt, QPointF, QRectF, Signal

from src.core.data_model import NodeData, MultiModalData
from src.ui.node_properties_dialog import NodePropertiesDialog
from src.utils.helpers import resource_path # For icons
# Avoid direct EdgeItem import to prevent circularity if EdgeItem imports NodeItem
# Use type hinting string 'EdgeItem' if needed

class NodeItem(QGraphicsEllipseItem):
    """ Represents a node in the diagram scene. """

    # Signal emitted when properties change that might require Undo command
    propertiesAboutToChange = Signal(dict) # Emits dict of old properties
    propertiesChanged = Signal(dict) # Emits dict of new properties

    def __init__(self, data: NodeData, parent: QGraphicsItem = None):
        self.node_data = data # Store data model object first
        radius = data.display_properties.get('radius', 40)
        super().__init__(-radius, -radius, 2 * radius, 2 * radius, parent)

        # Edge lists must be initialized before setPos is called indirectly by constructor
        self.edges_in = []
        self.edges_out = []

        # --- Graphics Setup ---
        # Position is set later by scene's add_node using data.position
        self.setBrush(QBrush(QColor(data.display_properties.get('color', 'skyblue'))))
        self.setPen(QPen(Qt.black, 2))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True) # Notify on move
        self.setAcceptHoverEvents(True) # For tooltips or hover effects
        self.setToolTip(f"ID: {data.id}\nType: {data.node_type}") # Basic tooltip

        # --- Load Indicator Icons ---
        try:
            icon_folder = resource_path("assets/icons")
            self.image_icon = QPixmap(os.path.join(icon_folder, "image_indicator.png"))
            self.audio_icon = QPixmap(os.path.join(icon_folder, "audio_indicator.png"))
            self.text_icon = QPixmap(os.path.join(icon_folder, "text_indicator.png"))
            # Resize icons if needed
            icon_size = 12
            self.image_icon = self.image_icon.scaled(icon_size, icon_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.audio_icon = self.audio_icon.scaled(icon_size, icon_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.text_icon = self.text_icon.scaled(icon_size, icon_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self._icons_loaded = True
        except Exception as e:
            print(f"Warning: Could not load indicator icons: {e}")
            self._icons_loaded = False


    def get_id(self):
        """ Returns the unique ID of the node data. """
        return self.node_data.id

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget=None):
        """ Draws the node ellipse, label, and indicators. """
        # Draw ellipse (default behavior)
        # Apply selection effect manually for better control?
        # painter.setPen(self.pen())
        # painter.setBrush(self.brush())
        # painter.drawEllipse(self.boundingRect())
        super().paint(painter, option, widget) # Use default paint for now

        # --- Draw Label ---
        painter.setPen(Qt.black)
        font = painter.font()
        font.setPointSize(10) # Consider making font size configurable
        painter.setFont(font)
        metrics = QFontMetrics(font)
        # Elide text if too long for the node radius
        available_width = self.boundingRect().width() - 10 # Padding
        elided_label = metrics.elidedText(self.node_data.label, Qt.TextElideMode.ElideRight, available_width)
        text_rect = metrics.boundingRect(elided_label)
        text_x = -text_rect.width() / 2
        text_y = -metrics.ascent() / 2 # Center vertically more accurately
        painter.drawText(QPointF(text_x, text_y), elided_label)

        # --- Draw Multimodal Indicators ---
        if self._icons_loaded:
            indicator_x_start = self.boundingRect().width() / 2 - 15 # Top-right corner inside node
            indicator_y = -self.boundingRect().height() / 2 + 5
            indicator_x = indicator_x_start
            spacing = self.image_icon.width() + 2 # Dynamic spacing

            # Draw icons from right to left
            if self.node_data.custom_data.image_ref:
                 painter.drawPixmap(int(indicator_x), int(indicator_y), self.image_icon)
                 indicator_x -= spacing
            if self.node_data.custom_data.audio_ref:
                 painter.drawPixmap(int(indicator_x), int(indicator_y), self.audio_icon)
                 indicator_x -= spacing
            if self.node_data.custom_data.text: # Check if text field has content
                 painter.drawPixmap(int(indicator_x), int(indicator_y), self.text_icon)
                 # indicator_x -= spacing # If more icons added


    def itemChange(self, change, value):
        """ Called when item state changes (e.g., position). """
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged and self.scene():
            # Update internal data model position when moved graphically
            new_pos = self.pos() # value is the new position QPointF
            self.node_data.position = (new_pos.x(), new_pos.y())
            # Notify connected edges to update their geometry
            for edge in self.edges_in + self.edges_out:
                if edge: # Check if edge reference is valid
                    edge.updatePosition()
        # Update tooltip if label changes (though label changes via dialog)
        # elif change == QGraphicsItem.GraphicsItemChange.ItemToolTipHasChanged:
        #    pass
        return super().itemChange(change, value)

    # --- Edge Reference Management ---
    def add_edge_ref(self, edge: 'EdgeItem', is_outgoing: bool):
         """ Stores a reference to a connected EdgeItem. """
         if is_outgoing:
             if edge not in self.edges_out: self.edges_out.append(edge)
         else:
             if edge not in self.edges_in: self.edges_in.append(edge)

    def remove_edge_ref(self, edge: 'EdgeItem'):
         """ Removes a reference to a connected EdgeItem. """
         if edge in self.edges_out: self.edges_out.remove(edge)
         if edge in self.edges_in: self.edges_in.remove(edge)

    # --- Properties Dialog Interaction ---
    def get_properties_dict(self) -> dict:
         """ Returns a dictionary representation of current editable properties. """
         # Used by ChangePropertiesCommand to store old/new state
         # TODO: Include relevant custom_data fields if they are editable and need undo
         return {
             "label": self.node_data.label,
             "node_type": self.node_data.node_type,
             "process_code": self.node_data.process_code,
             "transition_specs": self.node_data.transition_specs,
             "color": self.node_data.display_properties.get('color', 'skyblue'),
             # Add multimodal refs if needed for undo command granularity
             "image_ref": self.node_data.custom_data.image_ref,
             "audio_ref": self.node_data.custom_data.audio_ref,
             "text": self.node_data.custom_data.text,
         }

    def trigger_properties_dialog(self):
        """ Opens the properties dialog for this node. """
        main_window = self._find_main_window()
        if not main_window:
            print("Error: Could not find MainWindow parent for dialog.")
            return

        # Store old properties *before* dialog potentially changes them
        old_props = self.get_properties_dict()

        # Pass the *live* data object to the dialog
        # The dialog will modify this object directly upon accept()
        dialog = NodePropertiesDialog(self.node_data, parent=main_window)

        if dialog.exec(): # Returns 1 (Accepted) or 0 (Rejected)
            # --- Dialog Accepted: Properties were changed ---
            print(f"Properties accepted for node '{self.node_data.label}'")

            # Get new properties AFTER dialog modified node_data
            new_props = self.get_properties_dict()

            # Compare old and new to see what actually changed
            changed_props = {k: v for k, v in new_props.items() if v != old_props.get(k)}

            if changed_props:
                print(f"  Changes detected: {changed_props.keys()}")
                # Push ChangePropertiesCommand to undo stack
                if self.scene() and hasattr(self.scene(), 'undo_stack') and self.scene().undo_stack:
                     # Need old values for the keys that actually changed
                     old_changed_values = {k: old_props[k] for k in changed_props}
                     cmd = ChangePropertiesCommand(self.scene(), self.get_id(),
                                                   old_changed_values, changed_props,
                                                   f"Edit {self.node_data.label}")
                     self.scene().undo_stack.push(cmd)
                else:
                     print("Warning: Undo stack not available for property change.")


            # Update visual representation based on changes
            self.setBrush(QBrush(QColor(self.node_data.display_properties.get('color', 'skyblue'))))
            self.setToolTip(f"ID: {self.get_id()}\nType: {self.node_data.node_type}")
            self.update() # Trigger repaint for label, indicators, etc.
        else:
            # --- Dialog Rejected: Revert any potential direct changes (if any occurred) ---
            # Currently, dialog only modifies on accept(), so nothing needed here.
            # If dialog modified live object before accept, would need to restore old_props here.
            print(f"Property changes cancelled for node '{self.node_data.label}'")


    def mouseDoubleClickEvent(self, event: QMouseEvent):
        """ Handles double-click to open properties dialog. """
        self.trigger_properties_dialog()
        if event: event.accept() # Prevent further processing if event provided

    def _find_main_window(self) -> Optional[QMainWindow]:
         """ Traverses up the widget hierarchy to find the QMainWindow. """
         if not self.scene() or not self.scene().views():
             return None
         parent_widget = self.scene().views()[0] # Get the first view
         while parent_widget:
              if isinstance(parent_widget, QMainWindow):
                  return parent_widget
              parent_widget = parent_widget.parent()
         return None

``` 
