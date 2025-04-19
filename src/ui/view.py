```python
# src/ui/view.py
from PySide6.QtWidgets import QGraphicsView, QRubberBand
from PySide6.QtGui import QPainter, QCursor, QMouseEvent, QWheelEvent # Import event types
from PySide6.QtCore import Qt, QRect, QPoint

class DiagramView(QGraphicsView):
    """ Custom QGraphicsView for rendering the diagram scene. """
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        # --- Interaction Modes ---
        # Default to RubberBand for selection when clicking empty space
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        # Allow ScrollHandDrag with Middle Mouse Button
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setInteractive(True) # Ensure interactions are enabled

        # Store origin for panning
        self._pan_origin = QPoint()
        self._is_panning = False

    def wheelEvent(self, event: QWheelEvent):
        """ Handles mouse wheel events for zooming. """
        zoom_in_factor = 1.15
        zoom_out_factor = 1 / zoom_in_factor
        zoom_factor = zoom_in_factor if event.angleDelta().y() > 0 else zoom_out_factor

        # Save scene pos under cursor before zoom
        old_pos = self.mapToScene(event.position().toPoint())

        # Apply zoom
        self.scale(zoom_factor, zoom_factor)

        # Get scene pos under cursor after zoom
        new_pos = self.mapToScene(event.position().toPoint())

        # Move scene to keep cursor over the same spot
        delta = new_pos - old_pos
        self.translate(delta.x(), delta.y())
        event.accept() # Accept the event

    def mousePressEvent(self, event: QMouseEvent):
        """ Handles mouse press events for panning and selection. """
        scene_item = self.itemAt(event.pos())

        if event.button() == Qt.MouseButton.MiddleButton:
            # Start panning
            self._is_panning = True
            self._pan_origin = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self.setDragMode(QGraphicsView.DragMode.NoDrag) # Disable other drag modes during pan
            event.accept()
            return
        elif event.button() == Qt.MouseButton.LeftButton:
            # If clicking empty space, keep RubberBandDrag
            if not scene_item:
                 self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
            else:
                 # If clicking an item, let the item handle moves (NoDrag from view)
                 # This allows item's mousePress to correctly initiate MoveCommand tracking
                 self.setDragMode(QGraphicsView.DragMode.NoDrag)
        else:
             # For other buttons, disable view dragging
             self.setDragMode(QGraphicsView.DragMode.NoDrag)

        super().mousePressEvent(event) # Pass event to scene/items


    def mouseMoveEvent(self, event: QMouseEvent):
        """ Handles mouse move events for panning. """
        if self._is_panning:
            # Calculate delta and scroll
            delta = event.pos() - self._pan_origin
            hs = self.horizontalScrollBar()
            vs = self.verticalScrollBar()
            hs.setValue(hs.value() - delta.x())
            vs.setValue(vs.value() - delta.y())
            self._pan_origin = event.pos() # Update origin for next move delta
            event.accept()
            return

        super().mouseMoveEvent(event) # Pass for item dragging / rubber band


    def mouseReleaseEvent(self, event: QMouseEvent):
        """ Handles mouse release events to stop panning. """
        if event.button() == Qt.MouseButton.MiddleButton and self._is_panning:
            # Stop panning
            self._is_panning = False
            self.update_cursor(self.scene().current_mode) # Reset cursor based on current mode
            # Restore default drag mode? Depends on desired behavior after pan.
            # Let's keep RubberBandDrag as default for empty space clicks.
            self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
            event.accept()
            return

        super().mouseReleaseEvent(event) # Pass for selection/move end etc.
        # Restore default drag mode if it was NoDrag from clicking an item
        if self.dragMode() == QGraphicsView.DragMode.NoDrag:
             self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)


    def update_cursor(self, mode):
        """Changes the viewport cursor based on the current interaction mode."""
        if self._is_panning: # Keep panning cursor if active
             self.setCursor(Qt.CursorShape.ClosedHandCursor)
             return

        # Set cursor based on mode provided by MainWindow/Scene
        if mode == "link":
             self.setCursor(Qt.CursorShape.CrossCursor)
        elif mode == "execute":
             self.setCursor(Qt.CursorShape.PointingHandCursor)
        else: # select mode (or default)
             self.setCursor(Qt.CursorShape.ArrowCursor)

```
 
