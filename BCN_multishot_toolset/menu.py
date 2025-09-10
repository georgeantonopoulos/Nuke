"""Register BCN multishot Screens Manager panel in Nuke.

This module wires up a dockable Qt panel using
`nukescripts.panels.registerWidgetAsPanel`.
"""

from typing import Optional

import nuke  # type: ignore
import nukescripts  # type: ignore


def _panel_widget_class_name() -> str:
    """Return the fully qualified widget class name string for registration."""

    return "BCN_multishot_toolset.nuke_tools.screens_manager.ScreensManagerPanel"


def register_screens_manager_panel() -> Optional[object]:
    """Register the Screens Manager as a dockable panel.

    Returns the PythonPanel object in GUI mode; otherwise None.
    """

    try:
        panel = nukescripts.panels.registerWidgetAsPanel(
            _panel_widget_class_name(),
            "Screens Manager",
            "uk.co.bcn.multishot.screens_manager",
            False,
        )
        return panel
    except Exception:
        return None


def add_menu_entries() -> None:
    """Add an entry under the Nuke menu to open the panel."""

    try:
        menubar = nuke.menu("Nuke")
        tools = menubar.addMenu("BCN Multishot", index=450)
        tools.addCommand(
            "Open Screens Manager",
            "import nukescripts; pn = nukescripts.panels.registerWidgetAsPanel('BCN_multishot_toolset.nuke_tools.screens_manager.ScreensManagerPanel','Screens Manager','uk.co.bcn.multishot.screens_manager', True); pn.addToPane(nuke.getPaneFor('Properties.1'))",
        )
    except Exception:
        pass


# Register so it appears under the Pane menu; do not auto-create
register_screens_manager_panel()
add_menu_entries()


