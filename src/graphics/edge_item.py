```python
# src/graphics/edge_item.py
import math
from PySide6.QtWidgets import QGraphicsLineItem, QGraphicsItem, QStyleOptionGraphicsItem
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QPolygonF
from PySide6.QtCore import Qt, QLineF, QPointF, QRectF

# Import NodeItem for type hinting only, avoid circular import for logic
# from src.graphics.node_item import NodeItem <-- Causes circular import if NodeItem imports EdgeItem
# Use forward reference string instead:
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.graphics.node_item import NodeItem

from src.core.data_model import EdgeData

class EdgeItem(QGraphicsLineItem):
    """ Represents a directed edge (link) between two NodeItems. """
    def __init__(self, data: EdgeData, start_item: 'NodeItem', end_item: 'NodeItem', parent: QGraphicsItem = None):
        super().__init__(parent)
        self.edge_data = data
        self.start_item = start_item
        self.end_item = end_item

        # Graphics Setup
        self.setPen(QPen(QColor(data.display_properties.get('color', 'black')),
                         data.display_properties.get('width', 2),
                         Qt.PenStyle.SolidLine)) # Add style later if needed
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setZValue(-1) # Draw edges behind nodes

        # Arrowhead settings
        self.arrow_size = 15
        self.arrow_angle = math.radians(25) # Angle of arrowhead wings

        self.updatePosition()

    def get_id(self):
        """Returns the unique ID of the edge data."""
        return self.edge_data.id

    def boundingRect(self) -> QRectF:
        """ Ensure the bounding rect includes the arrowhead. """
        extra = (self.pen().widthF() + self.arrow_size) / 2.0
        p1 = self.line().p1()
        p2 = self.line().p2()
        return QRectF(p1, p2).normalized().adjusted(-extra, -extra, extra, extra)

    def updatePosition(self):
        """ Updates the line geometry based on connected node positions. """
        if not self.start_item or not self.end_item:
            # Hide or set to zero length if nodes are missing?
            self.setLine(0,0,0,0)
            return

        # Line between node centers
        center_line = QLineF(self.start_item.scenePos(), self.end_item.scenePos())

        # Optional: Adjust start/end points to touch node boundaries instead of centers
        # This requires knowing the node shapes (radius for ellipse)
        start_node_radius = self.start_item.boundingRect().width() / 2
        end_node_radius = self.end_item.boundingRect().width() / 2

        # Calculate intersection points (simplified for circles)
        if center_line.length() > start_node_radius + end_node_radius + 1: # Avoid overlap issues
             p1 = center_line.pointAt(start_node_radius / center_line.length())
             p2 = center_line.pointAt(1.0 - (end_node_radius / center_line.length()))
             adjusted_line = QLineF(p1, p2)
             self.setLine(adjusted_line)
        else:
             # Nodes are too close or overlapping, draw shorter line or hide?
             # Draw center-to-center if very close
             self.setLine(center_line)

        self.prepareGeometryChange() # Notify that geometry will change

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget=None):
        """ Draws the edge line and arrowhead. """
        if not self.start_item or not self.end_item or self.line().length() < 1:
            return

        line = self.line()
        painter.setPen(self.pen())
        painter.setBrush(self.pen().color()) # Arrowhead filled with line color

        # Draw the main line
        painter.drawLine(line)

        # --- Draw Arrowhead ---
        angle = math.atan2(-line.dy(), line.dx()) # Angle in radians

        # Calculate arrowhead points
        arrow_p1 = line.p2() # Tip of arrow is end of line
        arrow_p2 = arrow_p1 - QPointF(math.cos(angle + self.arrow_angle) * self.arrow_size,
                                       -math.sin(angle + self.arrow_angle) * self.arrow_size)
        arrow_p3 = arrow_p1 - QPointF(math.cos(angle - self.arrow_angle) * self.arrow_size,
                                       -math.sin(angle - self.arrow_angle) * self.arrow_size)

        arrow_head = QPolygonF([arrow_p1, arrow_p2, arrow_p3])
        painter.drawPolygon(arrow_head)
        # --- End Arrowhead ---

        # Optional: Draw selection highlight
        if option.state & QStyle.StateFlag.State_Selected:
            highlight_pen = QPen(QColor(0, 100, 200, 150), self.pen().widthF() + 2, Qt.PenStyle.DashLine)
            painter.setPen(highlight_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            # Draw slightly offset or around the bounding rect? Draw line again thicker.
            painter.drawLine(line)


    def destroy(self):
        """ Cleans up references when the edge is removed. """
        print(f"Destroying edge {self.get_id()}")
        # Remove references from connected nodes
        if self.start_item and hasattr(self.start_item, 'remove_edge_ref'):
            self.start_item.remove_edge_ref(self)
        if self.end_item and hasattr(self.end_item, 'remove_edge_ref'):
            self.end_item.remove_edge_ref(self)

        # Remove item from the scene
        if self.scene():
            self.scene().removeItem(self)

        # Clear local references (helps garbage collection)
        self.start_item = None
        self.end_item = None
```
 
