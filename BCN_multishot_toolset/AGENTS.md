# Nuke 16 Multi‑Shot Tools — Agent Plan (AGENTS.md)

## Goals

- Screens Panel: Add/edit a list of “screens” (e.g., `Moxy, Godzilla, NYD400`) and create the variables + a preview switch to fluidly toggle between them.
- Per‑Screen Overrides: Let artists set overrides on any node/knob, specific to each screen.
- Pre‑Render Hooks: On Write nodes (and Writes inside Groups), assign a target screen and, before rendering, enforce that all global variables and switches match that screen.
- Constraint: Leverage Nuke 16’s multi‑shot/Graph Scope Variables (GSV) and VariableGroup APIs; avoid reinventing behavior that the API provides.

## Key Nuke 16 APIs To Use

- Graph Scope Variables (GSV): root knob `nuke.root()['gsv']` is a `nuke.Gsv_Knob`.
  - Manage sets/vars: `Gsv_Knob.addGsvSet()`, `setGsvValue()`, `getGsvValue()`, `setValue()`, `value()`, `removeGsvSet()`, `removeGsv()`, `renameGsvSet()`, `renameGsv()`
  - Data types and options: `Gsv_Knob.setDataType(path, nuke.gsv.DataType.List)`, `Gsv_Knob.setListOptions(path, options)`
  - Variables Panel favorites/labels/tooltips: `setFavorite()`, `setLabel()`, `setTooltip()`
  - Docs: “Graph Scope Variables / Multi‑shot Set‑up” and `nuke.Gsv_Knob`
- Variable Groups: contextual scoping and overriding across the DAG
  - Create nodes: `nuke.nodes.VariableGroup(name='…')` or `nuke.collapseToVariableGroup()`
  - Paths extend with group names: `variable_group...variable_set.variable_name`
- Callbacks for renders and UI glue: `nuke.addBeforeRender()`, `nuke.addAfterRender()`, `nuke.addKnobChanged()`
- Panels/UI: `nukescripts.PythonPanel`, `nukescripts.panels.registerWidgetAsPanel`, or simple `nuke.Panel`
- Project settings: `nuke.root()['format']`, `['fps']`, `['first_frame']`, `['last_frame']`, `nuke.addFormat()`

References: See Nuke 16 Python docs (notably: `gsv.html`, `_autosummary/nuke.Gsv_Knob.html`, `_autosummary/nuke.collapseToVariableGroup.html`, `callbacks.html`, `custom_panels.html`, `_autosummary/nukescripts.panels.registerWidgetAsPanel.html`).

## Architecture

- Root‑Level Selector
  - `__default__.screen`: A List‑type GSV on the Root `Gsv_Knob` with options = screen names. It appears in the Variables panel, providing a canonical “current screen” selector.
  - Optional global toggles (favorites): add common switches (e.g., `__default__.use_ocio`, `__default__.render_quality`) and mark as favorites for quick access.

- VariableGroups per Screen
  - For each screen name, create a `VariableGroup` named e.g. `screen_Moxy`, `screen_Godzilla`, etc.
  - Within each screen group’s `Gsv_Knob`, store screen‑specific defaults in `__default__` (format/size/fps/range/paths) and any per‑screen override buckets (e.g., `Overrides` set).
  - Inheritance/overrides: Parent groups can hold shared defaults; child screen groups override only what differs.

- Preview “Variable Switch”
  - Provide an optional helper Group “ScreenSwitch” that contains a `Switch` node. Its `which` value is driven by `__default__.screen` → index mapping.
  - Keep it stateless: update `which` via a small `nuke.addKnobChanged()` or by a Python expression on `which` if acceptable.

- Per‑Screen Node Overrides
  - Store override values in GSVs, keyed under the current variable scope, instead of duplicating nodes.
  - Knobs that should vary by screen read from GSV using a small Python expression, or are updated via a `knobChanged` callback when `__default__.screen` changes.

