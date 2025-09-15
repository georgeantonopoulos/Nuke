"""Render-time hooks for enforcing screen context on Writes.

Keeps logic minimal: on before render, force Root `__default__.screen` to the
assigned value if present; after render, restore previous context.

Where possible, prefer expressions and VariableSwitch/Link nodes to avoid
imperative callbacks. This module focuses on render-time safety.
"""

from dataclasses import dataclass
from typing import Optional

try:
    import nuke  # type: ignore
except Exception:  # pragma: no cover
    nuke = None  # type: ignore

import gsv_utils


@dataclass
class _RootContext:
    screen: Optional[str]
    format_name: Optional[str]
    fps: Optional[float]
    first: Optional[int]
    last: Optional[int]


_PREV: Optional[_RootContext] = None


def _capture_root_context() -> _RootContext:
    if nuke is None:
        return _RootContext(None, None, None, None, None)
    root = nuke.root()
    return _RootContext(
        screen=gsv_utils.get_value("__default__.screens"),
        format_name=str(root["format"].value()) if "format" in root.knobs() else None,
        fps=float(root["fps"].value()) if "fps" in root.knobs() else None,
        first=int(root["first_frame"].value()) if "first_frame" in root.knobs() else None,
        last=int(root["last_frame"].value()) if "last_frame" in root.knobs() else None,
    )


def _restore_root_context(ctx: Optional[_RootContext]) -> None:
    if nuke is None or ctx is None:
        return
    root = nuke.root()
    if ctx.screen:
        gsv_utils.set_value("__default__.screens", ctx.screen)
    if ctx.format_name:
        try:
            root["format"].setValue(ctx.format_name)
        except Exception:
            pass
    if ctx.fps is not None:
        try:
            root["fps"].setValue(ctx.fps)
        except Exception:
            pass
    if ctx.first is not None:
        try:
            root["first_frame"].setValue(ctx.first)
        except Exception:
            pass
    if ctx.last is not None:
        try:
            root["last_frame"].setValue(ctx.last)
        except Exception:
            pass


def _set_root_screen(screen_name: str) -> None:
    """Safely set the root `__default__.screens` value on the main thread.

    Some render callbacks execute off the UI thread. Updating the GSV via the
    main thread avoids timing issues where upstream nodes (e.g. VariableSwitch)
    evaluate before the variable change is visible.
    """

    if nuke is None or not screen_name:
        return

    def _do_set() -> None:
        try:
            gsv_utils.set_value("__default__.screens", screen_name)
        except Exception:
            pass

    try:
        # Execute on main thread when possible
        exec_in_main = getattr(nuke, "executeInMainThreadWithResult", None)
        if callable(exec_in_main):
            exec_in_main(_do_set)
        else:
            _do_set()
    except Exception:
        _do_set()


def _apply_screen_project_settings(screen_name: str) -> None:
    """Stub: apply per-screen project settings (format/range) if encoded in GSVs.

    This can be extended to read from the corresponding `screen_<name>` group's
    GSV values. Kept minimal for safety.
    """

    # Future: lookup VariableGroup and pull format/fps/first/last
    _ = screen_name


def before_render_handler() -> None:
    """Before-render: set Root screen to the Write's chosen screen.

    Prefers the `screen_option` knob, falls back to `assigned_screen`.
    """

    global _PREV
    if nuke is None:
        return
    try:
        node = nuke.thisNode()
    except Exception:
        return

    _PREV = _capture_root_context()

    screen = None
    # Prefer new knob, then legacy
    for key in ("screen_option", "assigned_screen"):
        try:
            if key in node.knobs():
                val = str(node[key].value()).strip()
                if val:
                    screen = val
                    break
        except Exception:
            pass

    if screen:
        _set_root_screen(screen)
        _apply_screen_project_settings(screen)


def before_frame_render_handler() -> None:
    """Per-frame safety: re-assert the root screen before each frame render.

    This guards against any lazy evaluation that might have captured stale
    values before the global before-render ran.
    """

    if nuke is None:
        return
    try:
        node = nuke.thisNode()
    except Exception:
        return

    screen = None
    for key in ("screen_option", "assigned_screen"):
        try:
            if key in node.knobs():
                val = str(node[key].value()).strip()
                if val:
                    screen = val
                    break
        except Exception:
            pass

    if screen:
        _set_root_screen(screen)


def after_render_handler() -> None:
    """After-render: restore prior Root context."""

    global _PREV
    _restore_root_context(_PREV)
    _PREV = None


def install_render_callbacks() -> None:
    """Install global before/after render callbacks."""

    if nuke is None:
        return
    try:
        nuke.addBeforeRender(before_render_handler)
        # Per-frame safety re-assertion (Nuke 16 supports beforeFrameRender)
        try:
            nuke.addBeforeFrameRender(before_frame_render_handler)
        except Exception:
            pass
        nuke.addAfterRender(after_render_handler)
    except Exception:
        pass


def get_screen_options() -> list:
    """Return the current list of screen names from `__default__.screens` options.

    Returns an empty list if unavailable.
    """

    try:
        return gsv_utils.get_list_options("__default__.screens")
    except Exception:
        return []


def add_assigned_screen_knob(node: Optional[object] = None) -> None:
    """Add an `assigned_screen` Pulldown knob to a Write node.

    If `node` is None, operate on the currently selected node. The knob's
    choices are populated from the root `__default__.screen` options, and the
    default value is set to the current root selection if present.
    """

    if nuke is None:
        return
    try:
        nd = node or nuke.selectedNode()
    except Exception:
        return

    try:
        if nd.Class() != "Write":
            return
    except Exception:
        return

    # If knob already exists, refresh its menu if possible
    try:
        if "assigned_screen" in nd.knobs():
            screens = get_screen_options()
            if screens:
                menu_str = " ".join(screens)
                try:
                    nd["assigned_screen"].setValues(screens)  # for Enum_Knob
                except Exception:
                    try:
                        nd["assigned_screen"].setValue(menu_str)
                    except Exception:
                        pass
            return
    except Exception:
        pass

    # Create new pulldown
    screens = get_screen_options()
    menu_str = " ".join(screens) if screens else ""
    try:
        if menu_str:
            knob = nuke.Pulldown_Knob("assigned_screen", "Assigned Screen", menu_str)
        else:
            knob = nuke.String_Knob("assigned_screen", "Assigned Screen", "")
        nd.addKnob(knob)
        # Set default to current root selection
        current = gsv_utils.get_value("__default__.screens")
        if current:
            try:
                knob.setValue(current)
            except Exception:
                pass
    except Exception:
        pass


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

    # Inject beforeRender Python to set the GSV to the chosen screen
    try:
        py_stmt = (
            "python nuke.root()['gsv'].setGsvValue('__default__.screens', "
            "nuke.thisNode()['screen_option'].value())"
        )
        existing = nd["beforeRender"].value() if "beforeRender" in nd.knobs() else ""
        if py_stmt not in existing:
            new_val = (existing + "\n" + py_stmt).strip() if existing else py_stmt
            nd["beforeRender"].setValue(new_val)
    except Exception:
        pass


__all__ = [
    "install_render_callbacks",
    "before_render_handler",
    "after_render_handler",
    "add_assigned_screen_knob",
    "add_screen_option_knob",
    "get_screen_options",
]


