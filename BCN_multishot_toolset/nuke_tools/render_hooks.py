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
        screen=gsv_utils.get_value("__default__.screen"),
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
        gsv_utils.set_value("__default__.screen", ctx.screen)
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


def _apply_screen_project_settings(screen_name: str) -> None:
    """Stub: apply per-screen project settings (format/range) if encoded in GSVs.

    This can be extended to read from the corresponding `screen_<name>` group's
    GSV values. Kept minimal for safety.
    """

    # Future: lookup VariableGroup and pull format/fps/first/last
    _ = screen_name


def before_render_handler() -> None:
    """Before-render: set Root screen to Write's assigned_screen if present."""

    global _PREV
    if nuke is None:
        return
    try:
        node = nuke.thisNode()
    except Exception:
        return

    _PREV = _capture_root_context()

    try:
        screen = node["assigned_screen"].value()
        screen = str(screen).strip()
    except Exception:
        screen = None

    if screen:
        gsv_utils.set_value("__default__.screen", screen)
        _apply_screen_project_settings(screen)


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
        nuke.addAfterRender(after_render_handler)
    except Exception:
        pass


__all__ = [
    "install_render_callbacks",
    "before_render_handler",
    "after_render_handler",
]


