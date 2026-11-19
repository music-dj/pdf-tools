
import sys
import os
import subprocess
import tempfile
import math
import fitz  # PyMuPDF
from pdf2docx import Converter
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QTabWidget, QPushButton, QLabel, QFileDialog, QListWidget, 
    QAbstractItemView, QRadioButton, QLineEdit, QSpinBox, QColorDialog,
    QMessageBox, QGraphicsView, QGraphicsScene, QGraphicsPathItem,
    QGraphicsTextItem, QGraphicsRectItem, QInputDialog, QFontDialog, QGroupBox, QGridLayout,
    QListWidgetItem, QScrollArea, QCheckBox, QGraphicsItem, QProgressDialog, QSlider,
    QFontComboBox, QButtonGroup
)
from PyQt6.QtCore import Qt, QPointF, QSize, QRectF, QThread, pyqtSignal
from PyQt6.QtGui import QPen, QColor, QPainterPath, QPixmap, QImage, QIcon, QFont, QBrush, QTextCursor, QTextBlockFormat

# Custom GraphicsView supporting external file Drag & Drop
class DroppableGraphicsView(QGraphicsView):
    def __init__(self, on_file_dropped_callback, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.on_file_dropped = on_file_dropped_callback
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                file_path = urls[0].toLocalFile()
                self.on_file_dropped(file_path)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)


# Custom ListWidget supporting both internal reorder AND external file Drag & Drop
class DroppableListWidget(QListWidget):
    def __init__(self, on_files_dropped_callback, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.on_files_dropped = on_files_dropped_callback

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() or event.source() == self:
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls() or event.source() == self:
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            files = [url.toLocalFile() for url in event.mimeData().urls()]
            self.on_files_dropped(files)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)



class DropButton(QPushButton):
    def __init__(self, title, on_drop_callback, parent=None):
        super().__init__(title, parent)
        self.setAcceptDrops(True)
        self.on_drop = on_drop_callback

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                self.on_drop(urls[0].toLocalFile())
            event.acceptProposedAction()
        else:
            super().dropEvent(event)


# Custom ListWidget specifically engineered for visual page reordering (Drag & Drop + external PDF drop)
class PageReorderListWidget(QListWidget):
    def __init__(self, on_order_changed_cb=None, on_pdf_dropped_cb=None, parent=None):
        super().__init__(parent)
        self.on_order_changed = on_order_changed_cb
        self.on_pdf_dropped = on_pdf_dropped_cb
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() or event.source() == self:
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls() or event.source() == self:
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        # 1. External PDF file dropped -> trigger load
        if event.mimeData().hasUrls():
            pdf_urls = [u.toLocalFile() for u in event.mimeData().urls() if u.toLocalFile().lower().endswith('.pdf')]
            if pdf_urls and self.on_pdf_dropped:
                self.on_pdf_dropped(pdf_urls[0])
                event.acceptProposedAction()
                return

        # 2. Internal move -> reorder items accurately
        if event.source() == self:
            selected_items = self.selectedItems()
            if not selected_items:
                event.accept()
                return

            drop_pos = event.position().toPoint()
            target_item = self.itemAt(drop_pos)

            # Preserve selection order
            selected_rows = sorted([self.row(it) for it in selected_items])
            taken_items = [self.takeItem(r) for r in reversed(selected_rows)]
            taken_items.reverse()

            if target_item and target_item in [self.item(i) for i in range(self.count())]:
                target_rect = self.visualItemRect(target_item)
                if self.viewMode() == QListWidget.ViewMode.IconMode:
                    is_after = drop_pos.x() > target_rect.center().x()
                else:
                    is_after = drop_pos.y() > target_rect.center().y()
                dest_row = self.row(target_item) + (1 if is_after else 0)
            else:
                dest_row = self.count()

            dest_row = max(0, min(dest_row, self.count()))
            for i, it in enumerate(taken_items):
                self.insertItem(dest_row + i, it)
                it.setSelected(True)

            event.acceptProposedAction()
            if self.on_order_changed:
                self.on_order_changed()
        else:
            super().dropEvent(event)


class ResizableTextItem(QGraphicsTextItem):
    HANDLE_SIZE = 9

    def __init__(self, text="Type text here...", scene=None, parent=None):
        super().__init__(text, parent)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self.setDefaultTextColor(QColor(0, 0, 0))  # Default Black as requested
        self.setFont(QFont("Arial", 12))          # Default 12pt as requested

        self.resizing_handle = None
        self.drag_start_pos = QPointF()
        self.initial_font_size = 12
        self.initial_rect = QRectF()
        self.initial_pos = QPointF()
        self.is_editing = False
        self.alignment = 'left'
        self.on_size_changed_callback = None

    def boundingRect(self):
        r = super().boundingRect()
        hs = self.HANDLE_SIZE + 4.0
        return r.adjusted(-hs, -hs, hs, hs)

    def get_handle_rects(self):
        r = super().boundingRect()
        s = self.HANDLE_SIZE
        hs = s / 2.0
        return {
            'tl': QRectF(r.left() - hs, r.top() - hs, s, s),
            'tr': QRectF(r.right() - hs, r.top() - hs, s, s),
            'bl': QRectF(r.left() - hs, r.bottom() - hs, s, s),
            'br': QRectF(r.right() - hs, r.bottom() - hs, s, s),
        }

    def hoverMoveEvent(self, event):
        if self.isSelected() and not self.is_editing:
            pos = event.pos()
            handles = self.get_handle_rects()
            if handles['tl'].contains(pos) or handles['br'].contains(pos):
                self.setCursor(Qt.CursorShape.SizeFDiagCursor)
                return
            elif handles['tr'].contains(pos) or handles['bl'].contains(pos):
                self.setCursor(Qt.CursorShape.SizeBDiagCursor)
                return
        self.setCursor(Qt.CursorShape.SizeAllCursor if self.isSelected() and not self.is_editing else Qt.CursorShape.IBeamCursor)
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event):
        if self.isSelected() and not self.is_editing and event.button() == Qt.MouseButton.LeftButton:
            pos = event.pos()
            handles = self.get_handle_rects()
            for h_name, h_rect in handles.items():
                if h_rect.contains(pos):
                    self.resizing_handle = h_name
                    self.drag_start_pos = event.scenePos()
                    self.initial_font_size = max(6, self.font().pointSize())
                    rect = super().boundingRect()
                    self.initial_rect = rect
                    self.initial_pos = self.pos()
                    if h_name == 'br':
                        self.fixed_scene = self.mapToScene(rect.topLeft())
                        handle_scene = self.mapToScene(rect.bottomRight())
                    elif h_name == 'tl':
                        self.fixed_scene = self.mapToScene(rect.bottomRight())
                        handle_scene = self.mapToScene(rect.topLeft())
                    elif h_name == 'tr':
                        self.fixed_scene = self.mapToScene(rect.bottomLeft())
                        handle_scene = self.mapToScene(rect.topRight())
                    elif h_name == 'bl':
                        self.fixed_scene = self.mapToScene(rect.topRight())
                        handle_scene = self.mapToScene(rect.bottomLeft())
                    init_vec = handle_scene - self.fixed_scene
                    self.initial_dist = max(10.0, math.hypot(init_vec.x(), init_vec.y()))
                    event.accept()
                    return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.resizing_handle and hasattr(self, 'fixed_scene'):
            self.prepareGeometryChange()
            curr_vec = event.scenePos() - self.fixed_scene
            curr_dist = max(10.0, math.hypot(curr_vec.x(), curr_vec.y()))
            ratio = curr_dist / self.initial_dist

            new_size = max(6, min(144, int(round(self.initial_font_size * ratio))))
            f = self.font()
            if f.pointSize() != new_size:
                f.setPointSize(new_size)
                self.setFont(f)

                # Keep anchored corner fixed in scene coordinates
                new_rect = super().boundingRect()
                if self.resizing_handle == 'tl':
                    self.setPos(self.fixed_scene - new_rect.bottomRight())
                elif self.resizing_handle == 'tr':
                    self.setPos(self.fixed_scene - new_rect.bottomLeft())
                elif self.resizing_handle == 'bl':
                    self.setPos(self.fixed_scene - new_rect.topRight())
                elif self.resizing_handle == 'br':
                    self.setPos(self.fixed_scene - new_rect.topLeft())

                if self.on_size_changed_callback:
                    self.on_size_changed_callback(new_size)

            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.resizing_handle:
            self.resizing_handle = None
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.start_editing()
        super().mouseDoubleClickEvent(event)

    def start_editing(self):
        self.is_editing = True
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        cursor = self.textCursor()
        cursor.select(QTextCursor.SelectionType.Document)
        self.setTextCursor(cursor)

    def focusOutEvent(self, event):
        self.is_editing = False
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        cursor = self.textCursor()
        cursor.clearSelection()
        self.setTextCursor(cursor)
        super().focusOutEvent(event)

    def set_alignment(self, align_type):
        self.alignment = align_type
        doc = self.document()
        if align_type == 'right':
            qt_align = Qt.AlignmentFlag.AlignRight
        elif align_type == 'center':
            qt_align = Qt.AlignmentFlag.AlignHCenter
        else:
            qt_align = Qt.AlignmentFlag.AlignLeft

        opt = doc.defaultTextOption()
        opt.setAlignment(qt_align)
        doc.setDefaultTextOption(opt)

        cursor = QTextCursor(doc)
        cursor.select(QTextCursor.SelectionType.Document)
        block_fmt = QTextBlockFormat()
        block_fmt.setAlignment(qt_align)
        cursor.mergeBlockFormat(block_fmt)
        cursor.clearSelection()
        self.setTextCursor(cursor)
        self.update()

    def keyPressEvent(self, event):
        if self.is_editing or (self.textInteractionFlags() & Qt.TextInteractionFlag.TextEditorInteraction):
            super().keyPressEvent(event)
            return
        if event.key() == Qt.Key.Key_Delete:
            if self.scene():
                self.scene().removeItem(self)
                return
        super().keyPressEvent(event)

    def paint(self, painter, option, widget):
        super().paint(painter, option, widget)
        is_saving = getattr(self.scene(), 'is_saving', False)
        if self.isSelected() and not self.is_editing and not is_saving:
            painter.save()
            pen = QPen(QColor('#89b4fa'), 1, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(super().boundingRect())

            painter.setPen(QPen(QColor('#11111b'), 1))
            painter.setBrush(QBrush(QColor('#89b4fa')))
            for h_rect in self.get_handle_rects().values():
                painter.drawRect(h_rect)
            painter.restore()


class InteractiveScene(QGraphicsScene):
    shared_clipboard = None

    def __init__(self, parent=None):
        super().__init__(parent)
        self.drawing = False
        self.start_point = QPointF()
        self.current_path_item = None
        self.current_path = QPainterPath()
        self.current_rect_item = None
        self.pen = QPen(QColor("red"), 3, Qt.PenStyle.SolidLine)
        self.mode = "select" 
        self.is_saving = False

        # Undo / Redo stacks
        self.undo_stack = []
        self.redo_stack = []

        # Text properties
        self.text_font_family = "Arial"
        self.text_font_size = 12
        self.text_color = QColor(0, 0, 0)
        self.text_bold = False
        self.text_italic = False
        self.text_underline = False
        self.on_mode_change_cb = None
        self.on_text_size_changed_cb = None

    def push_undo_action(self, action):
        self.undo_stack.append(action)
        self.redo_stack.clear()

    def undo(self):
        if not self.undo_stack:
            return
        action = self.undo_stack.pop()
        self.redo_stack.append(action)
        act_type = action.get('type')
        item = action.get('item')
        if act_type == 'add':
            if item and item.scene() == self:
                self.removeItem(item)
        elif act_type == 'remove':
            if item and item.scene() != self:
                self.addItem(item)
                item.setSelected(True)

    def redo(self):
        if not self.redo_stack:
            return
        action = self.redo_stack.pop()
        self.undo_stack.append(action)
        act_type = action.get('type')
        item = action.get('item')
        if act_type == 'add':
            if item and item.scene() != self:
                self.addItem(item)
                item.setSelected(True)
        elif act_type == 'remove':
            if item and item.scene() == self:
                self.removeItem(item)

    def copy_selected(self):
        selected = [it for it in self.selectedItems() if isinstance(it, ResizableTextItem)]
        if selected:
            it = selected[0]
            InteractiveScene.shared_clipboard = {
                'text': it.toPlainText(),
                'font': QFont(it.font()),
                'color': QColor(it.defaultTextColor()),
                'alignment': getattr(it, 'alignment', 'right'),
                'opacity': it.opacity(),
                'pos': it.pos()
            }

    def paste(self):
        data = InteractiveScene.shared_clipboard
        if not data:
            return
        new_item = ResizableTextItem(data['text'], scene=self)
        new_item.setFont(QFont(data['font']))
        new_item.setDefaultTextColor(QColor(data['color']))
        new_item.set_alignment(data.get('alignment', 'right'))
        new_item.setOpacity(data.get('opacity', 1.0))
        new_pos = data['pos'] + QPointF(25, 25)
        new_item.setPos(new_pos)
        data['pos'] = new_pos  # cascade subsequent pastes
        new_item.on_size_changed_callback = self.on_text_size_changed_cb
        self.addItem(new_item)
        self.push_undo_action({'type': 'add', 'item': new_item})
        self.clearSelection()
        new_item.setSelected(True)

    def duplicate_selected(self):
        self.copy_selected()
        self.paste()

    def mousePressEvent(self, event):
        if self.mode == "draw":
            self.drawing = True
            self.current_path = QPainterPath()
            self.current_path.moveTo(event.scenePos())
            self.current_path_item = QGraphicsPathItem(self.current_path)
            self.current_path_item.setPen(self.pen)
            self.current_path_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
            self.current_path_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
            self.addItem(self.current_path_item)

        elif self.mode in ["rect", "solid_rect"]:
            self.drawing = True
            self.start_point = event.scenePos()
            self.current_rect_item = QGraphicsRectItem(QRectF(self.start_point, self.start_point))
            self.current_rect_item.setPen(self.pen)
            
            if self.mode == "solid_rect":
                self.current_rect_item.setBrush(QBrush(self.pen.color()))
                
            self.current_rect_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
            self.current_rect_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
            self.addItem(self.current_rect_item)

        elif self.mode == "text":
            font = QFont(self.text_font_family, self.text_font_size)
            font.setBold(self.text_bold)
            font.setItalic(self.text_italic)
            font.setUnderline(self.text_underline)

            text_item = ResizableTextItem("Type text here...", scene=self)
            text_item.setFont(font)
            text_item.setDefaultTextColor(self.text_color)
            text_item.set_alignment(getattr(self, 'text_alignment', 'right'))
            text_item.setPos(event.scenePos())
            text_item.on_size_changed_callback = self.on_text_size_changed_cb

            self.addItem(text_item)
            self.push_undo_action({'type': 'add', 'item': text_item})
            self.clearSelection()
            text_item.setSelected(True)
            text_item.start_editing()
            self.mode = "select"
            if self.on_mode_change_cb:
                self.on_mode_change_cb("select")
            return
        
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.mode == "draw" and self.drawing and self.current_path_item:
            self.current_path.lineTo(event.scenePos())
            self.current_path_item.setPath(self.current_path)

        elif self.mode in ["rect", "solid_rect"] and self.drawing and self.current_rect_item:
            p2 = event.scenePos()
            self.current_rect_item.setRect(QRectF(self.start_point, p2).normalized())

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.drawing:
            if self.current_path_item:
                self.push_undo_action({'type': 'add', 'item': self.current_path_item})
            elif self.current_rect_item:
                self.push_undo_action({'type': 'add', 'item': self.current_rect_item})
            self.drawing = False
            self.current_path_item = None
            self.current_rect_item = None
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        # If an item is being edited or has focus, let it handle the key directly
        focus_item = self.focusItem()
        if focus_item and (getattr(focus_item, 'is_editing', False) or 
                           focus_item.textInteractionFlags() != Qt.TextInteractionFlag.NoTextInteraction):
            super().keyPressEvent(event)
            return

        ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)

        # Undo: Ctrl+Z
        if ctrl and not shift and event.key() == Qt.Key.Key_Z:
            self.undo()
            return

        # Redo: Ctrl+Y or Ctrl+Shift+Z
        if (ctrl and event.key() == Qt.Key.Key_Y) or (ctrl and shift and event.key() == Qt.Key.Key_Z):
            self.redo()
            return

        # Copy: Ctrl+C
        if ctrl and event.key() == Qt.Key.Key_C:
            self.copy_selected()
            return

        # Paste: Ctrl+V
        if ctrl and event.key() == Qt.Key.Key_V:
            self.paste()
            return

        # Duplicate: Ctrl+D
        if ctrl and event.key() == Qt.Key.Key_D:
            self.duplicate_selected()
            return

        # NEVER delete on Backspace! Only delete selected items on the Delete key when not editing
        if event.key() == Qt.Key.Key_Delete:
            for item in self.selectedItems():
                if not getattr(item, 'is_editing', False):
                    self.push_undo_action({'type': 'remove', 'item': item})
                    self.removeItem(item)
            return

        super().keyPressEvent(event)



