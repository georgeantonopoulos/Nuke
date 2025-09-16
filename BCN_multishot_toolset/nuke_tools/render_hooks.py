"""Write node helpers for the Screens workflow.

Simplified design: we do not use global before/after render callbacks. Instead
we register a single `knobChanged` handler for `Write` nodes and detect when the
"Render" button is executed. When triggered, we run the same pre-render logic
that previously lived in `_before_render_callback` to set
`__default__.screens` from the node's `screen_option` before the render begins.

Note: `knobChanged` primarily fires when the Properties panel is open; behavior
in headless scripts depends on how the render is initiated. This module focuses
on running pre-render enforcement when the "Render" knob is activated.
"""

from typing import Optional, Iterable

try:
    import nuke  # type: ignore
except Exception:  # pragma: no cover
    nuke = None  # type: ignore

import gsv_utils

try:
    from screens_manager import set_default_screen_via_ui  # type: ignore
except Exception:  # pragma: no cover
    set_default_screen_via_ui = None  # type: ignore


_LOG_PREFIX = "[BCN Screens]"
_wrappers_installed = False
_original_execute = None  # type: ignore[assignment]
_original_executeMultiple = None  # type: ignore[assignment]


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


def _run_pre_render_from_node(node: Optional[object]) -> None:
    """Run pre-render logic for a Write node by setting `__default__.screens`.

    Reads `screen_option` from the provided node, writes it into the global
    selector, and nudges the UI so expressions re-evaluate. This mirrors the
    previous `_before_render_callback` behavior without relying on global
    render callbacks.
    """

    if nuke is None:
        return

    _log(f"Pre-render logic invoked for node {_describe_node(node)}")
    screen = _get_assigned_screen(node)

    if not screen:
        _log("No screen_option value; leaving current screen")
        return

    try:
        gsv_utils.set_value("__default__.screens", screen)
        _log(f"Set __default__.screens to '{screen}'")
        try:
            refreshed = gsv_utils.get_value("__default__.screens")
            _log(f"Verified __default__.screens now '{refreshed}'")
        except Exception:
            pass
    except Exception:
        _log("Failed to set __default__.screens before render")
        return

    try:
        if hasattr(nuke, "updateUI"):
            nuke.updateUI()
            _log("Called nuke.updateUI() after switching screen")
    except Exception:
        _log("nuke.updateUI() failed during pre-render; continuing")

    if set_default_screen_via_ui is not None:
        try:
            set_default_screen_via_ui(screen)
            _log("Updated Screens Manager UI selection")
        except Exception:
            _log("Screens Manager UI update failed; continuing")
            pass


def _on_knob_changed() -> None:
    """KnobChanged handler: when Write's Render knob is pressed, enforce screen.

    This detects the `render` knob on a `Write` node and runs pre-render logic
    so the `__default__.screens` GSV reflects the node's `screen_option`.
    """

    if nuke is None:
        return

    try:
        n = nuke.thisNode()
        k = nuke.thisKnob()
    except Exception:
        return

    try:
        if not n or n.Class() != "Write" or not k or not hasattr(k, "name"):
            return
        if k.name().lower() != "render":
            return
    except Exception:
        return

    _run_pre_render_from_node(n)


def _install_execute_wrappers() -> None:
    """Install wrappers for `nuke.execute` and `nuke.executeMultiple` safely.

    The wrappers call `_run_pre_render_from_node` for Write nodes that have a
    `screen_option` knob before delegating to the original execute functions.
    This ensures headless/programmatic renders also receive the correct screen
    context prior to evaluation.
    """

    global _wrappers_installed, _original_execute, _original_executeMultiple

    if nuke is None:
        _log("Nuke module unavailable; cannot install execute wrappers")
        return
    if _wrappers_installed:
        return

    # Wrap nuke.execute
    try:
        if hasattr(nuke, "execute") and _original_execute is None:  # type: ignore[attr-defined]
            _original_execute = nuke.execute  # type: ignore[attr-defined]

            def _wrapped_execute(node, start, end, incr=1, *args, **kwargs):  # type: ignore[no-redef]
                try:
                    target = node
                    try:
                        if isinstance(node, str):
                            target = nuke.toNode(node)  # type: ignore[attr-defined]
                    except Exception:
                        pass
                    if target is not None:
                        try:
                            if getattr(target, "Class", lambda: "")() == "Write" and "screen_option" in target.knobs():
                                _run_pre_render_from_node(target)
                        except Exception:
                            pass
                except Exception:
                    pass
                return _original_execute(node, start, end, incr, *args, **kwargs)  # type: ignore[misc]

            nuke.execute = _wrapped_execute  # type: ignore[attr-defined]
            _log("Wrapped nuke.execute for pre-render enforcement")
    except Exception:
        _log("Failed to wrap nuke.execute")

    # Wrap nuke.executeMultiple
    try:
        if hasattr(nuke, "executeMultiple") and _original_executeMultiple is None:  # type: ignore[attr-defined]
            _original_executeMultiple = nuke.executeMultiple  # type: ignore[attr-defined]

            def _wrapped_executeMultiple(nodes, start, end, incr=1, *args, **kwargs):  # type: ignore[no-redef]
                try:
                    candidates = nodes
                    try:
                        # Normalize to iterable
                        if isinstance(nodes, (str, bytes)):
                            candidates = [nodes]
                        elif not isinstance(nodes, Iterable):
                            candidates = [nodes]
                    except Exception:
                        candidates = [nodes]

                    for item in list(candidates):  # make a shallow copy for safety
                        try:
                            target = item
                            if isinstance(item, str):
                                try:
                                    target = nuke.toNode(item)  # type: ignore[attr-defined]
                                except Exception:
                                    target = None
                            if target is not None and getattr(target, "Class", lambda: "")() == "Write":
                                try:
                                    if "screen_option" in target.knobs():
                                        _run_pre_render_from_node(target)
                                except Exception:
                                    pass
                        except Exception:
                            pass
                except Exception:
                    pass
                return _original_executeMultiple(nodes, start, end, incr, *args, **kwargs)  # type: ignore[misc]

            nuke.executeMultiple = _wrapped_executeMultiple  # type: ignore[attr-defined]
            _log("Wrapped nuke.executeMultiple for pre-render enforcement")
    except Exception:
        _log("Failed to wrap nuke.executeMultiple")

    _wrappers_installed = True


def _install_knobchanged() -> None:
    """Register the `knobChanged` handler for Write nodes once per session."""

    if nuke is None:
        _log("Nuke module unavailable; cannot install knobChanged handler")
        return

    try:
        try:
            nuke.removeKnobChanged(_on_knob_changed)  # type: ignore[attr-defined]
        except Exception:
            pass
        nuke.addKnobChanged(_on_knob_changed, nodeClass="Write")  # type: ignore[attr-defined]
        _log("Registered knobChanged handler for Write nodes")
    except Exception:
        _log("Failed to register knobChanged handler")
        pass


def add_screen_option_knob(node: Optional[object] = None) -> None:
    """Add a `screen_option` pulldown to a selected Write and wire expressions."""

    if nuke is None:
        return

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
    """Public entry point retained for backward compatibility.

    Registers the `knobChanged` handler so pre-render logic runs when the Write
    node's Render knob is executed.
    """

    _log("install_render_callbacks invoked (registering knobChanged + execute wrappers)")
    _install_knobchanged()
    _install_execute_wrappers()


__all__ = [
    "add_screen_option_knob",
    "get_screen_options",
    "install_render_callbacks",
]
