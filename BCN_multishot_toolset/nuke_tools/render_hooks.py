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
_LOG_PREFIX = "[BCN Screens]"


def _log(message: str) -> None:
    """Centralised `print` helper so the log output stays consistent."""

    try:
        print(f"{_LOG_PREFIX} {message}")
    except Exception:
        pass


def _describe_node(node: Optional[object]) -> str:
    """Return a useful string for logging the current node context."""

    if node is None:
        return "<none>"
    try:
        if hasattr(node, "fullName"):
            return str(node.fullName())
    except Exception:
        pass
    try:
        if hasattr(node, "name"):
            return str(node.name())
    except Exception:
        pass
    return str(node)


def get_screen_options() -> list:
    """Return the current list of screen names from `__default__.screens` options."""

    try:
        return gsv_utils.get_list_options("__default__.screens")
    except Exception:
        return []


def _resolve_target_node(node: Optional[object] = None, nodes: Optional[object] = None) -> Optional[object]:
    """Return the render-driving Write node if possible."""

    if node is not None:
        if isinstance(node, str) and nuke is not None:
            try:
                converted = nuke.toNode(node)
                if converted is not None:
                    _log(f"Resolved node name '{node}' to {_describe_node(converted)}")
                else:
                    _log(f"Node name '{node}' could not be resolved")
                return converted
            except Exception:
                _log(f"Exception while resolving node name '{node}'")
                return None
        return node

    if isinstance(nodes, (list, tuple)):
        for candidate in nodes:
            if candidate is None:
                continue
            try:
                if getattr(candidate, "Class", lambda: "")() == "Write":
                    _log(f"Resolved render node from nodes list: {_describe_node(candidate)}")
                    return candidate
            except Exception:
                continue

        # Fall back to first entry even if not a Write; better than nothing.
        try:
            first = nodes[0]  # type: ignore[index]
            _log(f"Using first render candidate without class match: {_describe_node(first)}")
            return first
        except Exception:
            pass

    if nuke is None:
        return None

    try:
        node_from_this = nuke.thisNode()
        if node_from_this is not None:
            _log(f"Resolved render node via nuke.thisNode(): {_describe_node(node_from_this)}")
        return node_from_this
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
        _log(f"Failed to read screen_option knob on {_describe_node(node)}")
        return None

    if isinstance(value, str):
        value = value.strip()
    resolved = value or None
    _log(f"screen_option on {_describe_node(node)} resolved to '{resolved}'")
    return resolved


def _before_render_callback(**kwargs: object) -> None:
    """Apply the node's assigned screen before frame evaluation starts."""

    if nuke is None:
        return

    node_kwarg = kwargs.get("node") if isinstance(kwargs, dict) else None
    nodes_kwarg = kwargs.get("nodes") if isinstance(kwargs, dict) else None
    node = _resolve_target_node(node=node_kwarg, nodes=nodes_kwarg)
    _log(f"BeforeRender fired for node {_describe_node(node)}")
    screen = _get_assigned_screen(node)

    # Push current value so we can restore after render completes.
    current = gsv_utils.get_value("__default__.screens")
    _screen_stack.append(current)
    _log(f"Stored previous screen '{current}' (stack depth={len(_screen_stack)})")

    if not screen:
        _log("No screen_option value; leaving current screen")
        return

    try:
        gsv_utils.set_value("__default__.screens", screen)
        _log(f"Set __default__.screens to '{screen}'")
    except Exception:
        _log("Failed to set __default__.screens before render")
        return

    if set_default_screen_via_ui is not None:
        try:
            set_default_screen_via_ui(screen)
            _log("Updated Screens Manager UI selection")
        except Exception:
            _log("Screens Manager UI update failed; continuing")
            pass


def _after_render_callback(**kwargs: object) -> None:
    """Restore the previously selected screen once the render finishes."""

    if not _screen_stack:
        _log("AfterRender fired with empty stack; nothing to restore")
        return

    previous = _screen_stack.pop()
    _log(f"AfterRender restoring previous screen '{previous}' (remaining depth={len(_screen_stack)})")
    if previous is None:
        return

    try:
        gsv_utils.set_value("__default__.screens", previous)
        _log("Restored __default__.screens after render")
    except Exception:
        _log("Failed to restore __default__.screens after render")
        pass


def _ensure_render_callbacks() -> None:
    """Register global before/after render callbacks once per session."""

    global _callbacks_registered

    if _callbacks_registered:
        _log("Render callbacks already installed; skipping")
        return
    if nuke is None:
        _log("Nuke module unavailable; cannot install render callbacks")
        return

    try:
        callbacks = getattr(nuke, "callbacks", None)
        used_callbacks_module = False

        if callbacks:
            try:
                if hasattr(callbacks, "removeBeforeRender"):
                    callbacks.removeBeforeRender(_before_render_callback)
            except Exception:
                pass
            try:
                if hasattr(callbacks, "removeAfterRender"):
                    callbacks.removeAfterRender(_after_render_callback)
            except Exception:
                pass
            try:
                if hasattr(callbacks, "addBeforeRender"):
                    callbacks.addBeforeRender(_before_render_callback, nodeClass="Write")
                    used_callbacks_module = True
                    _log("Registered beforeRender via nuke.callbacks (Write)")
            except Exception:
                pass
            try:
                if hasattr(callbacks, "addAfterRender"):
                    callbacks.addAfterRender(_after_render_callback, nodeClass="Write")
                    used_callbacks_module = True
                    _log("Registered afterRender via nuke.callbacks (Write)")
            except Exception:
                pass

        if not used_callbacks_module:
            # Legacy API fallbacks
            try:
                nuke.removeBeforeRender(_before_render_callback)  # type: ignore[attr-defined]
            except Exception:
                pass
            try:
                nuke.removeAfterRender(_after_render_callback)  # type: ignore[attr-defined]
            except Exception:
                pass
            nuke.addBeforeRender(_before_render_callback)  # type: ignore[attr-defined]
            nuke.addAfterRender(_after_render_callback)  # type: ignore[attr-defined]
            _log("Registered render callbacks via legacy addBefore/AfterRender")
        _callbacks_registered = True
        _log("Render callbacks installed")
    except Exception:
        _log("Failed to install render callbacks")
        pass


def add_screen_option_knob(node: Optional[object] = None) -> None:
    """Add a `screen_option` pulldown to a selected Write and wire expressions."""

    if nuke is None:
        return

    _ensure_render_callbacks()

    try:
        nd = node or nuke.selectedNode()
        _log(f"add_screen_option_knob targeting node {_describe_node(nd)}")
    except Exception:
        nuke.message("No selected node")
        return

    try:
        if nd.Class() != "Write":
            nuke.message("The selected node is not a Write node or does not contain one.")
            _log(f"add_screen_option_knob aborted; node {_describe_node(nd)} is not a Write")
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

    _log("install_render_callbacks invoked")
    _ensure_render_callbacks()


__all__ = [
    "add_screen_option_knob",
    "get_screen_options",
    "install_render_callbacks",
]