class GenericWorker(QThread):
    progress = pyqtSignal(int)
    finished_signal = pyqtSignal(object)
    error_signal = pyqtSignal(str)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            self.kwargs['progress_cb'] = self.progress.emit
            res = self.fn(*self.args, **self.kwargs)
            self.finished_signal.emit(res)
        except Exception as e:
            self.error_signal.emit(str(e))

class ModernUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF Master Pro V3.2")
        self.setGeometry(100, 100, 1180, 820)
        
        # Set Window and Taskbar Icon
        icon_path = self.get_resource_path("engine pdf.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            
        self.setStyleSheet("""
            QMainWindow { background-color: #1e1e2e; }
            QWidget { color: #cdd6f4; font-family: 'Segoe UI', Arial; font-size: 13px; }
            
            /* Main Top Tabs */
            QTabWidget#main_tabs::pane { border: 1px solid #45475a; border-radius: 8px; background-color: #181825; }
            QTabWidget#main_tabs > QTabBar::tab { background: #313244; color: #a6adc8; padding: 11px 26px; margin: 3px; border-radius: 6px; font-weight: bold; font-size: 13px; }
            QTabWidget#main_tabs > QTabBar::tab:selected { background: #89b4fa; color: #11111b; font-weight: bold; }
            QTabWidget#main_tabs > QTabBar::tab:hover:!selected { background: #45475a; color: #cdd6f4; }
            
            /* Nested Sub Tabs */
            QTabWidget#sub_tabs::pane { border: 1px solid #313244; border-radius: 6px; background-color: #181825; padding: 5px; }
            QTabWidget#sub_tabs > QTabBar::tab { background: #1e1e2e; color: #a6adc8; padding: 8px 18px; margin: 2px; border-radius: 5px; font-weight: bold; font-size: 12px; }
            QTabWidget#sub_tabs > QTabBar::tab:selected { background: #45475a; color: #89b4fa; }
            QTabWidget#sub_tabs > QTabBar::tab:hover:!selected { background: #313244; color: #cdd6f4; }
            
            QPushButton { background-color: #45475a; color: #cdd6f4; border: none; padding: 8px 16px; border-radius: 5px; font-weight: bold; }
            QPushButton:hover { background-color: #585b70; }
            QPushButton:disabled { background-color: #313244; color: #7f849c; }
            QLineEdit, QSpinBox, QGroupBox, QScrollArea { background-color: #181825; border: 1px solid #45475a; padding: 5px; border-radius: 5px; }
            QListWidget { background-color: #181825; border: 1px solid #45475a; border-radius: 5px; outline: none; }
            QListWidget::item:selected { background-color: #45475a; border-radius: 3px; }
            QGroupBox { border: 1px solid #45475a; border-radius: 6px; margin-top: 1.2ex; font-weight: bold; padding-top: 10px; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; color: #89b4fa; }
            QCheckBox, QRadioButton { padding: 4px; }
        """)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("main_tabs")
        main_layout.addWidget(self.tabs)

        self.setup_organize_master_tab()
        self.setup_convert_master_tab()
        self.setup_edit_master_tab()
        self.setup_compress_master_tab()

        footer = QLabel("© 2026 MRT — All Rights Reserved")
        footer.setAlignment(Qt.AlignmentFlag.AlignRight)
        footer.setStyleSheet("color: #a6adc8; font-size: 11px; padding: 5px;")
        main_layout.addWidget(footer)

    def run_background_task(self, title, work_func, on_success, *args, **kwargs):
        self.progress_dlg = QProgressDialog(title, "Cancel", 0, 100, self)
        self.progress_dlg.setWindowTitle("Processing")
        self.progress_dlg.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dlg.setValue(0)
        self.progress_dlg.setAutoClose(True)
        self.progress_dlg.setAutoReset(True)
        
        self.worker = GenericWorker(work_func, *args, **kwargs)
        self.worker.progress.connect(self.progress_dlg.setValue)
        
        def handle_finish(res):
            self.progress_dlg.setValue(100)
            on_success(res)
            
        def handle_error(err):
            self.progress_dlg.close()
            self.show_msg("Error", f"Failed: {err}")
            
        self.worker.finished_signal.connect(handle_finish)
        self.worker.error_signal.connect(handle_error)
        self.progress_dlg.canceled.connect(self.worker.terminate)
        
        self.worker.start()
        self.progress_dlg.show()

    def get_resource_path(self, relative_path):
        if hasattr(sys, '_MEIPASS'):
            return os.path.join(sys._MEIPASS, relative_path)
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)

    def get_bin_dir(self):
        candidates = []
        # 1. Inside PyInstaller bundle (_MEIPASS)
        if hasattr(sys, '_MEIPASS'):
            candidates.append(os.path.join(sys._MEIPASS, "bin"))
        # 2. Next to running executable
        if getattr(sys, 'frozen', False):
            exe_dir = os.path.dirname(sys.executable)
            candidates.append(os.path.join(exe_dir, "bin"))
            candidates.append(os.path.join(exe_dir, "..", "bin"))
        # 3. Next to script / current file
        script_dir = os.path.dirname(os.path.abspath(__file__))
        candidates.append(os.path.join(script_dir, "bin"))
        candidates.append(os.path.join(script_dir, "..", "bin"))
        # 4. Known project locations
        candidates.append(r"E:\برامجي\برنامج pdf\برنامج pdf v2\bin")
        candidates.append(r"E:\برامجي\برنامج pdf\bin")
        candidates.append(r"C:\Users\smart\Desktop\برنامج pdf\bin")

        # Prioritize path that has both required tools
        for cand in candidates:
            if os.path.exists(cand):
                gs = os.path.join(cand, "gswin64c.exe")
                cpdf = os.path.join(cand, "cpdf.exe")
                if os.path.exists(gs) and os.path.exists(cpdf):
                    return os.path.abspath(cand)

        # Fallback to first existing candidate
        for cand in candidates:
            if os.path.exists(cand):
                return os.path.abspath(cand)

        return os.path.join(script_dir, "bin")

    def get_auto_output_path(self, input_path, suffix, new_ext=None):
        dir_name = os.path.dirname(os.path.abspath(input_path))
        base_name, old_ext = os.path.splitext(os.path.basename(input_path))
        ext = new_ext if new_ext else old_ext
        out_name = f"{base_name}_{suffix}{ext}"
        out_path = os.path.join(dir_name, out_name)
        
        counter = 1
        while os.path.exists(out_path):
            out_name = f"{base_name}_{suffix}_{counter}{ext}"
            out_path = os.path.join(dir_name, out_name)
            counter += 1
            
        return out_path

    def show_msg(self, title, message):
        QMessageBox.information(self, title, message)

    def pixmap_to_qimage(self, pix):
        if pix.alpha:
            fmt = QImage.Format.Format_RGBA8888
        else:
            fmt = QImage.Format.Format_RGB888
        img = QImage(pix.samples, pix.width, pix.height, pix.stride, fmt)
        return img.copy()

    def get_thumbnail(self, path):
        try:
            if path.lower().endswith('.pdf'):
                doc = fitz.open(path)
                pix = doc[0].get_pixmap(dpi=36)
                img = self.pixmap_to_qimage(pix)
                doc.close()
                return QIcon(QPixmap.fromImage(img))
            else:
                pm = QPixmap(path)
                if not pm.isNull():
                    return QIcon(pm.scaled(150, 150, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                from PIL import Image
                from PIL.ImageQt import ImageQt
                with Image.open(path) as pil_img:
                    pil_img.thumbnail((150, 150))
                    qimg = ImageQt(pil_img)
                    return QIcon(QPixmap.fromImage(qimg))
        except:
            return QIcon()

    def update_list_numbers(self, list_widget):
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            original_path = item.data(Qt.ItemDataRole.UserRole)
            if original_path:
                filename = os.path.basename(original_path)
                item.setText(f"{i+1}. {filename}")
            else:
                orig_page = item.data(Qt.ItemDataRole.UserRole + 1)
                item.setText(f"Page {i+1} (was {orig_page+1})")

    def build_list_ui(self, filter_str, parent_layout, valid_extensions):
        def handle_external_drop(files):
            valid_files = [f for f in files if any(f.lower().endswith(ext) for ext in valid_extensions)]
            self.add_specific_files_to_list(list_widget, valid_files)

        list_widget = DroppableListWidget(handle_external_drop)
        list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        list_widget.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        list_widget.setAcceptDrops(True)
        list_widget.setDragEnabled(True)
        list_widget.setDefaultDropAction(Qt.DropAction.MoveAction)
        list_widget.setIconSize(QSize(100, 100))
        list_widget.setViewMode(QListWidget.ViewMode.ListMode)
        list_widget.setResizeMode(QListWidget.ResizeMode.Adjust)
        
        list_widget.model().rowsMoved.connect(lambda: self.update_list_numbers(list_widget))
        parent_layout.addWidget(list_widget)

        btn_layout = QHBoxLayout()
        btn_add = QPushButton("➕ Add Files")
        btn_remove = QPushButton("🗑️ Remove Selected")
        btn_remove.setStyleSheet("background-color: #f38ba8; color: #11111b;")
        btn_view_list = QPushButton("📄 List View")
        btn_view_icon = QPushButton("🖼️ Thumbnail View")

        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_remove)
        btn_layout.addWidget(btn_view_list)
        btn_layout.addWidget(btn_view_icon)

        btn_add.clicked.connect(lambda: self.add_files_to_list(list_widget, filter_str))
        btn_remove.clicked.connect(lambda: self.remove_selected_items(list_widget))
        btn_view_list.clicked.connect(lambda: list_widget.setViewMode(QListWidget.ViewMode.ListMode))
        btn_view_icon.clicked.connect(lambda: list_widget.setViewMode(QListWidget.ViewMode.IconMode))
        
        return list_widget, btn_layout

    def remove_selected_items(self, list_widget):
        for item in list_widget.selectedItems():
            list_widget.takeItem(list_widget.row(item))
        self.update_list_numbers(list_widget)

    def add_specific_files_to_list(self, list_widget, files):
        for f in files:
            item = QListWidgetItem()
            item.setToolTip(f)
            item.setData(Qt.ItemDataRole.UserRole, f)
            item.setIcon(self.get_thumbnail(f))
            item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsDragEnabled)
            list_widget.addItem(item)
        self.update_list_numbers(list_widget)

    def add_files_to_list(self, list_widget, filter_str):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Files", "", filter_str)
        self.add_specific_files_to_list(list_widget, files)

    def sort_and_update(self, list_widget):
        list_widget.sortItems()
        self.update_list_numbers(list_widget)

    # ================= MASTER TAB 1: ORGANIZE & PAGES =================
    def setup_organize_master_tab(self):
        tab = QWidget()
        vl = QVBoxLayout(tab)
        sub = QTabWidget()
        sub.setObjectName("sub_tabs")

        # Sub 1: Merge
        w_merge = QWidget()
        vm = QVBoxLayout(w_merge)
        self.pdf_list, pdf_btns = self.build_list_ui("PDF Files (*.pdf)", vm, ['.pdf'])
        self.pdf_list.setViewMode(QListWidget.ViewMode.IconMode)
        vm.addLayout(pdf_btns)
        hm = QHBoxLayout()
        btn_sort_pdf = QPushButton("🔤 Sort Alphabetically")
        btn_sort_pdf.clicked.connect(lambda: self.sort_and_update(self.pdf_list))
        btn_merge = QPushButton("🔗 Merge PDFs Now")
        btn_merge.setStyleSheet("background-color: #89b4fa; color: #11111b; font-weight: bold; padding: 10px;")
        btn_merge.clicked.connect(self.merge_pdfs)
        hm.addWidget(btn_sort_pdf)
        hm.addWidget(btn_merge)
        vm.addLayout(hm)
        sub.addTab(w_merge, "🔗 Merge PDFs")

        # Sub 2: Split
        w_split = self.create_split_widget()
        sub.addTab(w_split, "✂️ Split PDF")

        # Sub 3: Reorder
        w_reorder = self.create_reorder_widget()
        sub.addTab(w_reorder, "🗂️ Reorder Pages")

        vl.addWidget(sub)
        self.tabs.addTab(tab, "📑 Organize Pages")

    # ================= MASTER TAB 2: CONVERT HUB =================
    def setup_convert_master_tab(self):
        tab = QWidget()
        vl = QVBoxLayout(tab)
        sub = QTabWidget()
        sub.setObjectName("sub_tabs")

        # Sub A: Images to PDF
        w_img2pdf = QWidget()
        vi = QVBoxLayout(w_img2pdf)
        img_filter = "Image Files (*.png *.jpg *.jpeg *.jfif *.webp *.bmp *.tiff *.tif *.ico *.gif);;All Files (*.*)"
        img_exts = ['.png', '.jpg', '.jpeg', '.jfif', '.webp', '.bmp', '.tiff', '.tif', '.ico', '.gif']
        self.img_list, list_btns = self.build_list_ui(img_filter, vi, img_exts)
        self.img_list.setViewMode(QListWidget.ViewMode.IconMode)
        vi.addLayout(list_btns)
        action_layout = QHBoxLayout()
        btn_sort = QPushButton("🔤 Sort Alphabetically")
        btn_sort.clicked.connect(lambda: self.sort_and_update(self.img_list))
        self.radio_high = QRadioButton("High Quality")
        self.radio_fast = QRadioButton("Fast Quality (Compressed)")
        self.radio_high.setChecked(True)
        btn_convert = QPushButton("✨ Convert Images to PDF Now")
        btn_convert.setStyleSheet("background-color: #a6e3a1; color: #11111b; font-weight: bold; padding: 10px;")
        btn_convert.clicked.connect(self.images_to_pdf)
        action_layout.addWidget(btn_sort)
        action_layout.addWidget(self.radio_high)
        action_layout.addWidget(self.radio_fast)
        action_layout.addWidget(btn_convert)
        vi.addLayout(action_layout)
        sub.addTab(w_img2pdf, "🖼️ Images to PDF")

        # Sub B: Word to PDF
        w_w2p = QWidget()
        vw = QVBoxLayout(w_w2p)
        grp_w2p = QGroupBox("📘 Microsoft Word to PDF (Native 100% Fidelity)")
        gl_w = QVBoxLayout(grp_w2p)
        lbl_w_info = QLabel("Converts .docx and .doc documents using native Word engine with exact preservation of Arabic fonts, layout, and tables.")
        lbl_w_info.setStyleSheet("color: #a6adc8; padding: 8px; font-size: 13px;")
        btn_w2p = DropButton("📄 Select Word Document (.docx, .doc — Drag & Drop Supported)", self.word_to_pdf)
        btn_w2p.setStyleSheet("background-color: #89b4fa; color: #11111b; font-weight: bold; font-size: 14px; padding: 14px;")
        btn_w2p.clicked.connect(lambda: self.word_to_pdf())
        gl_w.addWidget(lbl_w_info)
        gl_w.addWidget(btn_w2p)
        vw.addWidget(grp_w2p)
        vw.addStretch()
        sub.addTab(w_w2p, "📘 Word to PDF")

        # Sub C: Word to Pages
        w_w2pages = QWidget()
        vwp = QVBoxLayout(w_w2pages)
        grp_w2pages = QGroupBox("📘 Microsoft Word to Pages (تفكيك مستند الوورد إلى صفحات منفردة)")
        gl_wp = QVBoxLayout(grp_w2pages)
        lbl_wp_info = QLabel(
            "Converts a multi-page Microsoft Word document (.docx, .doc) into individual single-page files.\n"
            "Guarantees 100% exact original layout, crisp vector fonts, Arabic ligatures, and tables using the native Word engine."
        )
        lbl_wp_info.setStyleSheet("color: #a6adc8; padding: 10px; font-size: 13px; line-height: 1.4;")
        
        fmt_layout = QHBoxLayout()
        lbl_fmt = QLabel("Output Format:")
        lbl_fmt.setStyleSheet("font-weight: bold; color: #cdd6f4;")
        self.radio_w2p_pdf = QRadioButton("📑 Single-Page PDF (100% Exact Native Fidelity - Recommended)")
        self.radio_w2p_docx = QRadioButton("📝 Single-Page Word (.docx)")
        self.radio_w2p_both = QRadioButton("📦 Both (PDF + DOCX)")
        self.radio_w2p_pdf.setChecked(True)
        fmt_layout.addWidget(lbl_fmt)
        fmt_layout.addWidget(self.radio_w2p_pdf)
        fmt_layout.addWidget(self.radio_w2p_docx)
        fmt_layout.addWidget(self.radio_w2p_both)
        fmt_layout.addStretch()

        btn_w2pages = DropButton("📄 Select Word Document to Split into Pages (Drag & Drop Supported)", self.word_to_pages)
        btn_w2pages.setStyleSheet("background-color: #a6e3a1; color: #11111b; font-weight: bold; font-size: 14px; padding: 14px;")
        btn_w2pages.clicked.connect(lambda: self.word_to_pages())
        
        gl_wp.addWidget(lbl_wp_info)
        gl_wp.addLayout(fmt_layout)
        gl_wp.addWidget(btn_w2pages)
        vwp.addWidget(grp_w2pages)
        vwp.addStretch()
        sub.addTab(w_w2pages, "📑 Word to Pages")

        # Sub C: PDF to Word
        w_p2w = QWidget()
        vp = QVBoxLayout(w_p2w)
        grp_p2w = QGroupBox("📝 PDF to Microsoft Word (.docx)")
        gl_p = QVBoxLayout(grp_p2w)
        lbl_p_info = QLabel("Extracts and converts PDF pages into an editable Word document.")
        lbl_p_info.setStyleSheet("color: #a6adc8; padding: 8px; font-size: 13px;")
        btn_p2w = DropButton("📄 Select PDF to Convert to Word (Drag & Drop Supported)", self.pdf_to_word)
        btn_p2w.setStyleSheet("background-color: #74c7ec; color: #11111b; font-weight: bold; font-size: 14px; padding: 14px;")
        btn_p2w.clicked.connect(lambda: self.pdf_to_word())
        gl_p.addWidget(lbl_p_info)
        gl_p.addWidget(btn_p2w)
        vp.addWidget(grp_p2w)
        vp.addStretch()
        sub.addTab(w_p2w, "📝 PDF to Word")

        # Sub D: PDF to Images
        w_p2i = QWidget()
        vi2 = QVBoxLayout(w_p2i)
        grp_p2i = QGroupBox("📸 PDF to High-Resolution Images")
        gl_i = QVBoxLayout(grp_p2i)
        lbl_i_info = QLabel("Extracts all pages from a PDF as 300 DPI high-resolution PNG images into an automatic subfolder.")
        lbl_i_info.setStyleSheet("color: #a6adc8; padding: 8px; font-size: 13px;")
        btn_p2i = DropButton("📸 Select PDF & Extract Images (Drag & Drop Supported)", self.pdf_to_images)
        btn_p2i.setStyleSheet("background-color: #fab387; color: #11111b; font-weight: bold; font-size: 14px; padding: 14px;")
        btn_p2i.clicked.connect(lambda: self.pdf_to_images())
        gl_i.addWidget(lbl_i_info)
        gl_i.addWidget(btn_p2i)
        vi2.addWidget(grp_p2i)
        vi2.addStretch()
        sub.addTab(w_p2i, "📸 PDF to Images")

        # Sub E: Convert to Pages
        w_p2p = QWidget()
        vp_pages = QVBoxLayout(w_p2p)
        grp_p2p = QGroupBox("📑 Convert PDF to Single Page PDFs (100% Lossless Original Quality)")
        gl_pages = QVBoxLayout(grp_p2p)
        lbl_p2p_info = QLabel(
            "Converts a multi-page PDF into separate individual PDF files for every page.\n"
            "Guarantees 100% exact original clarity, crisp vector fonts, and lossless images without any rasterization or degradation."
        )
        lbl_p2p_info.setStyleSheet("color: #a6adc8; padding: 10px; font-size: 13px; line-height: 1.4;")
        btn_p2p = DropButton("📑 Select PDF to Convert to Pages (Drag & Drop Supported)", self.pdf_to_pages)
        btn_p2p.setStyleSheet("background-color: #a6e3a1; color: #11111b; font-weight: bold; font-size: 14px; padding: 14px;")
        btn_p2p.clicked.connect(lambda *a: self.pdf_to_pages())
        gl_pages.addWidget(lbl_p2p_info)
        gl_pages.addWidget(btn_p2p)
        vp_pages.addWidget(grp_p2p)
        vp_pages.addStretch()
        sub.addTab(w_p2p, "📑 Convert to Pages")

        # Sub F: Rotate PDF
        w_rotate = self.create_rotate_widget()
        sub.addTab(w_rotate, "🔄 Rotate PDF")

        vl.addWidget(sub)
        self.tabs.addTab(tab, "🔄 Convert Hub")

    # ================= MASTER TAB 3: EDIT & ANNOTATE =================
    def setup_edit_master_tab(self):
        tab = QWidget()
        vl = QVBoxLayout(tab)
        sub = QTabWidget()
        sub.setObjectName("sub_tabs")

        w_draw = self.create_draw_widget()
        sub.addTab(w_draw, "🎨 Draw & Edit")

        w_num = self.create_annotation_widget()
        sub.addTab(w_num, "🔢 Page Numbering")

        vl.addWidget(sub)
        self.tabs.addTab(tab, "🎨 Edit & Annotate")

    # ================= MASTER TAB 4: SMART COMPRESS =================
    def setup_compress_master_tab(self):
        w_comp = self.create_compress_widget()
        self.tabs.addTab(w_comp, "🗜️ Smart Compress")

    def images_to_pdf(self):
        if self.img_list.count() == 0: return
        img_paths = [self.img_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.img_list.count())]
        out_path = self.get_auto_output_path(img_paths[0], "converted", ".pdf")
        is_fast = self.radio_fast.isChecked()
        def work(progress_cb):
            import fitz
            doc = fitz.open()
            total = len(img_paths)
            for i, p in enumerate(img_paths):
                try:
                    with fitz.open(p) as img:
                        rect = img[0].rect
                        pdfbytes = img.convert_to_pdf()
                except Exception:
                    from PIL import Image
                    import io
                    with Image.open(p) as pil_img:
                        if pil_img.mode in ("RGBA", "LA", "P"):
                            pil_img = pil_img.convert("RGB")
                        buf = io.BytesIO()
                        pil_img.save(buf, format="JPEG", quality=95)
                        buf.seek(0)
                        with fitz.open(stream=buf.read(), filetype="jpeg") as img:
                            rect = img[0].rect
                            pdfbytes = img.convert_to_pdf()
                with fitz.open("pdf", pdfbytes) as img_doc:
                    page = doc.new_page(width=rect.width, height=rect.height)
                    if is_fast:
                        pix = img_doc[0].get_pixmap(dpi=72)
                        page.insert_image(rect, pixmap=pix)
                        pix = None
                    else:
                        page.show_pdf_page(rect, img_doc, 0)
                progress_cb(int(((i + 1) / total) * 95))
            doc.save(out_path)
            doc.close()
            progress_cb(100)
        self.run_background_task("Converting Images to PDF...", work, lambda r: self.show_msg("Success", f"Saved successfully to:\n{out_path}"))

    def merge_pdfs(self):
        if self.pdf_list.count() == 0: return
        pdf_paths = [self.pdf_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.pdf_list.count())]
        out_path = self.get_auto_output_path(pdf_paths[0], "merged", ".pdf")
        def work(progress_cb):
            import fitz
            result = fitz.open()
            total = len(pdf_paths)
            for i, p in enumerate(pdf_paths):
                with fitz.open(p) as doc:
                    result.insert_pdf(doc)
                progress_cb(int(((i + 1) / total) * 90))
            result.save(out_path)
            result.close()
            progress_cb(100)
        self.run_background_task("Merging PDFs...", work, lambda r: self.show_msg("Success", f"Merged successfully to:\n{out_path}"))

    def create_split_widget(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        control_hl = QHBoxLayout()
        btn_load = DropButton("📂 1. Open PDF to Split (Drag & Drop)", self.load_pdf_for_split)
        btn_load.clicked.connect(lambda: self.load_pdf_for_split())
        
        self.lbl_split_info = QLabel("No PDF loaded.")
        
        btn_save = QPushButton("✂️ 2. Save Selected Pages")
        btn_save.setStyleSheet("background-color: #fab387; color: #11111b;")
        btn_save.clicked.connect(self.save_split_pdf)
        
        control_hl.addWidget(btn_load)
        control_hl.addWidget(self.lbl_split_info)
        control_hl.addWidget(btn_save)
        layout.addLayout(control_hl)

        self.split_scroll = QScrollArea()
        self.split_scroll.setWidgetResizable(True)
        self.split_container = QWidget()
        self.split_grid = QGridLayout(self.split_container)
        self.split_scroll.setWidget(self.split_container)
        layout.addWidget(self.split_scroll)
        
        self.split_checkboxes = []
        self.split_pdf_path = None
        return tab

    def load_pdf_for_split(self, path=None):
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, "Select PDF", "", "PDF Files (*.pdf)")
        if not path: return
        self.split_pdf_path = path
        
        for i in reversed(range(self.split_grid.count())): 
            widget = self.split_grid.itemAt(i).widget()
            if widget: widget.deleteLater()
        self.split_checkboxes.clear()

        doc = fitz.open(path)
        self.lbl_split_info.setText(f"Loaded: {os.path.basename(path)} ({len(doc)} pages)")
        
        row, col = 0, 0
        for i in range(len(doc)):
            page = doc[i]
            pix = page.get_pixmap(dpi=36)
            img = self.pixmap_to_qimage(pix)
            
            box = QWidget()
            box_layout = QVBoxLayout(box)
            lbl_img = QLabel()
            lbl_img.setPixmap(QPixmap.fromImage(img))
            lbl_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
            chk = QCheckBox(f"Page {i+1}")
            chk.setChecked(True)
            box_layout.addWidget(lbl_img)
            box_layout.addWidget(chk)
            self.split_grid.addWidget(box, row, col)
            self.split_checkboxes.append(chk)
            
            col += 1
            if col > 4: 
                col = 0; row += 1
        doc.close()

    def save_split_pdf(self):
        if not self.split_pdf_path: return
        selected_pages = [i for i, chk in enumerate(self.split_checkboxes) if chk.isChecked()]
        if not selected_pages: return self.show_msg("Warning", "No pages selected!")
        in_path = self.split_pdf_path
        out_path = self.get_auto_output_path(in_path, "split", ".pdf")
        def work(progress_cb):
            import fitz
            progress_cb(10)
            with fitz.open(in_path) as doc:
                new_doc = fitz.open()
                total = len(selected_pages)
                for i, p_idx in enumerate(selected_pages):
                    new_doc.insert_pdf(doc, from_page=p_idx, to_page=p_idx)
                    progress_cb(10 + int(((i + 1) / total) * 80))
                new_doc.save(out_path)
                new_doc.close()
            progress_cb(100)
        self.run_background_task("Saving Selected Pages...", work, lambda r: self.show_msg("Success", f"Split saved successfully ({len(selected_pages)} pages) to:\n{out_path}"))

    def create_reorder_widget(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        control_hl = QHBoxLayout()
        btn_load = DropButton("📂 1. Open PDF to Reorder (Drag & Drop)", self.load_pdf_for_reorder)
        btn_load.clicked.connect(lambda *a: self.load_pdf_for_reorder())
        
        self.lbl_reorder_info = QLabel("Open a PDF. Drag pages or use arrow buttons to reorder.")
        self.lbl_reorder_info.setStyleSheet("color: #a6adc8; font-weight: 500;")
        
        btn_save = QPushButton("🔄 2. Save Reordered PDF")
        btn_save.setStyleSheet("background-color: #89b4fa; color: #11111b; font-weight: bold; padding: 10px 18px;")
        btn_save.clicked.connect(self.save_reorder_pdf)
        
        control_hl.addWidget(btn_load)
        control_hl.addWidget(self.lbl_reorder_info, 1)
        control_hl.addWidget(btn_save)
        layout.addLayout(control_hl)

        self.reorder_list = PageReorderListWidget(
            on_order_changed_cb=self.update_reorder_labels,
            on_pdf_dropped_cb=self.load_pdf_for_reorder
        )
        self.reorder_list.setIconSize(QSize(120, 160))
        self.reorder_list.setGridSize(QSize(150, 205))
        self.reorder_list.setSpacing(8)
        self.reorder_list.setViewMode(QListWidget.ViewMode.IconMode)
        self.reorder_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.reorder_list.setMovement(QListWidget.Movement.Snap)
        
        btn_layout = QHBoxLayout()
        btn_first = QPushButton("⏮ To First")
        btn_left = QPushButton("◀ Move Left")
        btn_right = QPushButton("▶ Move Right")
        btn_last = QPushButton("⏭ To Last")
        btn_reverse = QPushButton("🔄 Reverse All")
        btn_remove = QPushButton("🗑️ Remove Page")
        btn_remove.setStyleSheet("background-color: #f38ba8; color: #11111b; font-weight: bold;")
        btn_view_list = QPushButton("📄 List View")
        btn_view_icon = QPushButton("🖼️ Grid View")

        btn_first.clicked.connect(lambda *a: self.reorder_move_extreme(to_end=False))
        btn_left.clicked.connect(lambda *a: self.reorder_move_selected(delta=-1))
        btn_right.clicked.connect(lambda *a: self.reorder_move_selected(delta=1))
        btn_last.clicked.connect(lambda *a: self.reorder_move_extreme(to_end=True))
        btn_reverse.clicked.connect(self.reorder_reverse_all)
        btn_remove.clicked.connect(self.remove_reorder_items)
        btn_view_list.clicked.connect(lambda *a: self.reorder_list.setViewMode(QListWidget.ViewMode.ListMode))
        btn_view_icon.clicked.connect(lambda *a: self.reorder_list.setViewMode(QListWidget.ViewMode.IconMode))

        btn_layout.addWidget(btn_first)
        btn_layout.addWidget(btn_left)
        btn_layout.addWidget(btn_right)
        btn_layout.addWidget(btn_last)
        btn_layout.addWidget(btn_reverse)
        btn_layout.addWidget(btn_remove)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_view_list)
        btn_layout.addWidget(btn_view_icon)
        
        layout.addLayout(btn_layout)
        layout.addWidget(self.reorder_list)
        
        self.reorder_pdf_path = None
        return tab

    def reorder_move_selected(self, delta):
        count = self.reorder_list.count()
        if count <= 1:
            return
        selected_items = self.reorder_list.selectedItems()
        if not selected_items:
            return

        selected_rows = sorted([self.reorder_list.row(it) for it in selected_items])
        if delta < 0:
            if selected_rows[0] == 0:
                return
            for r in selected_rows:
                it = self.reorder_list.takeItem(r)
                self.reorder_list.insertItem(r - 1, it)
                it.setSelected(True)
        else:
            if selected_rows[-1] == count - 1:
                return
            for r in reversed(selected_rows):
                it = self.reorder_list.takeItem(r)
                self.reorder_list.insertItem(r + 1, it)
                it.setSelected(True)
        self.update_reorder_labels()

    def reorder_move_extreme(self, to_end=False):
        count = self.reorder_list.count()
        if count <= 1:
            return
        selected_items = self.reorder_list.selectedItems()
        if not selected_items:
            return

        selected_rows = sorted([self.reorder_list.row(it) for it in selected_items])
        taken_items = [self.reorder_list.takeItem(r) for r in reversed(selected_rows)]
        taken_items.reverse()

        if not to_end:
            for i, it in enumerate(taken_items):
                self.reorder_list.insertItem(i, it)
                it.setSelected(True)
        else:
            for it in taken_items:
                self.reorder_list.addItem(it)
                it.setSelected(True)
        self.update_reorder_labels()

    def reorder_reverse_all(self):
        count = self.reorder_list.count()
        if count <= 1:
            return
        items = [self.reorder_list.takeItem(0) for _ in range(count)]
        for it in items:
            self.reorder_list.insertItem(0, it)
        self.update_reorder_labels()

    def remove_reorder_items(self):
        for item in self.reorder_list.selectedItems():
            self.reorder_list.takeItem(self.reorder_list.row(item))
        self.update_reorder_labels()

    def update_reorder_labels(self):
        count = self.reorder_list.count()
        for i in range(count):
            item = self.reorder_list.item(i)
            orig_page = item.data(Qt.ItemDataRole.UserRole + 1)
            if orig_page is not None:
                item.setText(f"Page {i+1} (was {orig_page+1})")
        if hasattr(self, 'lbl_reorder_info'):
            self.lbl_reorder_info.setText(f"Total: {count} pages. Drag & drop or use buttons to reorder.")

    def load_pdf_for_reorder(self, path=None):
        if not path or not isinstance(path, str):
            path, _ = QFileDialog.getOpenFileName(self, "Select PDF to Reorder", "", "PDF Files (*.pdf)")
        if not path or not os.path.exists(path):
            return
        self.reorder_pdf_path = path
        self.reorder_list.clear()

        doc = fitz.open(path)
        for i in range(len(doc)):
            page = doc[i]
            pix = page.get_pixmap(dpi=72)
            img = self.pixmap_to_qimage(pix)
            item = QListWidgetItem()
            item.setIcon(QIcon(QPixmap.fromImage(img)))
            item.setData(Qt.ItemDataRole.UserRole + 1, i)
            item.setFlags(
                Qt.ItemFlag.ItemIsSelectable |
                Qt.ItemFlag.ItemIsEnabled |
                Qt.ItemFlag.ItemIsDragEnabled |
                Qt.ItemFlag.ItemIsDropEnabled
            )
            self.reorder_list.addItem(item)
        doc.close()
        self.update_reorder_labels()

    def save_reorder_pdf(self):
        if not self.reorder_pdf_path or self.reorder_list.count() == 0:
            self.show_msg("Notice", "Please open a PDF file with pages first.")
            return
        new_order = [self.reorder_list.item(i).data(Qt.ItemDataRole.UserRole + 1) for i in range(self.reorder_list.count())]
        in_path = self.reorder_pdf_path
        out_path = self.get_auto_output_path(in_path, "reordered", ".pdf")
        def work(progress_cb):
            import fitz
            progress_cb(20)
            doc = fitz.open(in_path)
            doc.select(new_order)
            progress_cb(80)
            doc.save(out_path, deflate=True)
            doc.close()
            progress_cb(100)
        self.run_background_task("Saving Reordered PDF...", work, lambda r: self.show_msg("Success", f"Reordered PDF saved successfully to:\n{out_path}"))

    def create_draw_widget(self):
        tab = QWidget()
        vl = QVBoxLayout(tab)
        
        tools_hl = QHBoxLayout()
        btn_load = QPushButton("📂 Load Image / PDF")
        btn_load.clicked.connect(self.load_canvas_dialog)
        
        self.btn_mode_select = QPushButton("↖️ Cursor (Move/Del)")
        self.btn_mode_draw = QPushButton("🖋️ Pen")
        self.btn_mode_rect = QPushButton("🔲 Rect (Outline)")
        self.btn_mode_srect = QPushButton("⬛ Rect (Solid)")
        self.btn_mode_text = QPushButton("🔤 Text")
        
        btn_color = QPushButton("🎨 Color")
        btn_color.setStyleSheet("background-color: #f9e2af; color: #11111b;")
        btn_color.clicked.connect(self.pick_draw_color)
        
        self.current_draw_mode = 'select'
        self.current_draw_color = QColor("red")

        self.btn_mode_select.clicked.connect(lambda: self.set_draw_mode('select'))
        self.btn_mode_draw.clicked.connect(lambda: self.set_draw_mode('draw'))
        self.btn_mode_rect.clicked.connect(lambda: self.set_draw_mode('rect'))
        self.btn_mode_srect.clicked.connect(lambda: self.set_draw_mode('solid_rect'))
        self.btn_mode_text.clicked.connect(lambda: self.set_draw_mode('text'))

        btn_undo = QPushButton("↩️ Undo")
        btn_undo.setToolTip("Undo last action (Ctrl+Z)")
        btn_undo.setStyleSheet("background-color: #585b70; color: #cdd6f4;")
        btn_undo.clicked.connect(self.on_undo_clicked)

        btn_redo = QPushButton("↪️ Redo")
        btn_redo.setToolTip("Redo last undone action (Ctrl+Y)")
        btn_redo.setStyleSheet("background-color: #585b70; color: #cdd6f4;")
        btn_redo.clicked.connect(self.on_redo_clicked)
        
        btn_save_canvas = QPushButton("💾 Save File")
        btn_save_canvas.setStyleSheet("background-color: #89dceb; color: #11111b;")
        btn_save_canvas.clicked.connect(self.save_canvas)
        
        tools_hl.addWidget(btn_load)
        tools_hl.addWidget(self.btn_mode_select)
        tools_hl.addWidget(self.btn_mode_draw)
        tools_hl.addWidget(self.btn_mode_rect)
        tools_hl.addWidget(self.btn_mode_srect)
        tools_hl.addWidget(self.btn_mode_text)
        tools_hl.addWidget(btn_color)
        tools_hl.addWidget(btn_undo)
        tools_hl.addWidget(btn_redo)
        tools_hl.addWidget(btn_save_canvas)
        vl.addLayout(tools_hl)

        # Dedicated Text Editing & Formatting Bar
        text_bar_hl = QHBoxLayout()
        lbl_text_title = QLabel("🔤 Text Tools:")
        lbl_text_title.setStyleSheet("font-weight: bold; color: #89b4fa; font-size: 13px;")

        self.combo_font_family = QFontComboBox()
        self.combo_font_family.setCurrentFont(QFont("Arial"))
        self.combo_font_family.setStyleSheet("background-color: #45475a; color: #cdd6f4; padding: 4px; border-radius: 4px;")
        self.combo_font_family.currentFontChanged.connect(self.on_text_font_family_changed)

        lbl_size = QLabel("Size:")
        lbl_size.setStyleSheet("color: #a6adc8;")
        self.spin_font_size = QSpinBox()
        self.spin_font_size.setRange(6, 144)
        self.spin_font_size.setValue(12)  # Default 12 pt as requested
        self.spin_font_size.setSuffix(" pt")
        self.spin_font_size.setStyleSheet("background-color: #45475a; color: #cdd6f4; padding: 4px; border-radius: 4px;")
        self.spin_font_size.valueChanged.connect(self.on_text_font_size_changed)

        self.current_text_color = QColor(0, 0, 0)  # Default Black as requested
        self.btn_text_color = QPushButton("⬛ Color")
        self.update_text_color_button_style()
        self.btn_text_color.clicked.connect(self.pick_text_color)

        self.btn_text_bold = QPushButton("𝐁")
        self.btn_text_bold.setCheckable(True)
        self.btn_text_bold.setFixedWidth(36)
        self.btn_text_bold.setToolTip("Bold")
        self.btn_text_bold.setStyleSheet("background-color: #45475a; color: #cdd6f4; font-weight: bold; border-radius: 4px; padding: 4px;")
        self.btn_text_bold.toggled.connect(self.on_text_bold_toggled)

        self.btn_text_italic = QPushButton("𝑰")
        self.btn_text_italic.setCheckable(True)
        self.btn_text_italic.setFixedWidth(36)
        self.btn_text_italic.setToolTip("Italic")
        self.btn_text_italic.setStyleSheet("background-color: #45475a; color: #cdd6f4; font-style: italic; border-radius: 4px; padding: 4px;")
        self.btn_text_italic.toggled.connect(self.on_text_italic_toggled)

        self.btn_text_underline = QPushButton("𝐔")
        self.btn_text_underline.setCheckable(True)
        self.btn_text_underline.setFixedWidth(36)
        self.btn_text_underline.setToolTip("Underline")
        self.btn_text_underline.setStyleSheet("background-color: #45475a; color: #cdd6f4; border-radius: 4px; padding: 4px;")
        self.btn_text_underline.toggled.connect(self.on_text_underline_toggled)

        # Text Alignment buttons
        lbl_align = QLabel("Align:")
        lbl_align.setStyleSheet("color: #a6adc8; margin-left: 6px;")

        self.btn_align_right = QPushButton("⫸ يمين")
        self.btn_align_right.setCheckable(True)
        self.btn_align_right.setChecked(True)
        self.btn_align_right.setToolTip("Align Right (محاذاة لليمين - عربي)")
        self.btn_align_right.setStyleSheet("background-color: #45475a; color: #cdd6f4; border-radius: 4px; padding: 4px 8px;")
        self.btn_align_right.clicked.connect(lambda: self.on_text_align_clicked('right'))

        self.btn_align_center = QPushButton("⫿ توسيط")
        self.btn_align_center.setCheckable(True)
        self.btn_align_center.setToolTip("Align Center (توسيط في المنتصف)")
        self.btn_align_center.setStyleSheet("background-color: #45475a; color: #cdd6f4; border-radius: 4px; padding: 4px 8px;")
        self.btn_align_center.clicked.connect(lambda: self.on_text_align_clicked('center'))

        self.btn_align_left = QPushButton("⫷ يسار")
        self.btn_align_left.setCheckable(True)
        self.btn_align_left.setToolTip("Align Left (محاذاة لليسار)")
        self.btn_align_left.setStyleSheet("background-color: #45475a; color: #cdd6f4; border-radius: 4px; padding: 4px 8px;")
        self.btn_align_left.clicked.connect(lambda: self.on_text_align_clicked('left'))

        self.align_group = QButtonGroup(self)
        self.align_group.addButton(self.btn_align_right)
        self.align_group.addButton(self.btn_align_center)
        self.align_group.addButton(self.btn_align_left)
        self.current_text_alignment = 'right'

        # Opacity / Transparency control
        lbl_opacity = QLabel("Opacity:")
        lbl_opacity.setStyleSheet("color: #a6adc8; margin-left: 6px;")
        self.slider_opacity = QSlider(Qt.Orientation.Horizontal)
        self.slider_opacity.setRange(10, 100)
        self.slider_opacity.setValue(100)
        self.slider_opacity.setFixedWidth(70)
        self.slider_opacity.setToolTip("Adjust text transparency / opacity (10% - 100%)")
        self.slider_opacity.valueChanged.connect(self.on_text_opacity_changed)
        self.lbl_opacity_val = QLabel("100%")
        self.lbl_opacity_val.setStyleSheet("color: #89b4fa; font-size: 11px; min-width: 32px;")

        # Copy / Paste / Duplicate buttons
        self.btn_copy_text = QPushButton("📋 Copy")
        self.btn_copy_text.setToolTip("Copy selected text box (Ctrl+C)")
        self.btn_copy_text.setStyleSheet("background-color: #45475a; color: #cdd6f4; border-radius: 4px; padding: 4px 8px;")
        self.btn_copy_text.clicked.connect(self.on_copy_text_clicked)

        self.btn_paste_text = QPushButton("📋 Paste")
        self.btn_paste_text.setToolTip("Paste copied text box (Ctrl+V)")
        self.btn_paste_text.setStyleSheet("background-color: #45475a; color: #cdd6f4; border-radius: 4px; padding: 4px 8px;")
        self.btn_paste_text.clicked.connect(self.on_paste_text_clicked)

        self.btn_dup_text = QPushButton("📑 Duplicate")
        self.btn_dup_text.setToolTip("Duplicate selected text box (Ctrl+D)")
        self.btn_dup_text.setStyleSheet("background-color: #45475a; color: #cdd6f4; border-radius: 4px; padding: 4px 8px;")
        self.btn_dup_text.clicked.connect(self.on_duplicate_text_clicked)

        self.btn_edit_text_inline = QPushButton("✏️ Edit Text")
        self.btn_edit_text_inline.setToolTip("Edit text in-place (or double click text directly)")
        self.btn_edit_text_inline.setStyleSheet("background-color: #f9e2af; color: #11111b; font-weight: bold; border-radius: 4px; padding: 4px 10px;")
        self.btn_edit_text_inline.clicked.connect(self.on_edit_text_clicked)

        self.btn_delete_text = QPushButton("🗑️ Delete")
        self.btn_delete_text.setStyleSheet("background-color: #f38ba8; color: #11111b; font-weight: bold; border-radius: 4px; padding: 4px 10px;")
        self.btn_delete_text.clicked.connect(self.on_delete_selected_items)

        text_bar_hl.addWidget(lbl_text_title)
        text_bar_hl.addWidget(self.combo_font_family)
        text_bar_hl.addWidget(lbl_size)
        text_bar_hl.addWidget(self.spin_font_size)
        text_bar_hl.addWidget(self.btn_text_color)
        text_bar_hl.addWidget(self.btn_text_bold)
        text_bar_hl.addWidget(self.btn_text_italic)
        text_bar_hl.addWidget(self.btn_text_underline)
        text_bar_hl.addWidget(lbl_align)
        text_bar_hl.addWidget(self.btn_align_right)
        text_bar_hl.addWidget(self.btn_align_center)
        text_bar_hl.addWidget(self.btn_align_left)
        text_bar_hl.addWidget(lbl_opacity)
        text_bar_hl.addWidget(self.slider_opacity)
        text_bar_hl.addWidget(self.lbl_opacity_val)
        text_bar_hl.addWidget(self.btn_copy_text)
        text_bar_hl.addWidget(self.btn_paste_text)
        text_bar_hl.addWidget(self.btn_dup_text)
        text_bar_hl.addWidget(self.btn_edit_text_inline)
        text_bar_hl.addWidget(self.btn_delete_text)
        text_bar_hl.addStretch()
        vl.addLayout(text_bar_hl)

        nav_hl = QHBoxLayout()
        btn_prev = QPushButton("◀ Prev Page")
        btn_prev.clicked.connect(self.prev_draw_page)
        
        self.lbl_draw_page = QLabel("Page 0 / 0 (Drag & Drop File Here)")
        self.lbl_draw_page.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        btn_next = QPushButton("Next Page ▶")
        btn_next.clicked.connect(self.next_draw_page)
        
        nav_hl.addWidget(btn_prev)
        nav_hl.addWidget(self.lbl_draw_page)
        nav_hl.addWidget(btn_next)
        nav_hl.addStretch()
        vl.addLayout(nav_hl)

        # Uses DroppableGraphicsView so images/PDFs can be dropped directly onto the canvas
        self.draw_view = DroppableGraphicsView(self.load_canvas_file)
        self.draw_view.setStyleSheet("background-color: #313244;")
        vl.addWidget(self.draw_view)

        self.draw_scenes = {}
        self.draw_current_page = 0
        self.draw_doc = None
        self.draw_pdf_path = None

        return tab

    def update_text_color_button_style(self):
        c = self.current_text_color
        bg_hex = c.name()
        text_hex = "#ffffff" if (c.red()*0.299 + c.green()*0.587 + c.blue()*0.114) < 128 else "#000000"
        self.btn_text_color.setStyleSheet(f"background-color: {bg_hex}; color: {text_hex}; font-weight: bold; border: 1px solid #cdd6f4; border-radius: 4px; padding: 4px 10px;")

    def pick_text_color(self):
        c = QColorDialog.getColor(self.current_text_color, self, "Select Text Color")
        if c.isValid():
            self.current_text_color = c
            self.update_text_color_button_style()
            if hasattr(self, 'draw_view') and self.draw_view.scene():
                scene = self.draw_view.scene()
                scene.text_color = c
                for item in scene.selectedItems():
                    if isinstance(item, ResizableTextItem):
                        item.setDefaultTextColor(c)

    def on_text_font_size_changed(self, size):
        if hasattr(self, 'draw_view') and self.draw_view.scene():
            scene = self.draw_view.scene()
            scene.text_font_size = size
            for item in scene.selectedItems():
                if isinstance(item, ResizableTextItem):
                    f = item.font()
                    if f.pointSize() != size:
                        f.setPointSize(size)
                        item.setFont(f)

    def on_text_font_family_changed(self, font):
        family = font.family()
        if hasattr(self, 'draw_view') and self.draw_view.scene():
            scene = self.draw_view.scene()
            scene.text_font_family = family
            for item in scene.selectedItems():
                if isinstance(item, ResizableTextItem):
                    f = item.font()
                    f.setFamily(family)
                    item.setFont(f)

    def on_text_bold_toggled(self, checked):
        if hasattr(self, 'draw_view') and self.draw_view.scene():
            scene = self.draw_view.scene()
            scene.text_bold = checked
            for item in scene.selectedItems():
                if isinstance(item, ResizableTextItem):
                    f = item.font()
                    f.setBold(checked)
                    item.setFont(f)

    def on_text_italic_toggled(self, checked):
        if hasattr(self, 'draw_view') and self.draw_view.scene():
            scene = self.draw_view.scene()
            scene.text_italic = checked
            for item in scene.selectedItems():
                if isinstance(item, ResizableTextItem):
                    f = item.font()
                    f.setItalic(checked)
                    item.setFont(f)

    def on_text_underline_toggled(self, checked):
        if hasattr(self, 'draw_view') and self.draw_view.scene():
            scene = self.draw_view.scene()
            scene.text_underline = checked
            for item in scene.selectedItems():
                if isinstance(item, ResizableTextItem):
                    f = item.font()
                    f.setUnderline(checked)
                    item.setFont(f)

    def on_text_align_clicked(self, align_type):
        self.current_text_alignment = align_type
        if hasattr(self, 'draw_view') and self.draw_view.scene():
            for item in self.draw_view.scene().selectedItems():
                if isinstance(item, ResizableTextItem):
                    item.set_alignment(align_type)

    def on_edit_text_clicked(self):
        if hasattr(self, 'draw_view') and self.draw_view.scene():
            for item in self.draw_view.scene().selectedItems():
                if isinstance(item, ResizableTextItem):
                    item.start_editing()
                    return

    def on_undo_clicked(self):
        if hasattr(self, 'draw_view') and self.draw_view.scene():
            self.draw_view.scene().undo()

    def on_redo_clicked(self):
        if hasattr(self, 'draw_view') and self.draw_view.scene():
            self.draw_view.scene().redo()

    def on_copy_text_clicked(self):
        if hasattr(self, 'draw_view') and self.draw_view.scene():
            self.draw_view.scene().copy_selected()

    def on_paste_text_clicked(self):
        if hasattr(self, 'draw_view') and self.draw_view.scene():
            self.draw_view.scene().paste()

    def on_duplicate_text_clicked(self):
        if hasattr(self, 'draw_view') and self.draw_view.scene():
            self.draw_view.scene().duplicate_selected()

    def on_text_opacity_changed(self, val):
        self.lbl_opacity_val.setText(f"{val}%")
        if hasattr(self, 'draw_view') and self.draw_view.scene():
            for item in self.draw_view.scene().selectedItems():
                if isinstance(item, ResizableTextItem):
                    item.setOpacity(val / 100.0)

    def on_delete_selected_items(self):
        if hasattr(self, 'draw_view') and self.draw_view.scene():
            scene = self.draw_view.scene()
            for item in scene.selectedItems():
                scene.push_undo_action({'type': 'remove', 'item': item})
                scene.removeItem(item)

    def on_scene_selection_changed(self):
        if not hasattr(self, 'draw_view') or not self.draw_view.scene():
            return
        selected = self.draw_view.scene().selectedItems()
        for item in selected:
            if isinstance(item, ResizableTextItem):
                f = item.font()
                self.spin_font_size.blockSignals(True)
                self.spin_font_size.setValue(f.pointSize())
                self.spin_font_size.blockSignals(False)

                self.combo_font_family.blockSignals(True)
                self.combo_font_family.setCurrentFont(f)
                self.combo_font_family.blockSignals(False)

                self.btn_text_bold.blockSignals(True)
                self.btn_text_bold.setChecked(f.bold())
                self.btn_text_bold.blockSignals(False)

                self.btn_text_italic.blockSignals(True)
                self.btn_text_italic.setChecked(f.italic())
                self.btn_text_italic.blockSignals(False)

                self.btn_text_underline.blockSignals(True)
                self.btn_text_underline.setChecked(f.underline())
                self.btn_text_underline.blockSignals(False)

                align = getattr(item, 'alignment', 'right')
                if hasattr(self, 'btn_align_right'):
                    self.btn_align_right.blockSignals(True)
                    self.btn_align_center.blockSignals(True)
                    self.btn_align_left.blockSignals(True)
                    self.btn_align_right.setChecked(align == 'right')
                    self.btn_align_center.setChecked(align == 'center')
                    self.btn_align_left.setChecked(align == 'left')
                    self.btn_align_right.blockSignals(False)
                    self.btn_align_center.blockSignals(False)
                    self.btn_align_left.blockSignals(False)

                op_val = int(round(item.opacity() * 100))
                if hasattr(self, 'slider_opacity'):
                    self.slider_opacity.blockSignals(True)
                    self.slider_opacity.setValue(op_val)
                    self.lbl_opacity_val.setText(f"{op_val}%")
                    self.slider_opacity.blockSignals(False)

                self.current_text_color = item.defaultTextColor()
                self.update_text_color_button_style()
                break

    def on_text_size_changed_from_scene(self, size):
        self.spin_font_size.blockSignals(True)
        self.spin_font_size.setValue(size)
        self.spin_font_size.blockSignals(False)

    def create_interactive_scene(self):
        scene = InteractiveScene(self)
        scene.mode = self.current_draw_mode
        pen = QPen(self.current_draw_color, 3, Qt.PenStyle.SolidLine)
        scene.pen = pen
        if hasattr(self, 'combo_font_family'):
            scene.text_font_family = self.combo_font_family.currentFont().family()
        if hasattr(self, 'spin_font_size'):
            scene.text_font_size = self.spin_font_size.value()
        if hasattr(self, 'current_text_color'):
            scene.text_color = self.current_text_color
        if hasattr(self, 'btn_text_bold'):
            scene.text_bold = self.btn_text_bold.isChecked()
        if hasattr(self, 'btn_text_italic'):
            scene.text_italic = self.btn_text_italic.isChecked()
        if hasattr(self, 'btn_text_underline'):
            scene.text_underline = self.btn_text_underline.isChecked()
        scene.text_alignment = getattr(self, 'current_text_alignment', 'right')
        scene.on_mode_change_cb = self.set_draw_mode
        scene.on_text_size_changed_cb = self.on_text_size_changed_from_scene
        scene.selectionChanged.connect(self.on_scene_selection_changed)
        return scene

    def set_draw_mode(self, mode):
        self.current_draw_mode = mode
        if hasattr(self, 'draw_view') and self.draw_view.scene():
            self.draw_view.scene().mode = mode

    def pick_draw_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.current_draw_color = color
            if hasattr(self, 'draw_view') and self.draw_view.scene():
                pen = self.draw_view.scene().pen
                pen.setColor(color)
                self.draw_view.scene().pen = pen

    def load_canvas_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open File", "", "Files (*.pdf *.png *.jpg *.jpeg *.jfif *.webp *.bmp *.tiff *.tif *.ico *.gif);;All Files (*.*)")
        if path:
            self.load_canvas_file(path)

    def load_canvas_file(self, path):
        if not path or not os.path.exists(path): return
        
        self.draw_scenes = {}
        self.draw_current_page = 0
        
        if self.draw_doc:
            self.draw_doc.close()
            
        if path.lower().endswith('.pdf'):
            self.draw_pdf_path = path
            self.draw_doc = fitz.open(path)
            self.update_draw_page_view()
        else:
            self.draw_pdf_path = path
            self.draw_doc = None
            
            scene = self.create_interactive_scene()
            
            pixmap = QPixmap(path)
            bg_item = scene.addPixmap(pixmap)
            scene.setSceneRect(QRectF(pixmap.rect()))
            
            self.draw_scenes[0] = {'scene': scene, 'bg_item': bg_item}
            self.draw_view.setScene(scene)
            self.lbl_draw_page.setText("Image 1 / 1")

    def update_draw_page_view(self):
        if not self.draw_doc: return
        
        if self.draw_current_page not in self.draw_scenes:
            scene = self.create_interactive_scene()
            page = self.draw_doc[self.draw_current_page]
            pix = page.get_pixmap(dpi=150)
            img = self.pixmap_to_qimage(pix)
            pixmap = QPixmap.fromImage(img)
            
            bg_item = scene.addPixmap(pixmap)
            scene.setSceneRect(QRectF(pixmap.rect()))
            self.draw_scenes[self.draw_current_page] = {'scene': scene, 'bg_item': bg_item}

        active_scene = self.draw_scenes[self.draw_current_page]['scene']
        self.draw_view.setScene(active_scene)
        
        self.set_draw_mode(self.current_draw_mode)
        pen = active_scene.pen
        pen.setColor(self.current_draw_color)
        active_scene.pen = pen
        
        self.lbl_draw_page.setText(f"Page {self.draw_current_page + 1} / {len(self.draw_doc)}")

    def next_draw_page(self):
        if self.draw_doc and self.draw_current_page < len(self.draw_doc) - 1:
            self.draw_current_page += 1
            self.update_draw_page_view()

    def prev_draw_page(self):
        if self.draw_doc and self.draw_current_page > 0:
            self.draw_current_page -= 1
            self.update_draw_page_view()

    def save_canvas(self):
        out_path, _ = QFileDialog.getSaveFileName(self, "Save File", "", "PDF Files (*.pdf);;Images (*.png)")
        if not out_path: return
        
        if out_path.endswith('.pdf'):
            if self.draw_doc:
                out_doc = fitz.open(self.draw_pdf_path)
                for i in range(len(out_doc)):
                    if i in self.draw_scenes:
                        scene_dict = self.draw_scenes[i]
                        scene = scene_dict['scene']
                        bg_item = scene_dict['bg_item']
                        
                        scene.is_saving = True
                        scene.clearSelection()
                        bg_item.hide()
                        rect = scene.sceneRect()
                        image = QImage(int(rect.width()), int(rect.height()), QImage.Format.Format_ARGB32)
                        image.fill(Qt.GlobalColor.transparent)
                        
                        from PyQt6.QtGui import QPainter
                        painter = QPainter(image)
                        scene.render(painter)
                        painter.end()
                        bg_item.show()
                        scene.is_saving = False
                        
                        temp_path = f"temp_draw_{i}.png"
                        image.save(temp_path)
                        page = out_doc[i]
                        page.insert_image(page.rect, filename=temp_path)
                        os.remove(temp_path)
                        
                out_doc.save(out_path)
                out_doc.close()
            else:
                scene = self.draw_scenes[0]['scene']
                scene.is_saving = True
                scene.clearSelection()
                rect = scene.sceneRect()
                image = QImage(int(rect.width()), int(rect.height()), QImage.Format.Format_ARGB32)
                image.fill(Qt.GlobalColor.transparent)
                
                from PyQt6.QtGui import QPainter
                painter = QPainter(image)
                scene.render(painter)
                painter.end()
                scene.is_saving = False
                
                temp_path = "temp_canvas.png"
                image.save(temp_path)
                doc = fitz.open(); img = fitz.open(temp_path)
                pdfbytes = img.convert_to_pdf(); img.close()
                img_doc = fitz.open("pdf", pdfbytes)
                page = doc.new_page(width=image.width(), height=image.height())
                page.show_pdf_page(page.rect, img_doc, 0)
                doc.save(out_path); doc.close()
                os.remove(temp_path)
        else:
            scene = self.draw_scenes[self.draw_current_page]['scene']
            scene.is_saving = True
            scene.clearSelection()
            rect = scene.sceneRect()
            image = QImage(int(rect.width()), int(rect.height()), QImage.Format.Format_ARGB32)
            image.fill(Qt.GlobalColor.transparent)
            
            from PyQt6.QtGui import QPainter
            painter = QPainter(image)
            scene.render(painter)
            painter.end()
            scene.is_saving = False
            image.save(out_path)
            
        self.show_msg("Success", "File saved successfully!")

    def create_annotation_widget(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        controls = QHBoxLayout()
        btn_load_pdf = DropButton("📂 1. Open PDF (Drag & Drop)", self.load_pdf_for_numbering)
        btn_load_pdf.clicked.connect(lambda: self.load_pdf_for_numbering())
        
        self.num_start = QSpinBox()
        self.num_start.setValue(1)
        self.num_size = QSpinBox()
        self.num_size.setValue(12)
        self.num_format = QLineEdit("Page {num}")
        
        btn_color = QPushButton("🎨 Pick Color")
        self.num_color = (0, 0, 0)
        btn_color.clicked.connect(self.pick_num_color)

        btn_generate = QPushButton("⚙️ 2. Apply Text/Style")
        btn_generate.clicked.connect(self.generate_numbering_data)

        btn_save = QPushButton("💾 3. Save Final PDF")
        btn_save.setStyleSheet("background-color: #a6e3a1; color: #11111b;")
        btn_save.clicked.connect(self.save_final_numbering)

        controls.addWidget(btn_load_pdf)
        controls.addWidget(QLabel("Start:"))
        controls.addWidget(self.num_start)
        controls.addWidget(QLabel("Size:"))
        controls.addWidget(self.num_size)
        controls.addWidget(QLabel("Format:"))
        controls.addWidget(self.num_format)
        controls.addWidget(btn_color)
        controls.addWidget(btn_generate)
        controls.addWidget(btn_save)
        layout.addLayout(controls)

        nav_hl = QHBoxLayout()
        btn_prev = QPushButton("◀ Prev Page")
        btn_prev.clicked.connect(self.prev_num_page)
        
        self.lbl_num_page = QLabel("Page 0 / 0")
        self.lbl_num_page.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        btn_next = QPushButton("Next Page ▶")
        btn_next.clicked.connect(self.next_num_page)
        
        btn_sync = QPushButton("🔄 Sync Position to All Pages")
        btn_sync.clicked.connect(self.sync_numbering_positions)
        
        nav_hl.addWidget(btn_prev)
        nav_hl.addWidget(self.lbl_num_page)
        nav_hl.addWidget(btn_next)
        nav_hl.addStretch()
        nav_hl.addWidget(btn_sync)
        layout.addLayout(nav_hl)

        self.num_scene = QGraphicsScene()
        self.num_view = QGraphicsView(self.num_scene)
        self.num_view.setStyleSheet("background-color: #313244;")
        layout.addWidget(self.num_view)

        self.num_text_item = None
        self.num_doc = None
        self.loaded_pdf_path_for_num = None
        self.page_numbering_data = {}
        self.num_current_page = 0
        
        return tab

    def pick_num_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.num_color = (color.red()/255, color.green()/255, color.blue()/255)
            self.generate_numbering_data() 

    def load_pdf_for_numbering(self, path=None):
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, "Select PDF", "", "PDF Files (*.pdf)")
        if path:
            if self.num_doc: self.num_doc.close()
            self.loaded_pdf_path_for_num = path
            self.num_doc = fitz.open(path)
            self.num_current_page = 0
            self.generate_numbering_data(is_initial=True)

    def generate_numbering_data(self, is_initial=False):
        if not self.num_doc: return
        fmt = self.num_format.text()
        start = self.num_start.value()
        size = self.num_size.value()
        
        for i in range(len(self.num_doc)):
            page = self.num_doc[i]
            
            if is_initial or i not in self.page_numbering_data:
                w = page.rect.width
                h = page.rect.height
                x = w / 2 - 20
                y = h - 40
                self.page_numbering_data[i] = {'x': x, 'y': y}
                
            self.page_numbering_data[i].update({
                'text': fmt.replace("{num}", str(start + i)),
                'size': size,
                'color': self.num_color
            })
            
        self.show_numbering_page()

    def save_current_num_pos(self):
        if self.num_text_item and self.num_current_page in self.page_numbering_data:
            self.page_numbering_data[self.num_current_page]['x'] = self.num_text_item.x()
            self.page_numbering_data[self.num_current_page]['y'] = self.num_text_item.y()

    def show_numbering_page(self):
        if not self.num_doc: return
        self.num_scene.clear()
        
        page = self.num_doc[self.num_current_page]
        pix = page.get_pixmap(dpi=72)
        img = self.pixmap_to_qimage(pix)
        pixmap = QPixmap.fromImage(img)
        
        self.num_scene.addPixmap(pixmap)
        self.num_scene.setSceneRect(QRectF(pixmap.rect()))
        
        data = self.page_numbering_data[self.num_current_page]
        
        self.num_text_item = QGraphicsTextItem(data['text'])
        self.num_text_item.setDefaultTextColor(QColor(int(data['color'][0]*255), int(data['color'][1]*255), int(data['color'][2]*255)))
        self.num_text_item.setFont(QFont("Arial", data['size']))
        self.num_text_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.num_text_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.num_text_item.setPos(data['x'], data['y'])
        self.num_scene.addItem(self.num_text_item)
        
        self.lbl_num_page.setText(f"Page {self.num_current_page + 1} / {len(self.num_doc)}")

    def next_num_page(self):
        if self.num_doc and self.num_current_page < len(self.num_doc) - 1:
            self.save_current_num_pos()
            self.num_current_page += 1
            self.show_numbering_page()

    def prev_num_page(self):
        if self.num_doc and self.num_current_page > 0:
            self.save_current_num_pos()
            self.num_current_page -= 1
            self.show_numbering_page()

    def sync_numbering_positions(self):
        if not self.num_doc: return
        self.save_current_num_pos()
        
        ref_data = self.page_numbering_data[self.num_current_page]
        ref_page = self.num_doc[self.num_current_page]
        w0, h0 = ref_page.rect.width, ref_page.rect.height
        
        rel_x = ref_data['x'] / w0 if w0 > 0 else 0
        rel_y = ref_data['y'] / h0 if h0 > 0 else 0
        
        for i in range(len(self.num_doc)):
            if i == self.num_current_page: continue
            page = self.num_doc[i]
            self.page_numbering_data[i]['x'] = page.rect.width * rel_x
            self.page_numbering_data[i]['y'] = page.rect.height * rel_y
            
        self.show_msg("Synced", "Position synced to all pages based on the current page's layout.")

    def save_final_numbering(self):
        if not self.num_doc: return
        self.save_current_num_pos()
        in_path = self.loaded_pdf_path_for_num
        out_path = self.get_auto_output_path(in_path, "numbered", ".pdf")
        data_map = self.page_numbering_data.copy()
        def work(progress_cb):
            import fitz
            out_doc = fitz.open(in_path)
            total = len(out_doc)
            for i in range(total):
                page = out_doc[i]
                data = data_map[i]
                target_y = data['y'] + (data['size'] * 0.8)
                page.insert_text(fitz.Point(data['x'], target_y), data['text'], fontsize=data['size'], color=data['color'])
                progress_cb(int(((i + 1) / total) * 90))
            out_doc.save(out_path)
            out_doc.close()
            progress_cb(100)
        self.run_background_task("Applying Page Numbers...", work, lambda r: self.show_msg("Success", f"Numbered PDF saved to:\n{out_path}"))



    def pdf_to_word(self, path=None):
        pdf_path = path or QFileDialog.getOpenFileName(self, "Select PDF", "", "PDF Files (*.pdf)")[0]
        if not pdf_path: return
        out_path = self.get_auto_output_path(pdf_path, "converted", ".docx")
        def work(progress_cb):
            from pdf2docx import Converter
            progress_cb(10)
            cv = Converter(pdf_path)
            cv.convert(out_path, start=0, end=None)
            cv.close()
            progress_cb(100)
        self.run_background_task("Converting to Word (This takes time)...", work, lambda r: self.show_msg("Success", f"Word file saved to:\n{out_path}"))

    def pdf_to_images(self, path=None):
        pdf_path = path or QFileDialog.getOpenFileName(self, "Select PDF", "", "PDF Files (*.pdf)")[0]
        if not pdf_path: return
        dir_name = os.path.dirname(os.path.abspath(pdf_path))
        base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        out_dir = os.path.join(dir_name, f"{base_name}_images")
        os.makedirs(out_dir, exist_ok=True)
        def work(progress_cb):
            import fitz
            import os
            doc = fitz.open(pdf_path)
            total = len(doc)
            for i in range(total):
                page = doc[i]
                pix = page.get_pixmap(dpi=300)
                pix.save(os.path.join(out_dir, f"page_{i+1}.png"))
                pix = None
                progress_cb(int(((i + 1) / total) * 100))
            doc.close()
            return total
        self.run_background_task("Extracting Images...", work, lambda total: self.show_msg("Success", f"Extracted {total} images into:\n{out_dir}"))

    def pdf_to_pages(self, path=None):
        if not path or not isinstance(path, str):
            path, _ = QFileDialog.getOpenFileName(self, "Select PDF to Convert into Pages", "", "PDF Files (*.pdf)")
        if not path or not os.path.exists(path):
            return

        pdf_path = os.path.abspath(path)
        dir_name = os.path.dirname(pdf_path)
        base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        out_dir = os.path.join(dir_name, f"{base_name}_pages")
        os.makedirs(out_dir, exist_ok=True)

        def work(progress_cb):
            import fitz
            doc = fitz.open(pdf_path)
            total = len(doc)
            if total == 0:
                doc.close()
                return 0, out_dir
            pad_width = max(2, len(str(total)))
            for i in range(total):
                page_num_str = str(i + 1).zfill(pad_width)
                page_out_path = os.path.join(out_dir, f"{base_name}_page_{page_num_str}.pdf")
                single_doc = fitz.open()
                # 100% Lossless vector, font, image, and DPI preservation
                single_doc.insert_pdf(doc, from_page=i, to_page=i)
                single_doc.save(page_out_path, deflate=True)
                single_doc.close()
                progress_cb(int(((i + 1) / total) * 100))
            doc.close()
            return total, out_dir

        def on_success(result):
            total, folder = result
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Conversion Complete - V3")
            msg_box.setText(f"Successfully converted PDF into {total} separate PDF files!\n\nAll pages preserved at 100% original quality and fidelity.\n\nSaved to folder:\n{folder}")
            btn_open = msg_box.addButton("📂 Open Output Folder", QMessageBox.ButtonRole.ActionRole)
            msg_box.addButton("OK", QMessageBox.ButtonRole.AcceptRole)
            msg_box.setDefaultButton(btn_open)
            msg_box.exec()
            if msg_box.clickedButton() == btn_open:
                subprocess.Popen(f'explorer "{os.path.abspath(folder)}"')

        self.run_background_task("Converting PDF to Separate Pages...", work, on_success)

    def word_to_pages(self, path=None):
        if not path or not isinstance(path, str):
            path, _ = QFileDialog.getOpenFileName(self, "Select Word Document to Convert into Pages", "", "Word Documents (*.docx *.doc)")
        if not path or not os.path.exists(path):
            return

        doc_path = os.path.abspath(path)
        dir_name = os.path.dirname(doc_path)
        base_name = os.path.splitext(os.path.basename(doc_path))[0]
        out_dir = os.path.join(dir_name, f"{base_name}_pages")
        os.makedirs(out_dir, exist_ok=True)

        want_pdf = self.radio_w2p_pdf.isChecked() or self.radio_w2p_both.isChecked()
        want_docx = self.radio_w2p_docx.isChecked() or self.radio_w2p_both.isChecked()

        def work(progress_cb):
            import pythoncom
            import win32com.client
            import docx
            import copy
            import bisect
            import fitz

            progress_cb(10)
            pythoncom.CoInitialize()
            word = None
            doc = None
            total_pages = 0
            page_starts = []

            try:
                word = win32com.client.Dispatch("Word.Application")
                word.Visible = False
                word.DisplayAlerts = False
                progress_cb(20)

                doc = word.Documents.Open(doc_path, ReadOnly=True)
                total_pages = doc.ComputeStatistics(2)  # wdStatisticPages = 2
                progress_cb(30)

                # Collect dynamic page boundaries via \page bookmark
                word.Selection.HomeKey(Unit=6)  # wdStory
                for p in range(1, total_pages + 1):
                    word.Selection.GoTo(What=1, Which=1, Count=p)
                    bm = word.Selection.Bookmarks(r"\page")
                    page_starts.append(bm.Range.Start)
                progress_cb(40)

                pad = max(2, len(str(total_pages)))

                # --- 1) PDF Export (Native Word Vector Engine) ---
                if want_pdf:
                    temp_pdf = os.path.join(out_dir, f"_temp_{base_name}.pdf")
                    doc.ExportAsFixedFormat(
                        OutputFileName=os.path.abspath(temp_pdf),
                        ExportFormat=17  # wdExportFormatPDF
                    )
                    progress_cb(60)

                    pdf_doc = fitz.open(temp_pdf)
                    for i in range(len(pdf_doc)):
                        p_str = str(i + 1).zfill(pad)
                        single_pdf = os.path.join(out_dir, f"{base_name}_page_{p_str}.pdf")
                        s_doc = fitz.open()
                        s_doc.insert_pdf(pdf_doc, from_page=i, to_page=i)
                        s_doc.save(single_pdf, deflate=True)
                        s_doc.close()
                    pdf_doc.close()
                    if os.path.exists(temp_pdf):
                        try: os.remove(temp_pdf)
                        except Exception: pass
                    progress_cb(75)

                # --- 2) DOCX Slicing (Native OpenXML - 100% Arabic & Layout Fidelity) ---
                if want_docx and doc_path.lower().endswith('.docx'):
                    src_doc = docx.Document(doc_path)
                    body = src_doc._body._body
                    sectPr = body.find(docx.oxml.ns.qn('w:sectPr'))
                    elements = [e for e in list(body) if e != sectPr]

                    # Calculate element character offsets
                    elem_starts = []
                    cum = 0
                    for elem in elements:
                        elem_starts.append(cum)
                        texts = elem.xpath('.//w:t/text()')
                        t_len = sum(len(t) for t in texts) + 1
                        cum += t_len

                    # Map each element to its page
                    elem_pages = [bisect.bisect_right(page_starts, s) for s in elem_starts]
                    page_elem_map = {p: [] for p in range(1, total_pages + 1)}
                    for elem, p in zip(elements, elem_pages):
                        p_clamped = max(1, min(total_pages, p))
                        page_elem_map[p_clamped].append(elem)

                    for p_idx in range(1, total_pages + 1):
                        elems = page_elem_map.get(p_idx, [])
                        if not elems:
                            continue
                        page_doc = docx.Document(doc_path)
                        p_body = page_doc._body._body
                        p_sectPr = p_body.find(docx.oxml.ns.qn('w:sectPr'))
                        for child in list(p_body):
                            if child != p_sectPr:
                                p_body.remove(child)

                        for elem in elems:
                            cloned = copy.deepcopy(elem)
                            for br in cloned.xpath('.//w:br[@w:type="page"]'):
                                br.getparent().remove(br)
                            if p_sectPr is not None:
                                p_body.insert(p_body.index(p_sectPr), cloned)
                            else:
                                p_body.append(cloned)

                        p_str = str(p_idx).zfill(pad)
                        out_docx = os.path.join(out_dir, f"{base_name}_page_{p_str}.docx")
                        page_doc.save(out_docx)

                    progress_cb(95)

            except Exception as e:
                # Fallback if Word COM fails
                if want_docx and doc_path.lower().endswith('.docx') and total_pages == 0:
                    src_doc = docx.Document(doc_path)
                    body = src_doc._body._body
                    sectPr = body.find(docx.oxml.ns.qn('w:sectPr'))
                    pages_elements = []
                    current_elements = []
                    for element in list(body):
                        if element == sectPr: continue
                        xml = element.xml
                        has_break = ('w:type="page"' in xml) or ('w:lastRenderedPageBreak' in xml)
                        current_elements.append(element)
                        if has_break:
                            pages_elements.append(current_elements)
                            current_elements = []
                    if current_elements:
                        pages_elements.append(current_elements)
                    pad = max(2, len(str(len(pages_elements))))
                    for i, elems in enumerate(pages_elements):
                        page_doc = docx.Document(doc_path)
                        p_body = page_doc._body._body
                        p_sectPr = p_body.find(docx.oxml.ns.qn('w:sectPr'))
                        for child in list(p_body):
                            if child != p_sectPr: p_body.remove(child)
                        for elem in elems:
                            cloned = copy.deepcopy(elem)
                            for br in cloned.xpath('.//w:br[@w:type="page"]'):
                                br.getparent().remove(br)
                            if p_sectPr is not None:
                                p_body.insert(p_body.index(p_sectPr), cloned)
                            else:
                                p_body.append(cloned)
                        p_num_str = str(i + 1).zfill(pad)
                        page_doc.save(os.path.join(out_dir, f"{base_name}_page_{p_num_str}.docx"))
                    total_pages = len(pages_elements)
            finally:
                if doc:
                    try: doc.Close(SaveChanges=False)
                    except Exception: pass
                if word:
                    try: word.Quit()
                    except Exception: pass
                pythoncom.CoUninitialize()

            progress_cb(100)
            return total_pages, out_dir

        def on_success(result):
            total, folder = result
            fmt_desc = "PDF" if want_pdf and not want_docx else ("DOCX" if want_docx and not want_pdf else "PDF + DOCX")
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Word to Pages Complete")
            msg_box.setText(f"Successfully converted Word document into {total} separate {fmt_desc} files!\n\nAll formatting, Arabic fonts, tables, and layouts preserved with 100% original fidelity.\n\nSaved to folder:\n{folder}")
            btn_open = msg_box.addButton("📂 Open Output Folder", QMessageBox.ButtonRole.ActionRole)
            msg_box.addButton("OK", QMessageBox.ButtonRole.AcceptRole)
            msg_box.setDefaultButton(btn_open)
            msg_box.exec()
            if msg_box.clickedButton() == btn_open:
                subprocess.Popen(f'explorer "{os.path.abspath(folder)}"')

        self.run_background_task("Converting Word to Pages (High Fidelity)...", work, on_success)

    # ================= ROTATE PDF FEATURE =================
    def create_rotate_widget(self):
        tab = QWidget()
        vl = QVBoxLayout(tab)

        # Top Control Bar: Load, Info, Save
        control_hl = QHBoxLayout()
        btn_load = DropButton("📂 1. Open PDF to Rotate (Drag & Drop Supported)", self.load_pdf_for_rotate)
        btn_load.clicked.connect(lambda *a: self.load_pdf_for_rotate())

        self.lbl_rotate_info = QLabel("Open or drop a PDF to view and rotate pages.")
        self.lbl_rotate_info.setStyleSheet("color: #a6adc8; font-weight: 500;")

        btn_save = QPushButton("💾 2. Save Rotated PDF")
        btn_save.setStyleSheet("background-color: #89b4fa; color: #11111b; font-weight: bold; padding: 10px 18px;")
        btn_save.clicked.connect(self.save_rotated_pdf)

        control_hl.addWidget(btn_load)
        control_hl.addWidget(self.lbl_rotate_info, 1)
        control_hl.addWidget(btn_save)
        vl.addLayout(control_hl)

        # Main Split Content: Left = Live Visual Preview, Right = Controls
        content_hl = QHBoxLayout()

        # Left Preview Panel
        preview_box = QGroupBox("📄 Live Page Preview")
        preview_vl = QVBoxLayout(preview_box)

        self.scroll_rotate = QScrollArea()
        self.scroll_rotate.setWidgetResizable(True)
        self.scroll_rotate.setStyleSheet("background-color: #181825; border: 1px solid #313244; border-radius: 6px;")

        self.lbl_rotate_preview = QLabel("Drag & drop a PDF file here or click Open above to view and rotate.")
        self.lbl_rotate_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_rotate_preview.setStyleSheet("color: #6c7086; font-size: 14px; padding: 20px;")
        self.scroll_rotate.setWidget(self.lbl_rotate_preview)
        preview_vl.addWidget(self.scroll_rotate)

        # Navigation Bar under Preview
        nav_hl = QHBoxLayout()
        btn_prev = QPushButton("◀ Previous Page")
        btn_prev.clicked.connect(self.prev_rotate_page)

        self.lbl_rotate_page = QLabel("Page 0 / 0")
        self.lbl_rotate_page.setStyleSheet("font-weight: bold; color: #cdd6f4; font-size: 13px;")

        btn_next = QPushButton("Next Page ▶")
        btn_next.clicked.connect(self.next_rotate_page)

        self.lbl_rotate_angle = QLabel("Orientation: 0°")
        self.lbl_rotate_angle.setStyleSheet("background-color: #313244; color: #a6e3a1; font-weight: bold; padding: 4px 10px; border-radius: 4px;")

        nav_hl.addWidget(btn_prev)
        nav_hl.addStretch()
        nav_hl.addWidget(self.lbl_rotate_page)
        nav_hl.addStretch()
        nav_hl.addWidget(btn_next)
        nav_hl.addWidget(self.lbl_rotate_angle)
        preview_vl.addLayout(nav_hl)

        content_hl.addWidget(preview_box, 3)

        # Right Controls Panel
        ctrl_box = QGroupBox("⚙️ Rotation Options & Actions")
        ctrl_vl = QVBoxLayout(ctrl_box)

        # Scope Selection
        lbl_scope = QLabel("📌 Apply Rotation To:")
        lbl_scope.setStyleSheet("font-weight: bold; color: #89b4fa;")
        ctrl_vl.addWidget(lbl_scope)

        self.radio_rot_all = QRadioButton("All Pages (جميع صفحات الملف)")
        self.radio_rot_current = QRadioButton("Current Page Only (الصفحة الحالية فقط)")
        self.radio_rot_all.setChecked(True)
        ctrl_vl.addWidget(self.radio_rot_all)
        ctrl_vl.addWidget(self.radio_rot_current)

        ctrl_vl.addSpacing(15)

        # Rotation Buttons
        lbl_actions = QLabel("🔄 Choose Rotation Direction:")
        lbl_actions.setStyleSheet("font-weight: bold; color: #89b4fa;")
        ctrl_vl.addWidget(lbl_actions)

        btn_cw = QPushButton("⟳ Rotate 90° Right (Clockwise)")
        btn_cw.setStyleSheet("background-color: #a6e3a1; color: #11111b; font-weight: bold; font-size: 13px; padding: 12px;")
        btn_cw.clicked.connect(lambda: self.apply_rotation(90))

        btn_ccw = QPushButton("⟲ Rotate 90° Left (Counter-Clockwise)")
        btn_ccw.setStyleSheet("background-color: #74c7ec; color: #11111b; font-weight: bold; font-size: 13px; padding: 12px;")
        btn_ccw.clicked.connect(lambda: self.apply_rotation(-90))

        btn_180 = QPushButton("🔄 Flip 180° (Upside Down)")
        btn_180.setStyleSheet("background-color: #fab387; color: #11111b; font-weight: bold; font-size: 13px; padding: 12px;")
        btn_180.clicked.connect(lambda: self.apply_rotation(180))

        btn_reset = QPushButton("↺ Reset to Original Rotation")
        btn_reset.setStyleSheet("background-color: #45475a; color: #cdd6f4; font-weight: bold; font-size: 12px; padding: 8px;")
        btn_reset.clicked.connect(self.reset_rotation)

        ctrl_vl.addWidget(btn_cw)
        ctrl_vl.addWidget(btn_ccw)
        ctrl_vl.addWidget(btn_180)
        ctrl_vl.addWidget(btn_reset)

        ctrl_vl.addSpacing(15)

        lbl_hint = QLabel(
            "💡 Tip: Rotations are 100% lossless!\n"
            "Vector text, fonts, and images are preserved with zero re-compression."
        )
        lbl_hint.setStyleSheet("color: #6c7086; font-size: 11px; line-height: 1.3;")
        ctrl_vl.addWidget(lbl_hint)

        ctrl_vl.addStretch()
        content_hl.addWidget(ctrl_box, 2)

        vl.addLayout(content_hl)

        # Initialize rotation state variables
        self.rotate_pdf_path = None
        self.rotate_doc = None
        self.rotate_current_page = 0
        self.rotate_page_rotations = {}
        self.rotate_orig_rotations = {}

        return tab

    def load_pdf_for_rotate(self, path=None):
        if not path or not isinstance(path, str):
            path, _ = QFileDialog.getOpenFileName(self, "Select PDF to Rotate", "", "PDF Files (*.pdf)")
        if not path or not os.path.exists(path):
            return

        try:
            doc = fitz.open(path)
            if len(doc) == 0:
                self.show_msg("Error", "The selected PDF contains no pages.")
                doc.close()
                return

            if self.rotate_doc:
                try: self.rotate_doc.close()
                except: pass

            self.rotate_pdf_path = os.path.abspath(path)
            self.rotate_doc = doc
            self.rotate_current_page = 0
            self.rotate_page_rotations = {i: doc[i].rotation for i in range(len(doc))}
            self.rotate_orig_rotations = dict(self.rotate_page_rotations)

            fname = os.path.basename(self.rotate_pdf_path)
            self.lbl_rotate_info.setText(f"📄 Loaded: {fname} ({len(doc)} pages)")
            self.update_rotate_preview()
        except Exception as e:
            self.show_msg("Error", f"Failed to open PDF:\n{e}")

    def update_rotate_preview(self):
        if not self.rotate_doc or len(self.rotate_doc) == 0:
            self.lbl_rotate_preview.setText("No document loaded.")
            self.lbl_rotate_page.setText("Page 0 / 0")
            self.lbl_rotate_angle.setText("Orientation: 0°")
            return

        page_idx = self.rotate_current_page
        page = self.rotate_doc[page_idx]
        current_rot = self.rotate_page_rotations.get(page_idx, 0)
        page.set_rotation(current_rot)

        pix = page.get_pixmap(dpi=72)
        qimg = self.pixmap_to_qimage(pix)
        pix = None

        pm = QPixmap.fromImage(qimg)
        scaled_pm = pm.scaled(550, 550, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.lbl_rotate_preview.setPixmap(scaled_pm)

        self.lbl_rotate_page.setText(f"Page {page_idx + 1} / {len(self.rotate_doc)}")
        self.lbl_rotate_angle.setText(f"Orientation: {current_rot}°")

    def prev_rotate_page(self):
        if self.rotate_doc and self.rotate_current_page > 0:
            self.rotate_current_page -= 1
            self.update_rotate_preview()

    def next_rotate_page(self):
        if self.rotate_doc and self.rotate_current_page < len(self.rotate_doc) - 1:
            self.rotate_current_page += 1
            self.update_rotate_preview()

    def apply_rotation(self, delta_degrees):
        if not self.rotate_doc or len(self.rotate_doc) == 0:
            self.show_msg("Notice", "Please open a PDF file first.")
            return

        if self.radio_rot_all.isChecked():
            for i in range(len(self.rotate_doc)):
                curr = self.rotate_page_rotations.get(i, 0)
                self.rotate_page_rotations[i] = (curr + delta_degrees) % 360
        else:
            curr = self.rotate_page_rotations.get(self.rotate_current_page, 0)
            self.rotate_page_rotations[self.rotate_current_page] = (curr + delta_degrees) % 360

        self.update_rotate_preview()

    def reset_rotation(self):
        if not self.rotate_doc:
            return
        self.rotate_page_rotations = dict(self.rotate_orig_rotations)
        self.update_rotate_preview()

    def save_rotated_pdf(self):
        if not self.rotate_doc or not self.rotate_pdf_path:
            self.show_msg("Notice", "Please load a PDF to rotate first.")
            return

        in_path = self.rotate_pdf_path
        out_path = self.get_auto_output_path(in_path, "rotated", ".pdf")
        rotations_copy = dict(self.rotate_page_rotations)

        def work(progress_cb):
            import fitz
            progress_cb(10)
            doc = fitz.open(in_path)
            total = len(doc)
            for i in range(total):
                rot = rotations_copy.get(i, doc[i].rotation)
                doc[i].set_rotation(rot % 360)
                progress_cb(10 + int(((i + 1) / total) * 80))
            doc.save(out_path, deflate=True)
            doc.close()
            progress_cb(100)

        def on_success(r):
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("PDF Saved Successfully")
            msg_box.setText(f"Rotated PDF has been saved successfully with 100% original quality!\n\nSaved to:\n{out_path}")
            btn_open_file = msg_box.addButton("📄 Open File", QMessageBox.ButtonRole.ActionRole)
            btn_open_folder = msg_box.addButton("📂 Open Folder", QMessageBox.ButtonRole.ActionRole)
            msg_box.addButton("OK", QMessageBox.ButtonRole.AcceptRole)
            msg_box.setDefaultButton(btn_open_file)
            msg_box.exec()

            if msg_box.clickedButton() == btn_open_file:
                subprocess.Popen(f'explorer "{os.path.abspath(out_path)}"')
            elif msg_box.clickedButton() == btn_open_folder:
                subprocess.Popen(f'explorer "{os.path.dirname(os.path.abspath(out_path))}"')

        self.run_background_task("Saving Rotated PDF...", work, on_success)

    def word_to_pdf(self, path=None):
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, "Select Word Document", "", "Word Documents (*.docx *.doc)")
        if not path or not os.path.exists(path):
            return

        doc_path = os.path.abspath(path)
        out_path = self.get_auto_output_path(doc_path, "converted", ".pdf")

        def work(progress_cb):
            import win32com.client, pythoncom
            progress_cb(15)
            pythoncom.CoInitialize()
            word = None
            doc = None
            try:
                word = win32com.client.Dispatch("Word.Application")
                word.Visible = False
                word.DisplayAlerts = False
                progress_cb(35)

                doc = word.Documents.Open(doc_path, ReadOnly=True)
                progress_cb(65)

                # 17 = wdFormatPDF (Native Word PDF engine)
                doc.SaveAs(os.path.abspath(out_path), FileFormat=17)
                progress_cb(95)
            finally:
                if doc:
                    doc.Close(SaveChanges=False)
                if word:
                    word.Quit()
                pythoncom.CoUninitialize()
            progress_cb(100)

        self.run_background_task(
            "Converting Word to PDF (High Fidelity)...",
            work,
            lambda r: self.show_msg("Success", f"Word document converted to PDF with 100% fidelity!\n\nSaved to:\n{out_path}")
        )

    def create_compress_widget(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 1. File Selection Group
        grp_file = QGroupBox("📂 1. Select PDF File")
        hl_file = QVBoxLayout(grp_file)
        
        self.btn_load_comp = DropButton("📂 Open PDF to Compress (Drag & Drop Supported)", self.load_compress_file)
        self.lbl_compress_info = QLabel("No PDF selected. Drag & Drop or click the button above.")
        self.lbl_compress_info.setStyleSheet("color: #a6adc8; font-size: 13px; padding: 5px;")
        
        hl_file.addWidget(self.btn_load_comp)
        hl_file.addWidget(self.lbl_compress_info)
        layout.addWidget(grp_file)

        # 2. Compression Mode & Resolution Group
        grp_modes = QGroupBox("⚙️ 2. Compression Quality & DPI Slider (تحكم نسبة الضغط وجودة الصفحات)")
        vl_modes = QVBoxLayout(grp_modes)

        # Mode Selection: Smart Resample (DPI Slider) vs Pure Lossless Squeeze
        hl_type = QHBoxLayout()
        self.radio_comp_slider = QRadioButton("⚡ Smart Compression (Resample via DPI Slider — Ghostscript + cpdf)")
        self.radio_comp_lossless = QRadioButton("🔒 Squeeze / Lossless (cpdf Only — No image downsampling)")
        self.radio_comp_slider.setChecked(True)
        hl_type.addWidget(self.radio_comp_slider)
        hl_type.addWidget(self.radio_comp_lossless)
        vl_modes.addLayout(hl_type)

        vl_modes.addSpacing(6)

        # Container for Slider and Presets
        self.widget_slider_container = QWidget()
        vl_slider = QVBoxLayout(self.widget_slider_container)
        vl_slider.setContentsMargins(0, 0, 0, 0)

        # Dynamic label showing current DPI value and description
        self.lbl_slider_dpi_val = QLabel("🎯 Target Resolution: 100 DPI ⭐ (Default)  (Recommended — Best balance of small size and clear text)")
        self.lbl_slider_dpi_val.setStyleSheet("color: #a6e3a1; font-weight: bold; font-size: 13px; padding: 2px;")
        vl_slider.addWidget(self.lbl_slider_dpi_val)

        # Interactive Slider
        self.slider_dpi = QSlider(Qt.Orientation.Horizontal)
        self.slider_dpi.setRange(50, 300)
        self.slider_dpi.setValue(100)  # Default 100 DPI as requested
        self.slider_dpi.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.slider_dpi.setTickInterval(25)
        self.slider_dpi.setStyleSheet("""
            QSlider::groove:horizontal { height: 8px; background: #313244; border-radius: 4px; }
            QSlider::sub-page:horizontal { background: #89b4fa; border-radius: 4px; }
            QSlider::handle:horizontal { background: #cdd6f4; border: 2px solid #89b4fa; width: 18px; margin: -5px 0; border-radius: 9px; }
            QSlider::handle:horizontal:hover { background: #a6e3a1; border-color: #a6e3a1; }
        """)
        self.slider_dpi.valueChanged.connect(self.on_dpi_slider_changed)
        vl_slider.addWidget(self.slider_dpi)

        # Quick preset buttons row
        hl_presets = QHBoxLayout()
        lbl_quick = QLabel("⚡ Quick Presets:")
        lbl_quick.setStyleSheet("color: #89b4fa; font-weight: bold; font-size: 12px;")
        hl_presets.addWidget(lbl_quick)

        presets = [
            ("72 DPI (Max)", 72),
            ("90 DPI (High)", 90),
            ("🎯 100 DPI (Default)", 100),
            ("120 DPI (Sharp)", 120),
            ("150 DPI (Balanced)", 150),
            ("200 DPI (Crisp)", 200),
            ("250 DPI (Very Sharp)", 250),
            ("300 DPI (Print)", 300),
        ]
        for name, val in presets:
            btn_p = QPushButton(name)
            btn_p.setStyleSheet("padding: 4px 7px; font-size: 11px;")
            btn_p.clicked.connect(lambda checked, v=val: self.set_dpi_preset(v))
            hl_presets.addWidget(btn_p)

        vl_slider.addLayout(hl_presets)
        vl_modes.addWidget(self.widget_slider_container)

        self.radio_comp_slider.toggled.connect(lambda checked: self.widget_slider_container.setEnabled(checked))
        layout.addWidget(grp_modes)

        # 3. Extra Options Group
        grp_options = QGroupBox("🛠️ 3. Additional Options")
        vl_opt = QVBoxLayout(grp_options)
        self.chk_comp_grayscale = QCheckBox("Convert images to Grayscale (Black & White — saves extra size)")
        self.chk_comp_linearize = QCheckBox("Fast Web View (Linearize document for fast web streaming)")
        self.chk_comp_linearize.setChecked(True)
        vl_opt.addWidget(self.chk_comp_grayscale)
        vl_opt.addWidget(self.chk_comp_linearize)
        layout.addWidget(grp_options)

        # 4. Action Button & Results
        self.btn_run_compress = QPushButton("🗜️ Compress PDF Now")
        self.btn_run_compress.setStyleSheet("background-color: #a6e3a1; color: #11111b; font-size: 15px; padding: 12px; font-weight: bold;")
        self.btn_run_compress.clicked.connect(self.compress_pdf_advanced)
        layout.addWidget(self.btn_run_compress)

        self.lbl_compress_result = QLabel("")
        self.lbl_compress_result.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_compress_result.setStyleSheet("color: #89b4fa; font-size: 14px; font-weight: bold; padding: 10px;")
        layout.addWidget(self.lbl_compress_result)

        layout.addStretch()
        self.compress_pdf_path = None
        return tab

    def on_dpi_slider_changed(self, val):
        if val <= 72:
            desc = "Maximum Compression — Smallest file size for mobile/email"
            color = "#f38ba8"
        elif val <= 90:
            desc = "High Compression — Very compact file size with good readability"
            color = "#fab387"
        elif val == 100:
            desc = "Recommended Default — Best balance of small size and clear text"
            color = "#a6e3a1"
        elif val <= 120:
            desc = "Sharp & Efficient — Lightweight with enhanced text sharpness"
            color = "#89dceb"
        elif val <= 150:
            desc = "Balanced — Ideal for ebooks and sharp screen viewing"
            color = "#89b4fa"
        elif val <= 200:
            desc = "Crisp — Extra sharpness for detailed graphics"
            color = "#b4befe"
        else:
            desc = "High Quality / Print — Maximum fidelity with moderate compression"
            color = "#cba6f7"

        star = " ⭐ (Default)" if val == 100 else ""
        self.lbl_slider_dpi_val.setText(f"🎯 Target Resolution: {val} DPI{star}  ({desc})")
        self.lbl_slider_dpi_val.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 13px; padding: 2px;")

    def set_dpi_preset(self, val):
        self.radio_comp_slider.setChecked(True)
        self.slider_dpi.setValue(val)

    def load_compress_file(self, path=None):
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, "Select PDF to Compress", "", "PDF Files (*.pdf)")
        if not path or not os.path.exists(path):
            return
        self.compress_pdf_path = path
        size_bytes = os.path.getsize(path)
        if size_bytes > 1024 * 1024:
            size_str = f"{size_bytes / (1024 * 1024):.2f} MB"
        else:
            size_str = f"{size_bytes / 1024:.1f} KB"
        self.lbl_compress_info.setText(f"📄 Loaded: {os.path.basename(path)}  |  Original Size: {size_str}")
        self.lbl_compress_info.setStyleSheet("color: #a6e3a1; font-weight: bold; font-size: 13px; padding: 5px;")
        self.lbl_compress_result.setText("")

    def compress_pdf_advanced(self):
        if not self.compress_pdf_path or not os.path.exists(self.compress_pdf_path):
            self.show_msg("Warning", "Please select a PDF file first!")
            return

        in_path = self.compress_pdf_path
        out_path = self.get_auto_output_path(in_path, "compressed", ".pdf")

        bin_dir = self.get_bin_dir()
        gs_path = os.path.join(bin_dir, "gswin64c.exe")
        cpdf_path = os.path.join(bin_dir, "cpdf.exe")

        if not os.path.exists(gs_path) or not os.path.exists(cpdf_path):
            self.show_msg("Error", f"Compression tools (Ghostscript / cpdf) were not found in: {bin_dir}")
            return

        is_grayscale = self.chk_comp_grayscale.isChecked()
        is_linearize = self.chk_comp_linearize.isChecked()

        if self.radio_comp_lossless.isChecked():
            mode = "lossless"
            dpi = None
        else:
            mode = "resample"
            dpi = self.slider_dpi.value()

        def work(progress_cb):
            import subprocess, tempfile
            progress_cb(10)
            orig_size = os.path.getsize(in_path)

            if mode == "lossless":
                progress_cb(30)
                cmd = [cpdf_path, in_path, "-squeeze", "-create-objstm", "-o", out_path]
                subprocess.run(cmd, check=True, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
                progress_cb(100)
            else:
                progress_cb(25)
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
                    temp_mid_path = tf.name

                try:
                    if dpi <= 90:
                        base_setting = "/screen"
                    elif dpi <= 150:
                        base_setting = "/ebook"
                    else:
                        base_setting = "/printer"

                    gs_cmd = [
                        gs_path, '-sDEVICE=pdfwrite', '-dCompatibilityLevel=1.4',
                        '-dNOPAUSE', '-dBATCH', '-dQUIET', '-dSAFER',
                        f'-dPDFSETTINGS={base_setting}',
                        '-dPreserveMarkedContent=true',
                        '-dOptimize=true',
                        '-dDownsampleColorImages=true',
                        f'-dColorImageResolution={dpi}',
                        '-dDownsampleGrayImages=true',
                        f'-dGrayImageResolution={dpi}',
                        '-dDownsampleMonoImages=true',
                        f'-dMonoImageResolution={max(dpi * 2, 150)}',
                        '-dColorImageDownsampleThreshold=1.0',
                        '-dGrayImageDownsampleThreshold=1.0',
                        '-dMonoImageDownsampleThreshold=1.0',
                        '-dDownsampleType=/Bicubic',
                        '-dSubsetFonts=true', '-dCompressFonts=true',
                        '-dEmbedAllFonts=true'
                    ]
                    if is_linearize:
                        gs_cmd.append('-dFastWebView=true')
                    if is_grayscale:
                        gs_cmd.append('-sColorConversionStrategy=Gray')
                    else:
                        gs_cmd.append('-sColorConversionStrategy=LeaveColorUnchanged')

                    gs_cmd.extend([f'-sOutputFile={temp_mid_path}', in_path])
                    subprocess.run(gs_cmd, check=True, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
                    progress_cb(70)

                    cpdf_cmd = [cpdf_path, temp_mid_path, "-squeeze", "-create-objstm", "-o", out_path]
                    subprocess.run(cpdf_cmd, check=True, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
                    progress_cb(95)
                finally:
                    if os.path.exists(temp_mid_path):
                        os.remove(temp_mid_path)
                progress_cb(100)

            new_size = os.path.getsize(out_path)
            return orig_size, new_size

        def on_success(sizes):
            orig_s, new_s = sizes
            orig_str = f"{orig_s / (1024*1024):.2f} MB" if orig_s > 1024*1024 else f"{orig_s / 1024:.1f} KB"
            new_str = f"{new_s / (1024*1024):.2f} MB" if new_s > 1024*1024 else f"{new_s / 1024:.1f} KB"
            if orig_s > 0:
                saved_pct = ((orig_s - new_s) / orig_s) * 100
            else:
                saved_pct = 0

            dpi_str = f"Target Resolution: {dpi} DPI" if dpi else "Mode: Lossless Stream Squeeze"
            msg = f"Original: {orig_str}  ➔  Compressed: {new_str} (Saved: {saved_pct:.1f}%)\n{dpi_str}"
            self.lbl_compress_result.setText(f"🎉 {msg}\nSaved to: {os.path.basename(out_path)}")
            self.show_msg("Success", f"PDF compressed successfully!\n\n{msg}\n\nSaved to:\n{out_path}")

        task_title = f"Compressing PDF ({dpi} DPI)..." if dpi else "Compressing PDF (Lossless)..."
        self.run_background_task(task_title, work, on_success)


if __name__ == "__main__":
    if sys.platform == "win32":
        import ctypes
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("mrt.pdfmasterpro.app.2026")
        except:
            pass
    app = QApplication(sys.argv)
    
    # Set application icon globally
    icon_path = os.path.join(getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__))), "engine pdf.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
        
    window = ModernUI()
    window.show()
    sys.exit(app.exec())