- Render Context Enforcement
  - Global `nuke.addBeforeRender()` callback inspects `nuke.thisNode()` (Write). If a custom `assigned_screen` knob exists, it resolves that screen, sets Root selector `__default__.screen`, and pushes any project settings (format/fps/range) from the target screen group. Restore on `nuke.addAfterRender()`.

## Data Model (GSV layout)

- Root `Gsv_Knob` (`nuke.root()['gsv']`)
  - `__default__.screen` (List): current screen name; options reflect all screens
  - `Screens` set (optional index/metadata): `Screens.names_csv`, others if helpful
- Per screen VariableGroup: e.g. `screen_Moxy`
  - `__default__.format_name` (String), `width`, `height`, `pixel_aspect` (String/Integer)
  - `__default__.fps`, `frame_start`, `frame_end`
  - `__default__.write_root` (root path for outputs)
  - `Overrides` set for general overrides, e.g. `Overrides.<node>.<knob>`

Note: All GSV values are strings; knobs typically accept string inputs and parse types as needed.

## Feature 1 — Screens Panel

- UX Scope
  - Add/remove/rename screens quickly (comma‑separated input and inline edits)
  - Edit per‑screen properties (format, fps, frame range, output root)
  - Build/refresh the VariableGroups and the Root selector (List options)
  - Create/update an optional “ScreenSwitch” preview Group hooked to the DAG

- Backed by official APIs
  - Create/maintain Root list: `setDataType('__default__.screen', nuke.gsv.DataType.List)`, `setListOptions('__default__.screen', screens)`
  - Create/maintain VariableGroups: `nuke.nodes.VariableGroup(name=...)`; write values with the group’s own `['gsv']`
  - Persist favorites: `setFavorite(path, True)` for commonly tweaked vars

- Implementation Notes
  - Widget: Qt + `nukescripts.panels.registerWidgetAsPanel` for a dockable panel
  - Actions:
    - Parse input list → normalize unique screen names
    - Ensure a VariableGroup per screen; add/update per‑screen GSVs
    - Update Root `__default__.screen` list options and default
    - Optionally emit a “ScreenSwitch” group: map `screen` → `Switch.which`

- Minimal Code Sketch
  - Root list setup:
    - `gsv = nuke.root()['gsv']`
    - `gsv.setDataType('__default__.screen', nuke.gsv.DataType.List)`
    - `gsv.setListOptions('__default__.screen', ['Moxy','Godzilla','NYD400'])`
    - `gsv.setGsvValue('__default__.screen', 'Moxy')`
  - Per screen group creation:
    - `grp = nuke.nodes.VariableGroup(name='screen_Moxy')`
    - `grp['gsv'].setGsvValue('__default__.format_name', 'moxy_fmt')` …

## Feature 2 — Per‑Screen Overrides on Any Node

- Options
  - Expression‑driven: set a knob expression to fetch from GSV for the current variable context.
    - Example expression (Python): `python {nuke.root()['gsv'].getGsvValue('screen_Moxy.__default__.my_knob')}`
    - For automatic context: reference the nearest group’s `gsv` when feasible, or update via callbacks when `screen` changes.
  - Callback‑driven: on `KnobChanged` of Root `__default__.screen` update selected knobs with the GSV values for that screen.

- Helper Tooling
  - “Add Per‑Screen Override” command: for the selected node and chosen knobs, create `Overrides.<node>.<knob>` GSV entries inside each screen’s VariableGroup and either:
    - inject expressions into the knobs, or
    - register a `KnobChanged` to push values on screen change

- API Touchpoints
  - Read/write override values: `group['gsv'].setGsvValue('Overrides.Node.knob', '…')`
  - Inject expressions: `node[kn].setExpression("python {…getGsvValue('Overrides.Node.knob')} ")`
  - Update on change: `nuke.addKnobChanged(handler, nodeClass='Root')` and check for changes to Root `gsv`/screen

- Practical Guidance
  - Prefer expressions for deterministic dependency and less global state
  - Use consistent naming for override paths; avoid spaces in node names or sanitize keys

## Feature 3 — Pre‑Render Hook for Screen Assignment

