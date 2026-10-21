"""Temporary OCR review; recognition alone never modifies clipboard or artwork."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QApplication, QDialog, QHBoxLayout, QLabel,
                               QPushButton, QTextEdit, QVBoxLayout)

from .document import Text
from . import rendering


class OcrPanel(QDialog):
    def __init__(self, canvas, image):
        super().__init__(canvas.window(), Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.canvas, self.image, self.service = canvas, image, canvas.ocr_service
        self.identifier = None
        self.valid = True
        self.ready = False
        self.setWindowTitle('Extract Text · English · offline')
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.resize(440, 300)
        layout = QVBoxLayout(self)
        self.status = QLabel('Reading image… You can cancel at any time.', self)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.review = QTextEdit(self)
        self.review.setAcceptRichText(False)
        self.review.setPlaceholderText('Recognized text will appear here for review.')
        self.review.setEnabled(False)
        layout.addWidget(self.review)
        buttons = QHBoxLayout()
        self.copy_button = QPushButton('Copy', self)
        self.insert_button = QPushButton('Insert as Text', self)
        cancel = QPushButton('Cancel', self)
        for button in (self.copy_button, self.insert_button, cancel):
            buttons.addWidget(button)
        self.copy_button.setEnabled(False)
        self.insert_button.setEnabled(False)
        self.copy_button.clicked.connect(self.copy_text)
        self.insert_button.clicked.connect(self.insert_text)
        cancel.clicked.connect(self.close)
        self.review.textChanged.connect(self.update_actions)
        layout.addLayout(buttons)
        self.service.delivered.connect(self.receive)

    def start(self):
        self.identifier = self.service.submit(self.image)
        self.show()
        board = self.canvas.window()
        centre = board.mapToGlobal(board.rect().center())
        self.move(centre.x()-self.width()//2, centre.y()-self.height()//2)

    def source_valid(self):
        return (self.valid and not self.canvas.suspended and self.canvas.window().isVisible()
                and not self.canvas.window()._closing
                and self.canvas.document.get(self.image.id) is self.image)

    def receive(self, result):
        if result.identifier != self.identifier:
            return
        if not self.source_valid():
            self.close()
            return
        self.ready = True
        self.status.setText(result.error or ('Review the text before copying or inserting. OCR can make mistakes.'
                                            if result.text else 'No text found. Try a clearer English image.'))
        self.review.setPlainText(result.text)
        self.review.setEnabled(not result.error)
        self.update_actions()

    def update_actions(self):
        enabled = self.ready and self.review.isEnabled() and bool(self.review.toPlainText().strip())
        self.copy_button.setEnabled(enabled)
        self.insert_button.setEnabled(enabled)

    def copy_text(self):
        if self.source_valid() and self.copy_button.isEnabled():
            QApplication.clipboard().setText(self.review.toPlainText())
            self.status.setText('Copied. You can still correct or insert this text.')

    def insert_text(self):
        if not self.source_valid() or not self.insert_button.isEnabled():
            self.close()
            return
        canvas = self.canvas
        bounds = rendering.bounds(self.image)
        width = max(80, min(360, canvas.width()-40))
        x = max(12, min(bounds.left()+16, canvas.width()-width-12))
        y = max(12, min(bounds.top()+16, canvas.height()-50))
        obj = Text((x, y), self.review.toPlainText(), layout_width=width, color=canvas.active_color)
        # No creation viewport clip: all recognized lines remain editable.
        canvas.commit_edit((*canvas.document.objects, obj), 'Insert OCR text', {obj.id})
        canvas.tool = 'Text'
        canvas.update_cursor()
        self.close()

    def closeEvent(self, event):
        self.valid = False
        if self.identifier is not None:
            self.service.cancel(self.identifier)
        if self.canvas.ocr_panel is self:
            self.canvas.ocr_panel = None
        super().closeEvent(event)
