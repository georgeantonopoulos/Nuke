"""Write node helpers for the Screens workflow.

The prior approach injected a per-node `beforeRender` snippet that attempted to
update the root `__default__.screens` GSV just before rendering. Nuke resolves
Graph Scope Variables before executing a Write node's `beforeRender`, so the
update landed too late and renders used stale values. This module now installs
central callbacks that adjust the GSV at the correct stage, keeping the screen
assignment in sync for both local renders and render-farm jobs.
"""

from typing import List, Optional

try:
    import nuke  # type: ignore
except Exception:  # pragma: no cover
    nuke = None  # type: ignore

import gsv_utils

try:
    from screens_manager import set_default_screen_via_ui  # type: ignore
except Exception:  # pragma: no cover
    set_default_screen_via_ui = None  # type: ignore


_callbacks_registered = False
_screen_stack: List[Optional[str]] = []


def get_screen_options() -> list:
    """Return the current list of screen names from `__default__.screens` options."""

    try:
        return gsv_utils.get_list_options("__default__.screens")
    except Exception:
        return []


def _resolve_target_node(node: Optional[object] = None) -> Optional[object]:
    """Return the Write-like node driving the current render."""

    if node is not None:
        return node
    if nuke is None:
        return None
    try:
        return nuke.thisNode()
    except Exception:
        return None


def _get_assigned_screen(node: Optional[object]) -> Optional[str]:
    """Fetch the screen assignment stored on `node` if the knob exists."""

    if node is None:
        return None
    try:
        if "screen_option" not in node.knobs():
            return None
        knob = node["screen_option"]
    except Exception:
        return None

    try:
        value = knob.value()
    except Exception:
        return None

    if isinstance(value, str):
        value = value.strip()
    return value or None


def _before_render_callback(**kwargs: object) -> None:
    """Apply the node's assigned screen before frame evaluation starts."""

    if nuke is None:
        return

    node = _resolve_target_node(node=kwargs.get("node") if isinstance(kwargs, dict) else None)
    screen = _get_assigned_screen(node)

    # Push current value so we can restore after render completes.
    current = gsv_utils.get_value("__default__.screens")
    _screen_stack.append(current)

    if not screen:
        return

    try:
        gsv_utils.set_value("__default__.screens", screen)
    except Exception:
        return

    if set_default_screen_via_ui is not None:
        try:
            set_default_screen_via_ui(screen)
        except Exception:
            pass


def _after_render_callback(**kwargs: object) -> None:
    """Restore the previously selected screen once the render finishes."""

    if not _screen_stack:
        return

    previous = _screen_stack.pop()
    if previous is None:
        return

    try:
        gsv_utils.set_value("__default__.screens", previous)
    except Exception:
        pass


def _ensure_render_callbacks() -> None:
    """Register global before/after render callbacks once per session."""

    global _callbacks_registered

    if _callbacks_registered or nuke is None:
        return

    try:
        callbacks = getattr(nuke, "callbacks", None)

        try:
            if callbacks and hasattr(callbacks, "removeBeforeRender"):
                callbacks.removeBeforeRender(_before_render_callback)
            else:
                nuke.removeBeforeRender(_before_render_callback)  # type: ignore[attr-defined]
        except Exception:
            pass
        try:
            if callbacks and hasattr(callbacks, "removeAfterRender"):
                callbacks.removeAfterRender(_after_render_callback)
            else:
                nuke.removeAfterRender(_after_render_callback)  # type: ignore[attr-defined]
        except Exception:
            pass

        if callbacks and hasattr(callbacks, "addBeforeRender"):
            callbacks.addBeforeRender(_before_render_callback)
        else:
            nuke.addBeforeRender(_before_render_callback)  # type: ignore[attr-defined]

        if callbacks and hasattr(callbacks, "addAfterRender"):
            callbacks.addAfterRender(_after_render_callback)
        else:
            nuke.addAfterRender(_after_render_callback)  # type: ignore[attr-defined]
        _callbacks_registered = True
    except Exception:
        pass


def add_screen_option_knob(node: Optional[object] = None) -> None:
    """Add a `screen_option` pulldown to a selected Write and wire expressions."""

    if nuke is None:
        return

    _ensure_render_callbacks()

    try:
        nd = node or nuke.selectedNode()
    except Exception:
        nuke.message("No selected node")
        return

    try:
        if nd.Class() != "Write":
            nuke.message("The selected node is not a Write node or does not contain one.")
            return
    except Exception as exc:
        print(f"Error: {exc}")
        return

    screens = get_screen_options()
    menu_str = " ".join(screens) if screens else ""

    try:
        if "screen_option" in nd.knobs():
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
            current = gsv_utils.get_value("__default__.screens")
            if current:
                try:
                    knob.setValue(current)
                except Exception:
                    pass
    except Exception:
        pass

    try:
        nd["label"].setValue("[value screen_option]")
    except Exception:
        pass


def install_render_callbacks() -> None:
    """Public entry point for init.py and other bootstrap hooks."""

    _ensure_render_callbacks()


__all__ = [
    "add_screen_option_knob",
    "get_screen_options",
    "install_render_callbacks",
]
