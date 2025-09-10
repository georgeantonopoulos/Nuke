"""Register BCN multishot Screens Manager panel in Nuke.

This module wires up a dockable Qt panel using `nukescripts.panels.registerWidgetAsPanel`.
It assumes Nuke 16 with Qt available in the environment.
"""

from typing import Optional

try:
    import nuke  # type: ignore
    import nukescripts  # type: ignore
    from PySide2 import QtWidgets  # type: ignore
except Exception:  # pragma: no cover - allows import outside Nuke
    nuke = None  # type: ignore
    nukescripts = None  # type: ignore
    QtWidgets = None  # type: ignore


def _panel_widget_class_name() -> str:
    """Return the fully qualified widget class name string for registration."""

    return "BCN_multishot_toolset.nuke_tools.screens_manager.ScreensManagerPanel"


def register_screens_manager_panel() -> Optional[object]:
    """Register the Screens Manager as a dockable panel.

    Returns the PythonPanel object when running inside Nuke; otherwise None.
    """

    if nuke is None or nukescripts is None:
        return None

    panel = nukescripts.panels.registerWidgetAsPanel(
        _panel_widget_class_name(),
        "Screens Manager",
        "uk.co.bcn.multishot.screens_manager",
        True,
    )
    return panel


def add_to_pane() -> None:
    """Add the panel to Nuke's Properties pane if available."""

    if nuke is None:
        return
    pane = nuke.getPaneFor("Properties.1")
    reg = register_screens_manager_panel()
    if hasattr(reg, "addToPane"):
        reg.addToPane(pane)


# Auto-register when menu.py is imported by Nuke
try:  # pragma: no cover
    register_screens_manager_panel()
except Exception:
    pass


