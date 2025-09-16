"""Helpers to wrap Write nodes into VariableGroups for per-screen workflows.

This module now focuses on a single operation: take a selected Write node,
encapsulate it inside a `VariableGroup`, and expose all of the Write's knobs on
the group's interface. Artists can then switch screen variables directly on the
VariableGroup node using Nuke's native multi-shot UI without any custom
callbacks or scripts.
"""

from typing import Iterable, List, Optional

try:
    import nuke  # type: ignore
except Exception:  # pragma: no cover - keep import-safe when Nuke is absent
    nuke = None  # type: ignore


_LOG_PREFIX = "[BCN Screens]"

# Knobs that should not be promoted because the VariableGroup already provides
# its own versions or they are positional/housekeeping values.
_RESERVED_KNOBS = {
    "name",
    "label",
    "xpos",
    "ypos",
    "selected",
    "hide_input",
    "note_font",
    "note_font_size",
    "note_font_color",
    "tile_color",
    "gl_color",
    "cached",
    "knobChanged",
    "help",
    "onCreate",
    "onDestroy",
    "node_class",
}


def _log(message: str) -> None:
    """Lightweight logger for Script Editor visibility."""

    try:
        print(f"{_LOG_PREFIX} {message}")
    except Exception:
        pass


def _describe(node: Optional[object]) -> str:
    """Generate a readable description for logging purposes."""

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


def _iter_write_knobs(write_node: object) -> Iterable[tuple[str, object]]:
    """Yield knobs from the internal Write node in display order."""

    try:
        knobs = getattr(write_node, "knobs")()
    except Exception:
        return []
    # Preserve the original ordering by iterating over values()
    return list(knobs.items())


def _add_tab(group: object, name: str, label: str) -> None:
    if name in group.knobs():
        return
    try:
        tab = nuke.Tab_Knob(name, label)  # type: ignore[attr-defined]
        group.addKnob(tab)
    except Exception:
        pass


def _add_link_knob(
    group: object,
    write_node: object,
    name: str,
    label: str,
    tooltip: Optional[str],
) -> bool:
    if name in _RESERVED_KNOBS:
        return False
    if name in group.knobs():
        return False
    try:
        link = nuke.Link_Knob(name, label)  # type: ignore[attr-defined]
        link.makeLink(write_node, name)
        if tooltip:
            try:
                link.setTooltip(tooltip)
            except Exception:
                pass
        group.addKnob(link)
        return True
    except Exception:
        _log(f"Failed to promote knob '{name}' from {_describe(write_node)}")
    return False


def _promote_write_knobs(group: object, write_node: object) -> None:
    """Expose Write node knobs on the VariableGroup interface."""

    added = 0
    for name, knob in _iter_write_knobs(write_node):
        try:
            klass = knob.Class()
        except Exception:
            klass = ""

        label_attr = getattr(knob, "label", None)
        if callable(label_attr):
            try:
                label = label_attr()
            except Exception:
                label = name
        elif label_attr:
            label = str(label_attr)
        else:
            label = name

        tile_color_attr = getattr(knob, "tileColor", None)
        if callable(tile_color_attr):
            try:
                tile_color = tile_color_attr()
            except Exception:
                tile_color = None
        else:
            tile_color = tile_color_attr

        tooltip_attr = getattr(knob, "tooltip", None)
        if callable(tooltip_attr):
            try:
                tooltip = tooltip_attr()
            except Exception:
                tooltip = None
        else:
            tooltip = tooltip_attr

        if klass == "Tab_Knob":
            _add_tab(group, name, label)
            continue

        if _add_link_knob(group, write_node, name, label, tooltip, tile_color):
            added += 1

    _log(f"Promoted {added} knobs from {_describe(write_node)} to {_describe(group)}")


