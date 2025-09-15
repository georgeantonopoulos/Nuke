"""Write node helpers for the Screens workflow.

This module now focuses on a single entry point that adds a `screen_option`
pulldown to a Write node and wires the label + a beforeRender script. The
beforeRender script updates the Screens Manager panel's "Default screen" UI
directly, falling back to the root GSV if the panel is not available.
"""

from typing import Optional

try:
    import nuke  # type: ignore
except Exception:  # pragma: no cover
    nuke = None  # type: ignore

import gsv_utils
try:
    # Optional import used by other tools; not strictly needed here because the
    # injected beforeRender script imports at run-time. Kept for type hints.
    from screens_manager import set_default_screen_via_ui  # type: ignore
except Exception:  # pragma: no cover
    set_default_screen_via_ui = None  # type: ignore
 
def get_screen_options() -> list:
    """Return the current list of screen names from `__default__.screens` options.

    Returns an empty list if unavailable.
    """

    try:
        return gsv_utils.get_list_options("__default__.screens")
    except Exception:
        return []
def add_screen_option_knob(node: Optional[object] = None) -> None:
    """Add a `screen_option` pulldown to a selected Write and wire expressions.

    - Creates or refreshes an `Enumeration_Knob`/`Pulldown_Knob` named
      `screen_option` populated from `__default__.screens` list options.
    - Sets the node `label` to the TCL expression `[value screen_option]`.
    - Inserts a Python expression into the `beforeRender` knob that updates the
      Root GSV `__default__.screens` to the selected value before rendering.
    """

    if nuke is None:
        return
    try:
        nd = nuke.selectedNode()
    except Exception:
        nuke.message("No selected node")
        return

    try:
        if nd.Class() != "Write":
            nuke.message("The selected node is not a Write node or does not contain one.")
            return
    except Exception as e:
        print(f"Error: {e}")
        return

    # Build or refresh the pulldown values
    screens = get_screen_options()
    menu_str = " ".join(screens) if screens else ""

    try:
        if "screen_option" in nd.knobs():
            # Refresh values when possible
            try:
                nd["screen_option"].setValues(screens)
            except Exception:
                try:
                    nd["screen_option"].setValue(menu_str)
                except Exception:
                    pass
        else:
            if screens:
                try:
                    knob = nuke.Enumeration_Knob("screen_option", "Screen Option", screens)
                except Exception:
                    knob = nuke.Pulldown_Knob("screen_option", "Screen Option", menu_str)
            else:
                knob = nuke.String_Knob("screen_option", "Screen Option", "")
            nd.addKnob(knob)
            # Default selection from root if available
            current = gsv_utils.get_value("__default__.screens")
            if current:
                try:
                    knob.setValue(current)
                except Exception:
                    pass
    except Exception:
        pass

    # Update node label to show the chosen option
    try:
        nd["label"].setValue("[value screen_option]")
    except Exception:
        pass

    # Inject beforeRender to drive the Screens Manager UI (fallback to GSV)
    try:
        py_stmt = (
            "_v=nuke.thisNode()['screen_option'].value();m=__import__('sys').modules.get('screens_manager');(getattr(m,'set_default_screen_via_ui')(_v) if m else None);nuke.root()['gsv'].setGsvValue('__default__.screens',_v)"
        )
        existing = nd["beforeRender"].value() if "beforeRender" in nd.knobs() else ""
        if py_stmt not in existing:
            new_val = (existing + "\n" + py_stmt).strip() if existing else py_stmt
            nd["beforeRender"].setValue(new_val)
    except Exception:
        pass


__all__ = [
    "add_screen_option_knob",
    "get_screen_options",
]