- Behavior
  - Each Write node (or a Group containing Writes) can have a `assigned_screen` Pulldown knob populated from the Root selector’s list options.
  - Global `nuke.addBeforeRender()` callback:
    - Resolve `nuke.thisNode()`; read `assigned_screen` (fallback to current Root `__default__.screen`)
    - Set Root `__default__.screen` to the assigned value (so any preview switch and expressions align)
    - Apply project settings from the corresponding screen group’s `Gsv_Knob` (format/fps/first/last)
  - `nuke.addAfterRender()` restores previous Root values to keep the UI state consistent

- Implementation Sketch
  - Assignment knob: `nuke.Pulldown_Knob('assigned_screen', 'Assigned Screen', 'Moxy Godzilla NYD400')`
  - Populate choices: `gsv.getListOptions('__default__.screen')`
  - Before render:
    - Capture prev context (root format/fps/range and current screen)
    - Lookup screen group, pull its GSVs via `group['gsv'].getGsvValue('__default__.format_name')`, etc.
    - `nuke.addFormat()` missing formats; set root knobs accordingly
  - After render: restore captured values

## DAG Wiring Patterns

- Preview ScreenSwitch
  - Single Group with `Switch` to route to the chosen screen for interactive viewing; not required for farm renders.

- Per‑Screen Subgraphs
  - Keep screen‑specific nodes under their respective `VariableGroup`s when you truly need “different nodes per screen”
  - Shared nodes upstream can still reference per‑screen GSVs for configurable behavior

## Edge Cases & Safeguards

- Missing screen/group: fail gracefully and warn via `nuke.error()`
- Format creation: guard `nuke.addFormat()` with existence checks
- Name changes: `renameGsvSet()` and update any stored paths/expressions
- Serialization: use `Gsv_Knob.setValue()`/`value()` to load/save screen sets in bulk if needed

## File Structure (proposed)

- `nuke_tools/screens_manager.py` — Qt panel to manage screens, formats, fps, ranges, “build switch”, and bulk edit
- `nuke_tools/gsv_utils.py` — Thin wrapper over `Gsv_Knob` for typed gets/sets and common paths
- `nuke_tools/overrides.py` — Commands to bind knobs to GSV overrides and manage expressions
- `nuke_tools/render_hooks.py` — `addBeforeRender`/`addAfterRender` handlers + utilities
- `menu.py` — Menu items and `registerWidgetAsPanel` integration

## Milestones

1) GSV + VariableGroup scaffolding: root selector + per‑screen groups
2) Screens Manager panel: add/edit/remove + list options wiring
3) Preview ScreenSwitch helper group
4) Overrides tooling for selected nodes/knobs
5) Pre‑render hooks (assignment + context enforcement + restore)
6) Polish + edge cases + docstrings and brief README

## Validation Plan

- Unit‑style checks (interactive):
  - Root `__default__.screen` exists, list options match panel
  - Screen groups exist and contain expected GSVs
  - ScreenSwitch “which” changes when root `screen` changes
  - Overrides: changing `screen` updates visible knob values (expression or handler)
  - Pre‑render: assign different screens to two Writes; each render picks the correct format/range and output path

- Non‑Goals (initial):
  - Farm integrations beyond calling `execute()`; we’ll expose hooks to integrate later
  - Complex conflict resolution UI when nodes exist in multiple screen groups

## Notes on Using the Official API

- GSV pathing: use dot‑separated paths; with VariableGroups the path is `group_hierarchy.set.var`. When addressing via a group’s own `['gsv']`, paths are relative to that group.
- Lists: make `__default__.screen` a `List` data type with `setListOptions()` so the Variables panel shows a proper dropdown.
- Callbacks: prefer `addBeforeRender`/`addAfterRender` over per‑node `beforeRender` strings to centralize logic and avoid duplication.
- Expressions: Python expressions in knobs are supported; use sparingly for performance and keep them short.

---

This document is the plan for building the requested tools on top of Nuke 16’s GSV/VariableGroup multi‑shot APIs, minimizing custom logic while providing a friendly UI and reliable render‑time behavior.

