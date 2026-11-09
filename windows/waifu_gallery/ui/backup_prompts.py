from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .dialog_chrome import DialogTitleBar, FramelessResizableDialog


class BackupPassphraseDialog(FramelessResizableDialog):
    def __init__(
        self,
        *,
        title: str,
        description: str,
        confirm_passphrase: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.confirm_passphrase = confirm_passphrase
        self.passphrase = ""
        self.setObjectName("backupPromptDialog")
        self.setWindowTitle(title)
        self.setFixedWidth(420)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        surface = QWidget(self)
        surface.setObjectName("backupPromptSurface")
        layout = QVBoxLayout(surface)
        layout.setContentsMargins(14, 4, 14, 14)
        layout.setSpacing(10)
        layout.addWidget(DialogTitleBar(self, title))

        instructions = QLabel(description)
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        self.passphrase_input = QLineEdit()
        self.passphrase_input.setObjectName("backupPassphrase")
        self.passphrase_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.passphrase_input.setPlaceholderText(
            "Create passphrase" if confirm_passphrase else "Passphrase"
        )
        layout.addWidget(self.passphrase_input)
        self.confirm_input = None
        if confirm_passphrase:
            self.confirm_input = QLineEdit()
            self.confirm_input.setObjectName("backupPassphraseConfirm")
            self.confirm_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.confirm_input.setPlaceholderText("Confirm passphrase")
            layout.addWidget(self.confirm_input)

        self.error_label = QLabel()
        self.error_label.setObjectName("backupPromptError")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        layout.addWidget(self.error_label)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        submit = QPushButton("Create backup" if confirm_passphrase else "Unlock backup")
        submit.setDefault(True)
        submit.clicked.connect(self._submit)
        buttons.addWidget(cancel)
        buttons.addWidget(submit)
        layout.addLayout(buttons)
        outer.addWidget(surface)
        self.passphrase_input.returnPressed.connect(self._submit)
        if self.confirm_input is not None:
            self.confirm_input.returnPressed.connect(self._submit)

    def _submit(self) -> None:
        value = self.passphrase_input.text()
        if self.confirm_passphrase:
            if len(value) < 8:
                self._show_error("Use a passphrase with at least 8 characters.")
                return
            if self.confirm_input is None or value != self.confirm_input.text():
                self._show_error("Passphrases do not match.")
                return
        elif not value:
            self._show_error("Enter the backup passphrase.")
            return
        self.passphrase = value
        self.accept()

    def _show_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.show()


class BackupMessageDialog(FramelessResizableDialog):
    def __init__(
        self,
        title: str,
        message: str,
        buttons: tuple[str, ...],
        *,
        default_button: str | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.selected_action: str | None = None
        self.setObjectName("backupPromptDialog")
        self.setWindowTitle(title)
        self.setFixedWidth(440)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        surface = QWidget(self)
        surface.setObjectName("backupPromptSurface")
        layout = QVBoxLayout(surface)
        layout.setContentsMargins(14, 4, 14, 14)
        layout.setSpacing(10)
        layout.addWidget(DialogTitleBar(self, title))
        description = QLabel(message)
        description.setWordWrap(True)
        layout.addWidget(description)
        row = QHBoxLayout()
        row.addStretch(1)
        for text in buttons:
            button = QPushButton(text)
            button.setDefault(text == default_button)
            if text == "Replace":
                button.setObjectName("backupDestructiveButton")
            button.clicked.connect(lambda _checked=False, action=text: self._choose(action))
            row.addWidget(button)
        layout.addLayout(row)
        outer.addWidget(surface)

    @classmethod
    def ask(
        cls,
        parent,
        title: str,
        message: str,
        buttons: tuple[str, ...],
        *,
        default_button: str | None = None,
    ) -> str | None:
        dialog = cls(
            title,
            message,
            buttons,
            default_button=default_button,
            parent=parent,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.selected_action
        return None

    def _choose(self, action: str) -> None:
        self.selected_action = action
        self.accept()