def _find_internal_node(
    group: object,
    original_name: str,
    prefer_publish_instance: bool = False,
) -> Optional[object]:
    """Return the node inside the VariableGroup to promote knobs from."""

    nodes: List[object] = []

    try:
        with group:
            try:
                named = nuke.toNode(original_name)
            except Exception:
                named = None
            if named is not None:
                return named
            nodes = list(nuke.allNodes(recurse=False))  # type: ignore[attr-defined]
    except Exception:
        nodes = []

    if prefer_publish_instance:
        for node in nodes:
            try:
                if "publish_instance" in node.knobs():
                    return node
            except Exception:
                continue

    for node in nodes:
        try:
            if node.Class() == "Write":
                return node
        except Exception:
            continue

    return nodes[0] if nodes else None


def _collapse_into_variable_group(node: object) -> Optional[object]:
    """Collapse the given node into a new VariableGroup."""

    try:
        previous_selection = list(nuke.selectedNodes())  # type: ignore[attr-defined]
    except Exception:
        previous_selection = []

    try:
        for other in previous_selection:
            try:
                other.setSelected(False)
            except Exception:
                pass
        node.setSelected(True)
        vg = nuke.collapseToVariableGroup()  # type: ignore[attr-defined]
    except Exception as exc:
        _log(f"Failed to collapse node {_describe(node)} into VariableGroup: {exc}")
        vg = None
    finally:
        # Restore previous selection, preferring the new VariableGroup if successful.
        try:
            if vg is not None:
                vg.setSelected(True)
            else:
                for other in previous_selection:
                    try:
                        other.setSelected(True)
                    except Exception:
                        pass
        except Exception:
            pass

    return vg


def encapsulate_write_with_variable_group(node: Optional[object] = None) -> Optional[object]:
    """Wrap a Write or publishable Group node in a VariableGroup and expose knobs."""

    if nuke is None:
        _log("Nuke module not available; cannot create VariableGroup")
        return None

    target = node
    if target is None:
        try:
            target = nuke.selectedNode()  # type: ignore[attr-defined]
        except Exception:
            nuke.message("Select a Write node first")
            return None

    prefer_publish = False

    try:
        node_class = target.Class()
    except Exception:
        nuke.message("Unable to determine node class")
        return None

    try:
        has_publish_knob = "publish_instance" in target.knobs()
    except Exception:
        has_publish_knob = False

    if node_class != "Write" and not (node_class == "Group" and has_publish_knob):
        nuke.message("Select a Write node or a Group with a publish_instance knob")
        _log(f"Cannot encapsulate node {_describe(target)} (class {node_class})")
        return None

    if node_class == "Group" and has_publish_knob:
        prefer_publish = True

    undo = getattr(nuke, "Undo", None)
    if undo is not None:
        try:
            undo.begin("Encapsulate Write in VariableGroup")
        except Exception:
            undo = None

    try:
        group = _collapse_into_variable_group(target)
        if group is None:
            return None

        original_name = getattr(target, "name", lambda: "Write")()
        try:
            group.setName(f"{original_name}_VG")
        except Exception:
            pass

        promote_target = _find_internal_node(
            group,
            original_name,
            prefer_publish_instance=prefer_publish,
        )
        if promote_target is None:
            nuke.message("The VariableGroup does not contain the expected node")
            _log(f"No internal node found inside {_describe(group)}")
            return group

        # Ensure the internal node keeps its original name for clarity.
        try:
            promote_target.setName(original_name)
        except Exception:
            pass

        _promote_write_knobs(group, promote_target)

        # Show the active variable scope directly on the wrapper label.
        try:
            label_knob = group["label"]
            label_knob.setValue("[value gsv]")
        except Exception:
            pass
        
        try:
            tile_color_knob = group["tile_color"]
            tile_color_knob.setValue(4290838783)
        except Exception:
            pass

        try:
            group.showControlPanel()
        except Exception:
            pass

        return group
    finally:
        if undo is not None:
            try:
                undo.end()
            except Exception:
                pass


__all__ = [
    "encapsulate_write_with_variable_group",
]
