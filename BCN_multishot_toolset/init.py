"""BCN multishot toolset package initialization.

This package provides a Screens Manager panel and utilities for working with
Nuke 16 Graph Scope Variables (GSV), VariableGroups, and related multishot
workflows.

The `menu.py` module registers the dockable panel in Nuke's Pane menu.
"""

from typing import Optional

__all__ = [
    "__version__",
]

__version__: str = "0.1.0"

# Attempt to import menu to ensure the panel is registered when the package is
# imported by Nuke. Safe to ignore errors if imported outside Nuke.
def _auto_register_panel() -> Optional[Exception]:
    """Try to import the menu module to register the panel.

    Returns the exception if registration fails, otherwise None. This is
    intentionally non-fatal outside Nuke.
    """

    try:
        from . import menu as _menu  # noqa: F401
        return None
    except Exception as exc:  # pragma: no cover - safe fallback
        return exc

_auto_register_panel()


