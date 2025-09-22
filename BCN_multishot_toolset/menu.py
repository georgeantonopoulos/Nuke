"""BCN Multishot menu bootstrap.

Minimal, Deadline-style: add plugin paths, then in GUI add a Pane command
and a callable that docks the panel.
"""

from typing import Optional

import nuke  # type: ignore
import nukescripts  # type: ignore
from nukescripts import panels  # type: ignore
import importlib
import sys


nuke.pluginAddPath('./nuke_tools')

# Tools on NUKE_PATH
from screens_manager import ScreensManagerPanel  # type: ignore
from render_hooks import encapsulate_write_with_variable_group  # type: ignore


def add_screens_manager_panel() -> Optional[object]:
    """Create and dock the Screens Manager panel next to Properties."""

    try:
        pane = nuke.getPaneFor('Properties.1')
        return panels.registerWidgetAsPanel('ScreensManagerPanel', 'Screens Manager', 'uk.co.bcn.multishot.screens_manager', True).addToPane(pane) if pane else panels.registerWidgetAsPanel('ScreensManagerPanel', 'Screens Manager', 'uk.co.bcn.multishot.screens_manager', True)
    except Exception:
        return None


def reload_bcn_multishot() -> None:
    """Reload BCN Multishot toolset modules and refresh bound callables.

    This reloads the key modules (screens_manager, overrides, render_hooks),
    then rebinds exported callables used by menu items so newly edited code
    takes effect without restarting Nuke.
    """

    modules_to_reload = [
        'screens_manager',
        'overrides',
        'render_hooks',
    ]

    reloaded = []
    for module_name in modules_to_reload:
        try:
            module = sys.modules.get(module_name)
            if module is None:
                module = importlib.import_module(module_name)
            importlib.reload(module)
            reloaded.append(module_name)
        except Exception:
            # Best-effort reload; skip failures silently to avoid interrupting UX
            pass

    # Rebind globals used by menu wiring so commands use the latest code
    try:
        if 'screens_manager' in sys.modules:
            globals()['ScreensManagerPanel'] = getattr(sys.modules['screens_manager'], 'ScreensManagerPanel', ScreensManagerPanel)
        if 'render_hooks' in sys.modules:
            globals()['encapsulate_write_with_variable_group'] = getattr(sys.modules['render_hooks'], 'encapsulate_write_with_variable_group', encapsulate_write_with_variable_group)
    except Exception:
        pass

    try:
        nuke.tprint('BCN Multishot reloaded modules: ' + ', '.join(reloaded))
        if nuke.env.get('gui'):
            nuke.message('BCN Multishot reloaded: ' + (', '.join(reloaded) or 'no modules reloaded'))
    except Exception:
        pass


# GUI-only wiring
try:
    if nuke.env['gui']:
        # Pane menu entry
        nuke.menu('Pane').addCommand('Screens Manager', add_screens_manager_panel)
        # Enable layout save/restore
        nukescripts.registerPanel('uk.co.bcn.multishot.screens_manager', add_screens_manager_panel)
        # Optional: Nuke menu shortcut
        nuke.menu('Nuke').addCommand(
            'BCN Multishot/Screens Manager',
            add_screens_manager_panel,
        )
        # Write helpers
        nuke.menu('Nuke').addCommand(
            'BCN Multishot/Wrap Node in Variable Group',
            encapsulate_write_with_variable_group,
        )
        # Reload plugin for rapid iteration
        nuke.menu('Nuke').addCommand(
            'BCN Multishot/Reload Plugin',
            reload_bcn_multishot,
        )
except Exception:
    pass
