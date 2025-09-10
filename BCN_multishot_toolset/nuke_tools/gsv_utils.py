"""Thin utilities around Nuke's GSV API to keep code readable.

All functions are defensive and return early when Nuke is not available to
keep the module import-safe outside Nuke.
"""

from typing import Iterable, List, Optional, Sequence

try:
    import nuke  # type: ignore
except Exception:  # pragma: no cover - allow importing outside Nuke
    nuke = None  # type: ignore


def get_root_gsv_knob():
    """Return the Root GSV knob (`nuke.Gsv_Knob`) or None if unavailable."""

    if nuke is None:
        return None
    try:
        return nuke.root()["gsv"]
    except Exception:
        return None


def ensure_list_datatype(path: str) -> None:
    """Ensure the GSV at `path` is of type List.

    If unavailable, this is a no-op.
    """

    gsv = get_root_gsv_knob()
    if gsv is None:
        return
    try:
        gsv.setDataType(path, nuke.gsv.DataType.List)  # type: ignore[attr-defined]
    except Exception:
        pass


def set_list_options(path: str, options: Sequence[str]) -> None:
    """Set list options for a List-type GSV at `path`. No-op on failure."""

    gsv = get_root_gsv_knob()
    if gsv is None:
        return
    try:
        gsv.setListOptions(path, list(options))
    except Exception:
        pass


def get_list_options(path: str) -> List[str]:
    """Get list options for a List-type GSV at `path`. Returns empty on error."""

    gsv = get_root_gsv_knob()
    if gsv is None:
        return []
    try:
        opts = gsv.getListOptions(path)
        return list(opts) if isinstance(opts, Iterable) else []
    except Exception:
        return []


def set_value(path: str, value: str) -> None:
    """Set the GSV value at `path`. No-op on failure."""

    gsv = get_root_gsv_knob()
    if gsv is None:
        return
    try:
        gsv.setGsvValue(path, value)
    except Exception:
        pass


def get_value(path: str) -> Optional[str]:
    """Get the GSV value at `path`. Returns None on error."""

    gsv = get_root_gsv_knob()
    if gsv is None:
        return None
    try:
        return gsv.getGsvValue(path)
    except Exception:
        return None


def ensure_screen_list(screens: Sequence[str], default_screen: Optional[str] = None) -> None:
    """Ensure `__default__.screen` exists, is a List, and has given options.

    Parameters:
      - screens: unique screen names
      - default_screen: initial selection; falls back to first option
    """

    ensure_list_datatype("__default__.screen")
    set_list_options("__default__.screen", screens)
    if default_screen is None and screens:
        default_screen = screens[0]
    if default_screen:
        set_value("__default__.screen", default_screen)


def create_variable_group(name: str):
    """Create a VariableGroup node with the given name, if possible.

    Returns the group node or None.
    """

    if nuke is None:
        return None
    try:
        return nuke.nodes.VariableGroup(name=name)
    except Exception:
        return None


