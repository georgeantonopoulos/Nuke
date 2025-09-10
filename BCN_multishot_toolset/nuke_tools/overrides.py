"""Helpers to create per-screen overrides using GSVs and expressions.

Avoids generic callbacks where possible. These utilities focus on wiring
knob expressions to GSVs and providing a small helper to respond to GSV
changes using `nuke.callbacks.onGsvSetChanged` if available.
"""

from typing import Optional

try:
    import nuke  # type: ignore
except Exception:  # pragma: no cover
    nuke = None  # type: ignore


def set_knob_expression_from_gsv(node: "nuke.Node", knob_name: str, gsv_path: str) -> None:  # type: ignore[name-defined]
    """Inject a python expression to read a value from a GSV path.

    Example expression: python {nuke.root()['gsv'].getGsvValue('path.to.var')}
    """

    if nuke is None or node is None:
        return
    try:
        expr = f"python {{nuke.root()['gsv'].getGsvValue('{gsv_path}')}}"
        node[knob_name].setExpression(expr)
    except Exception:
        pass


def on_screen_changed(callback) -> Optional[object]:
    """Attach a handler for when `__default__.screen` changes, if supported.

    Uses `nuke.callbacks.onGsvSetChanged` when available; returns the handler
    token/object if applicable; otherwise None.
    """

    if nuke is None:
        return None

    cb = getattr(nuke, "callbacks", None)
    if cb is None:
        return None

    handler = None
    try:
        # Prefer the specific GSV change callback if present
        if hasattr(cb, "onGsvSetChanged"):
            handler = cb.onGsvSetChanged(callback)  # type: ignore[attr-defined]
            return handler
    except Exception:
        # Fall back to no registration; callers can decide alternative strategies
        return None
    return None


__all__ = [
    "set_knob_expression_from_gsv",
    "on_screen_changed",
]


