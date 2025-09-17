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

    _log(f"Iterating knobs for {_describe(write_node)}")
    try:
        knobs = getattr(write_node, "knobs")()
    except Exception as exc:
        _log(f"Failed to retrieve knobs for {_describe(write_node)}: {exc}")
        return []
    items = list(knobs.items())
    _log(f"Found {len(items)} knobs on {_describe(write_node)}")
    # Preserve the original ordering by iterating over values()
    return items


def _add_tab(group: object, name: str, label: str) -> None:
    if name in group.knobs():
        _log(f"Tab '{name}' already exists on {_describe(group)}; skipping")
        return
    try:
        _log(f"Adding Tab '{name}' (label '{label}') to {_describe(group)}")
        tab = nuke.Tab_Knob(name, label)  # type: ignore[attr-defined]
        group.addKnob(tab)
    except Exception as exc:
        _log(f"Failed to add Tab '{name}' to {_describe(group)}: {exc}")


def _add_link_knob(
    group: object,
    write_node: object,
    name: str,
    label: str,
    tooltip: Optional[str],
) -> bool:
    _log(
        f"Attempting to link knob '{name}' (label '{label}') from {_describe(write_node)} to {_describe(group)}"
    )
    if name in _RESERVED_KNOBS:
        _log(f"Skipping reserved knob '{name}'")
        return False
    if name in group.knobs():
        _log(f"Knob '{name}' already present on {_describe(group)}; skipping")
        return False
    try:
        link = nuke.Link_Knob(name, label)  # type: ignore[attr-defined]
        link.makeLink(write_node, name)
        if tooltip:
            try:
                link.setTooltip(tooltip)
            except Exception as exc:
                _log(f"Failed to set tooltip for knob '{name}': {exc}")
        group.addKnob(link)
        _log(f"Linked knob '{name}' onto {_describe(group)}")
        return True
    except Exception as exc:
        _log(
            f"Failed to link knob '{name}' from {_describe(write_node)} to {_describe(group)}: {exc}"
        )
    return False


def _promote_write_knobs(group: object, write_node: object) -> None:
    """Expose Write node knobs on the VariableGroup interface."""

    _log(
        f"Promoting knobs from {_describe(write_node)} into group {_describe(group)}"
    )
    added = 0
    for name, knob in _iter_write_knobs(write_node):
        try:
            klass = knob.Class()
        except Exception:
            klass = ""

        _log(f"Inspecting knob '{name}' of class '{klass}'")

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
            _log(f"Adding Tab_Knob '{name}'")
            _add_tab(group, name, label)
            continue

        try:
            if _add_link_knob(group, write_node, name, label, tooltip):
                added += 1
        except Exception as exc:
            _log(f"Error while linking knob '{name}': {exc}")

    _log(f"Promoted {added} knobs from {_describe(write_node)} to {_describe(group)}")


def _find_internal_node(
    group: object,
    original_name: str,
    prefer_publish_instance: bool = False,
) -> Optional[object]:
    """Return the node inside the VariableGroup to promote knobs from."""

    nodes: List[object] = []

    _log(
        f"Searching for internal node inside {_describe(group)} (prefer_publish_instance={prefer_publish_instance})"
    )
    try:
        with group:
            try:
                named = nuke.toNode(original_name)
            except Exception as exc:
                _log(
                    f"Lookup by name '{original_name}' failed inside {_describe(group)}: {exc}"
                )
                named = None
            if named is not None:
                _log(f"Found internal node by name: {_describe(named)}")
                return named
            nodes = list(nuke.allNodes(recurse=False))  # type: ignore[attr-defined]
            _log(f"Found {len(nodes)} internal nodes inside {_describe(group)}")
    except Exception as exc:
        _log(f"Failed to list internal nodes in {_describe(group)}: {exc}")
        nodes = []

    if prefer_publish_instance:
        for node in nodes:
            try:
                if "publish_instance" in node.knobs():
                    _log(
                        f"Selecting internal node with 'publish_instance': {_describe(node)}"
                    )
                    return node
            except Exception:
                continue

    for node in nodes:
        try:
            if node.Class() == "Write":
                _log(f"Selecting internal Write node: {_describe(node)}")
                return node
        except Exception:
            continue

    if nodes:
        _log(f"Falling back to first internal node: {_describe(nodes[0])}")
        return nodes[0]
    _log("No internal nodes found")
    return None


def _collapse_into_variable_group(node: object) -> Optional[object]:
    """Collapse the given node into a new VariableGroup."""

    try:
        previous_selection = list(nuke.selectedNodes())  # type: ignore[attr-defined]
    except Exception:
        previous_selection = []

    _log(
        f"Collapsing node {_describe(node)} into VariableGroup (prev selection count={len(previous_selection)})"
    )
    try:
        for other in previous_selection:
            try:
                other.setSelected(False)
            except Exception:
                pass
        node.setSelected(True)
        vg = nuke.collapseToVariableGroup()  # type: ignore[attr-defined]
        _log(f"Created VariableGroup from {_describe(node)} -> {_describe(vg)}")
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

    _log(f"Encapsulation target {_describe(target)} of class '{node_class}'")

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
        _log("Prefer internal node with 'publish_instance' for promotion")

    undo = getattr(nuke, "Undo", None)
    if undo is not None:
        try:
            undo.begin("Encapsulate Write in VariableGroup")
            _log("Undo group begun: 'Encapsulate Write in VariableGroup'")
        except Exception:
            undo = None

    try:
        group = _collapse_into_variable_group(target)
        if group is None:
            _log("VariableGroup creation failed; aborting")
            return None

        original_name = getattr(target, "name", lambda: "Write")()
        try:
            group.setName(f"{original_name}_VG")
            _log(f"Named VariableGroup '{original_name}_VG'")
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
            _log(
                f"Set internal promote target name to '{original_name}' -> {_describe(promote_target)}"
            )
        except Exception:
            pass

        _log("Starting knob promotion onto VariableGroup")
        _promote_write_knobs(group, promote_target)

        # Show the active variable scope directly on the wrapper label.
        try:
            label_knob = group["label"]
            label_knob.setValue("[value gsv]")
            _log("Set group label to display '[value gsv]'")
        except Exception:
            pass
        
        try:
            tile_color_knob = group["tile_color"]
            tile_color_knob.setValue(4290838783)
            _log("Applied default tile color to VariableGroup")
        except Exception:
            pass

        try:
            group.showControlPanel()
            _log("Opened VariableGroup control panel")
        except Exception:
            pass

        return group
    finally:
        if undo is not None:
            try:
                undo.end()
                _log("Undo group ended")
            except Exception:
                pass


__all__ = [
    "encapsulate_write_with_variable_group",
]
