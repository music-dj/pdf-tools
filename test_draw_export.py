"""Run with Python to exercise the drawing tools and saved PDF output."""
import os
from pathlib import Path
import runpy
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
app_module = runpy.run_path(str(Path(__file__).with_name("PDF editor tool.py")))

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor, QBrush, QPainterPath, QPen
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QFileDialog


def main():
    app = QApplication([])
    window = app_module["ModernUI"]()
    window.show()
    app.processEvents()
    assert "pymupdf" not in sys.modules
    assert "pdf2docx" not in sys.modules
    assert [window.tabs.widget(i).layout() is not None for i in range(4)] == [
        True, False, False, False
    ]
    for index in (1, 3, 2):
        window.tabs.setCurrentIndex(index)
        app.processEvents()
        assert window.tabs.widget(index).layout() is not None

    import pymupdf

    messages = []
    window.show_msg = lambda *args: messages.append(args)
    window.save_canvas()
    assert messages[-1][0] == "No File Open"

    with TemporaryDirectory(ignore_cleanup_errors=True) as temp:
        source = Path(temp) / "source.pdf"
        output = Path(temp) / "saved.PDF"
        with pymupdf.open() as document:
            for rotation in (0, 90, 180, 270):
                page = document.new_page(width=220, height=140)
                page.set_rotation(rotation)
                page.insert_text(pymupdf.Point(95, 110) * page.derotation_matrix, "Original", rotate=rotation)
                mark = pymupdf.Rect(22, 24, 50, 46) * page.derotation_matrix
                page.draw_rect(mark, color=None, fill=(0, 0, 0))
            document.save(source)

        window.load_canvas_file(str(source))
        for index in range(4):
            window.draw_current_page = index
            window.update_draw_page_view()
            scene = window.draw_view.scene()
            view = window.draw_view
            for button in (window.btn_mode_rect, window.btn_mode_srect,
                           window.btn_mode_whiteout, window.btn_mode_draw):
                button.click()
                start = view.mapFromScene(QPointF(40, 40))
                end = view.mapFromScene(QPointF(110, 105))
                QTest.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=start)
                QTest.mouseMove(view.viewport(), end)
                QTest.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=end)
            assert len(scene.get_user_items()) == 4
            for item in scene.get_user_items():
                scene.removeItem(item)

            no_pen = QPen(Qt.PenStyle.NoPen)
            scene.addRect(33, 35, 90, 80, no_pen, QBrush(QColor("white")))
            path = QPainterPath(QPointF(125, 35))
            path.lineTo(165, 75)
            scene.addPath(path, QPen(QColor("white"), 12))
            scene.addRect(20, 150, 50, 40, no_pen, QBrush(QColor("red")))
            scene.brush_preview_item.setRect(45, 40, 25, 25)
            scene.brush_preview_item.show()

        with patch.object(QFileDialog, "getSaveFileName", return_value=(str(output), "PDF Files (*.pdf)")):
            window.save_canvas()
        assert messages[-1][0] == "Success", messages[-1]
        with pymupdf.open(output) as document:
            for index, page in enumerate(document):
                assert page.rotation == index * 90
                assert "Original" in page.get_text()
                assert not page.get_images()
                for dpi in (72, 150, 300):
                    pix = page.get_pixmap(dpi=dpi)
                    scale = dpi / 150
                    assert pix.pixel(round(42 * scale), round(168 * scale)) == (255, 0, 0), index
                    # White geometry and its edges must match the white page exactly.
                    for y in range(round(27 * scale), round(120 * scale)):
                        for x in range(round(24 * scale), round(173 * scale)):
                            assert pix.pixel(x, y) == (255, 255, 255), (index, dpi, x, y)

        window.draw_doc.close()

    print("PASS: lazy tabs, drawing buttons, and saved PDF edges at three resolutions")


if __name__ == "__main__":
    main()
