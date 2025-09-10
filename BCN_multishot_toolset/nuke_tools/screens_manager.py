"""Screens Manager panel for Nuke 16 multishot workflows.

Provides a minimal dockable Qt panel to:
- maintain `__default__.screen` list options
- create per-screen VariableGroups
- optionally create a `VariableSwitch` preview node

This keeps to expressions/VariableSwitch/Link nodes and avoids generic
callbacks; when a callback is required, prefer `nuke.callbacks.onGsvSetChanged`.
"""

from typing import List, Optional, Sequence

try:
    import nuke  # type: ignore
    from PySide2 import QtCore, QtWidgets  # type: ignore
except Exception:  # pragma: no cover
    nuke = None  # type: ignore
    QtCore = None  # type: ignore
    QtWidgets = None  # type: ignore

from . import gsv_utils


class ScreensManagerPanel(QtWidgets.QWidget):  # type: ignore[misc]
    """Simple UI for managing screens.

    The UI is intentionally minimal:
      - A line edit to enter comma-separated screen names
      - A default screen combobox
      - Buttons to apply/update, build VariableGroups, and create VariableSwitch
    """

    def __init__(self, parent=None) -> None:  # noqa: D401
        super().__init__(parent)
        self.setWindowTitle("Screens Manager")
        self._build_ui()
        self._load_from_gsv()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)

        # Screens input
        self.screens_edit = QtWidgets.QLineEdit(self)
        self.screens_edit.setPlaceholderText("Comma-separated screen names, e.g. Moxy,Godzilla,NYD400")

        # Default selector
        default_row = QtWidgets.QHBoxLayout()
        default_label = QtWidgets.QLabel("Default screen:", self)
        self.default_combo = QtWidgets.QComboBox(self)
        default_row.addWidget(default_label)
        default_row.addWidget(self.default_combo, 1)

        # Buttons
        btn_row = QtWidgets.QHBoxLayout()
        self.apply_btn = QtWidgets.QPushButton("Apply to GSV", self)
        self.groups_btn = QtWidgets.QPushButton("Ensure VariableGroups", self)
        self.switch_btn = QtWidgets.QPushButton("Create VariableSwitch", self)
        btn_row.addWidget(self.apply_btn)
        btn_row.addWidget(self.groups_btn)
        btn_row.addWidget(self.switch_btn)

        layout.addWidget(self.screens_edit)
        layout.addLayout(default_row)
        layout.addLayout(btn_row)
        layout.addStretch(1)

        # Wire signals
        self.apply_btn.clicked.connect(self._on_apply)
        self.groups_btn.clicked.connect(self._on_groups)
        self.switch_btn.clicked.connect(self._on_switch)

    def _load_from_gsv(self) -> None:
        options = gsv_utils.get_list_options("__default__.screen")
        self._set_combo_items(self.default_combo, options)
        if options:
            self.screens_edit.setText(
                ",".join(options)
            )

    def _set_combo_items(self, combo: QtWidgets.QComboBox, items: Sequence[str]) -> None:
        combo.clear()
        for item in items:
            combo.addItem(item)

    def _parse_screens(self) -> List[str]:
        text = self.screens_edit.text().strip()
        if not text:
            return []
        names = [n.strip() for n in text.split(",")]
        # de-duplicate while preserving order
        seen = set()
        unique: List[str] = []
        for n in names:
            if n and n not in seen:
                unique.append(n)
                seen.add(n)
        return unique

    # Actions
    def _on_apply(self) -> None:
        screens = self._parse_screens()
        if not screens:
            return
        default = self.default_combo.currentText() or screens[0]
        gsv_utils.ensure_screen_list(screens, default)
        self._load_from_gsv()

    def _on_groups(self) -> None:
        for name in self._parse_screens():
            gsv_utils.create_variable_group(f"screen_{name}")

    def _on_switch(self) -> None:
        if nuke is None:
            return
        try:
            node = nuke.createNode("VariableSwitch")
            node.setName("ScreenSwitch")
            # The VariableSwitch configuration is usually done via its patterns.
            # We keep this minimal and let users wire inputs and patterns.
        except Exception:
            pass


__all__ = ["ScreensManagerPanel"]


