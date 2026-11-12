from collections.abc import Callable

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..pin_security import valid_pin
from .dialog_chrome import DialogTitleBar, FramelessResizableDialog


class PinPromptDialog(FramelessResizableDialog):
    def __init__(
        self,
        *,
        title: str,
        description: str,
        verify_current: Callable[[str], tuple[bool, int]] | None = None,
        require_new: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.current_pin = ""
        self.new_pin = ""
        self._verify_current = verify_current
        self._require_new = require_new
        self.setObjectName("pinPromptDialog")
        self.setWindowTitle(title)
        self.setFixedWidth(420)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        surface = QWidget(self)
        surface.setObjectName("pinPromptSurface")
        layout = QVBoxLayout(surface)
        layout.setContentsMargins(14, 4, 14, 14)
        layout.setSpacing(10)
        layout.addWidget(DialogTitleBar(self, title))

        instructions = QLabel(description)
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        self.current_input = None
        if verify_current is not None:
            self.current_input = self._pin_input("pinPromptCurrent", "Current PIN")
            layout.addWidget(self.current_input)

        self.new_input = None
        self.confirm_input = None
        if require_new:
            self.new_input = self._pin_input("pinPromptNew", "New PIN (4-12 digits)")
            self.confirm_input = self._pin_input("pinPromptConfirm", "Confirm new PIN")
            layout.addWidget(self.new_input)
            layout.addWidget(self.confirm_input)

        self.error_label = QLabel()
        self.error_label.setObjectName("pinPromptError")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        layout.addWidget(self.error_label)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        submit = QPushButton("Save PIN" if require_new else "Continue")
        submit.setDefault(True)
        submit.clicked.connect(self._submit)
        buttons.addWidget(cancel)
        buttons.addWidget(submit)
        layout.addLayout(buttons)
        outer.addWidget(surface)

        for field in (self.current_input, self.new_input, self.confirm_input):
            if field is not None:
                field.returnPressed.connect(self._submit)

    @staticmethod
    def _pin_input(object_name: str, placeholder: str) -> QLineEdit:
        field = QLineEdit()
        field.setObjectName(object_name)
        field.setEchoMode(QLineEdit.EchoMode.Password)
        field.setMaxLength(12)
        field.setMinimumHeight(38)
        field.setPlaceholderText(placeholder)
        return field

    def _submit(self) -> None:
        current_pin = self.current_input.text() if self.current_input is not None else ""
        if self.current_input is not None and not current_pin:
            self._show_error("Enter your current PIN.")
            self.current_input.setFocus()
            return

        new_pin = self.new_input.text() if self.new_input is not None else ""
        if self._require_new:
            assert self.new_input is not None and self.confirm_input is not None
            if not valid_pin(new_pin):
                self._show_error("PIN must contain 4 to 12 digits.")
                self.new_input.setFocus()
                return
            if new_pin != self.confirm_input.text():
                self._show_error("PIN entries do not match.")
                self.confirm_input.selectAll()
                self.confirm_input.setFocus()
                return

        if self._verify_current is not None:
            assert self.current_input is not None
            verified, wait_seconds = self._verify_current(current_pin)
            if not verified:
                message = (
                    f"Incorrect PIN. Try again in {wait_seconds} seconds."
                    if wait_seconds else "Incorrect PIN."
                )
                self._show_error(message)
                self.current_input.selectAll()
                self.current_input.setFocus()
                return

        self.current_pin = current_pin
        self.new_pin = new_pin
        self.accept()

    def _show_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.show()