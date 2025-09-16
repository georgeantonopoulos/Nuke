# Nuke 16 Multi‑Shot Tools — Agent Plan (AGENTS.md)

## Goals

- Screens Panel: Add/edit a list of “screens” (e.g., `Moxy, Godzilla, NYD400`) and create the variables + a preview switch to fluidly toggle between them.
- Per‑Screen Overrides: Let artists set overrides on any node/knob, specific to each screen.
- Write Integration: Provide a one-click way to wrap a Write node inside a VariableGroup so artists can choose the active screen using Nuke’s native multi-shot UI.
- Constraint: Leverage Nuke 16’s multi-shot/Graph Scope Variables (GSV) and VariableGroup APIs; avoid reinventing behavior that the API provides.

## Current Implementation Snapshot (2025‑09‑16)

- Root selector variable is `__default__.screens` (plural) of type List, not `__default__.screen`.
- Screens Manager panel manages the `__default__.screens` options and default, ensures per-screen GSV Sets at root, and can optionally create a `VariableGroup` per screen and a `VariableSwitch` preview node.
- Write integration is now handled by wrapping a selected Write node (or a publishable Group) inside a `VariableGroup` via `render_hooks.encapsulate_write_with_variable_group()`. The helper automatically exposes every relevant knob on the VariableGroup interface using `Link_Knob`s, sets the wrapper label to the simple expression `[value gsv]`, and keeps the internal node named for clarity, so artists can switch screens directly on the VariableGroup without any injected scripts or callbacks.
- Menu wiring provides a “Wrap Node in Variable Group” command under `BCN Multishot`, keeping the workflow accessible to artists who are new to multi-shot setups.

## Key Nuke 16 APIs To Use

- Graph Scope Variables (GSV): root knob `nuke.root()['gsv']` is a `nuke.Gsv_Knob`.
  - Manage sets/vars: `Gsv_Knob.addGsvSet()`, `setGsvValue()`, `getGsvValue()`, `setValue()`, `value()`, `removeGsvSet()`, `removeGsv()`, `renameGsvSet()`, `renameGsv()`
  - Data types and options: `Gsv_Knob.setDataType(path, nuke.gsv.DataType.List)`, `Gsv_Knob.setListOptions(path, options)`
  - Variables Panel favorites/labels/tooltips: `setFavorite()`, `setLabel()`, `setTooltip()`
  - Docs: “Graph Scope Variables / Multi‑shot Set‑up” and `nuke.Gsv_Knob`
- Variable Groups: contextual scoping and overriding across the DAG
  - Create nodes: `nuke.nodes.VariableGroup(name='…')` or `nuke.collapseToVariableGroup()`
  - Paths extend with group names: `variable_group...variable_set.variable_name`
- VariableGroup helpers: `nuke.collapseToVariableGroup()`, `Link_Knob.makeLink()`, and the VariableGroup node UI for selecting variables
- Panels/UI: `nukescripts.PythonPanel`, `nukescripts.panels.registerWidgetAsPanel`, or simple `nuke.Panel`
- Project settings: `nuke.root()['format']`, `['fps']`, `['first_frame']`, `['last_frame']`, `nuke.addFormat()`

References: See Nuke 16 Python docs (notably: `gsv.html`, `_autosummary/nuke.Gsv_Knob.html`, `_autosummary/nuke.collapseToVariableGroup.html`, `callbacks.html`, `custom_panels.html`, `_autosummary/nukescripts.panels.registerWidgetAsPanel.html`).

Additional references:
- Multishot variables (Graph Scope Variables): https://learn.foundry.com/nuke/content/comp_environment/multishot/multishot_variables.html
- Using VariableSwitch: https://learn.foundry.com/nuke/content/comp_environment/multishot/using_variableswitch.html
- Using Link nodes: https://learn.foundry.com/nuke/content/comp_environment/multishot/using_link_nodes.html
- Local docs: see `Nuke16_docs/_sources/gsv.rst.txt` (sections “The Gsv_Knob” and VariableGroups pathing)

## Architecture

- Root‑Level Selector
  - `__default__.screens`: A List‑type GSV on the Root `Gsv_Knob` with options = screen names. It appears in the Variables panel, providing a canonical current‑screen selector.
  - Optional global toggles (favorites): add common switches (e.g., `__default__.use_ocio`, `__default__.render_quality`) and mark as favorites for quick access.

- VariableGroups per Screen
  - For each screen name, create a `VariableGroup` named e.g. `screen_Moxy`, `screen_Godzilla`, etc.
  - Within each screen group’s `Gsv_Knob`, store screen‑specific defaults in `__default__` (format/size/fps/range/paths) and any per‑screen override buckets (e.g., `Overrides` set).
  - Inheritance/overrides: Parent groups can hold shared defaults; child screen groups override only what differs.
  - Current code also ensures a root‑level GSV Set per screen (e.g. `Moxy`, `Godzilla`) for easy `%Set.Var` references in string knobs.

- Preview “Variable Switch”
  - Prefer a `VariableSwitch` node driven by the `__default__.screens` GSV to control which input is active without custom callbacks.
  - Fallback: provide a helper Group “ScreenSwitch” with a plain `Switch` whose `which` is driven by a short expression that references the GSV. Avoid generic `knobChanged` callbacks for this.

- Per‑Screen Node Overrides
  - Store override values in GSVs, keyed under the current variable scope, instead of duplicating nodes.
  - Knobs that should vary by screen should preferably read from GSV using a short expression. Where node mirroring is needed, use Link nodes and override only the differing knobs per screen.

- Render Context Enforcement
  - Planned: a centralized `nuke.addBeforeRender()`/`nuke.addAfterRender()` would set `__default__.screens` and push project settings from the target screen prior to rendering.
  - Current code: Write nodes are wrapped inside VariableGroups so the screen selector lives on the wrapper and drives evaluation without additional scripting.

## Data Model (GSV layout)

- Root `Gsv_Knob` (`nuke.root()['gsv']`)
  - `__default__.screens` (List): current screen name; options reflect all screens
  - `Screens` set (optional index/metadata): `Screens.names_csv`, others if helpful
- Per screen VariableGroup: e.g. `screen_Moxy`
  - `__default__.format_name` (String), `width`, `height`, `pixel_aspect` (String/Integer)
  - `__default__.fps`, `frame_start`, `frame_end`
  - `__default__.write_root` (root path for outputs)
  - `Overrides` set for general overrides, e.g. `Overrides.<node>.<knob>`
  - Additionally, a root Set per screen (e.g. `Moxy`, `Godzilla`) for `%Set.Var` access.

Note: All GSV values are strings; knobs typically accept string inputs and parse types as needed.

## Feature 1 — Screens Panel

- UX Scope
  - Add/remove/rename screens quickly (comma‑separated input and inline edits)
  - Edit per‑screen properties (format, fps, frame range, output root)
  - Build/refresh the VariableGroups and the Root selector (List options)
  - Create/update an optional “ScreenSwitch” preview Group hooked to the DAG

- Backed by official APIs
  - Create/maintain Root list: `setDataType('__default__.screens', nuke.gsv.DataType.List)`, `setListOptions('__default__.screens', screens)`
  - Create/maintain VariableGroups: `nuke.nodes.VariableGroup(name=...)`; write values with the group’s own `['gsv']`
  - Persist favorites: `setFavorite(path, True)` for commonly tweaked vars

- Implementation Notes
  - Widget: Qt + `nukescripts.panels.registerWidgetAsPanel` for a dockable panel
  - Actions:
    - Parse input list → normalize unique screen names
    - Ensure a VariableGroup per screen; add/update per‑screen GSVs
    - Update Root `__default__.screens` list options and default
    - Optionally emit a “ScreenSwitch” group: map `screen` → `Switch.which`

- Minimal Code Sketch
  - Root list setup:
    - `gsv = nuke.root()['gsv']`
    - `gsv.setDataType('__default__.screens', nuke.gsv.DataType.List)`
    - `gsv.setListOptions('__default__.screens', ['Moxy','Godzilla','NYD400'])`
    - `gsv.setGsvValue('__default__.screens', 'Moxy')`
  - Per screen group creation:
    - `grp = nuke.nodes.VariableGroup(name='screen_Moxy')`
    - `grp['gsv'].setGsvValue('__default__.format_name', 'moxy_fmt')` …

## Feature 2 — Per‑Screen Overrides on Any Node

- Options
  - Expression‑driven: set a knob expression to fetch from GSV for the current variable context.
    - Example expression (Python): `python {g=nuke.root()['gsv']; s=g.getGsvValue('__default__.screens'); g.getGsvValue(s + '.my_knob')}`
    - For automatic context: reference the nearest group’s `gsv` when feasible.
  - Link‑node‑driven: for repeated structures, use Link nodes to mirror a source node and override only per‑screen differences (reduces or eliminates the need for callbacks).
  - GSV‑change callback (last resort): if an imperative push is absolutely required, respond to GSV changes with `nuke.callbacks.onGsvSetChanged()` when `__default__.screen` changes.

- Helper Tooling
  - “Add Per‑Screen Override” command: for the selected node and chosen knobs, create `Overrides.<node>.<knob>` GSV entries inside each screen’s VariableGroup and either:
    - inject expressions into the knobs, or
    - register a `KnobChanged` to push values on screen change

- API Touchpoints
  - Read/write override values: `group['gsv'].setGsvValue('Overrides.Node.knob', '…')`
  - Inject expressions: `node[kn].setExpression("python {…getGsvValue('Overrides.Node.knob')}")`
  - Update on change (only if required): use `nuke.callbacks.onGsvSetChanged()` to react to changes in `__default__.screen` rather than a generic `addKnobChanged`.

- Practical Guidance
  - Prefer expressions for deterministic dependency and less global state
  - Use consistent naming for override paths; avoid spaces in node names or sanitize keys

## Feature 3 — Write VariableGroup Wrapper

- Behavior
  - Artists select a Write node or a publish-ready Group (one that exposes a `publish_instance` knob) and trigger “Wrap Node in Variable Group” from the BCN Multishot menu.
  - The tool collapses the selection into a `VariableGroup`, renames the wrapper, links every exposed knob to the group UI with `Link_Knob`s, and sets the label to `[value gsv]` so the active screen is visible using Nuke's own evaluation. Tabs from the original node are preserved.
  - Because VariableGroup nodes already expose the variable selector UI, artists can pick the active screen directly on the wrapper node. No extra callbacks or render-time scripts are required.

  - Use `nuke.collapseToVariableGroup()` on the selected node, wrapping it in a VariableGroup within a single undo step.
  - Locate the internal node (Write preferred, otherwise a node carrying `publish_instance`) and iterate over its knobs.
  - For each `Tab_Knob`, add a matching tab to the VariableGroup; for other knobs, create a `Link_Knob` pointing back to the internal node knob.
  - Skip housekeeping knobs already provided by the VariableGroup (`name`, `xpos`, etc.) to avoid duplicates on the interface.
  - Set the wrapper's label to the lightweight TCL expression `[value gsv]` so the active scope is visible, and open the VariableGroup’s properties so artists immediately see the familiar UI alongside the Variable selector.

## DAG Wiring Patterns

- Preview ScreenSwitch
  - The panel's "Create VariableSwitch" button now instantiates a fresh `VariableSwitch` plus dedicated Dots each time it is pressed; artists can spawn multiple preview switches without reusing prior nodes.
  - Prefer `VariableSwitch` to route to the chosen screen based on the `__default__.screens` GSV; not required for farm renders.
  - If `VariableSwitch` is not appropriate, a Group with a plain `Switch` is acceptable but should be driven by an expression, not a callback.

- Per‑Screen Subgraphs
  - Keep screen‑specific nodes under their respective `VariableGroup`s when you truly need “different nodes per screen”
  - Shared nodes upstream can still reference per‑screen GSVs for configurable behavior

- Link Nodes
  - Use Link nodes to mirror shared nodes across screens while maintaining a single source of truth; override only the necessary knobs in each context. This often replaces callback‑based synchronization.

## Edge Cases & Safeguards

- Missing screen/group: fail gracefully and warn via `nuke.error()`
- Format creation: guard `nuke.addFormat()` with existence checks
- Name changes: `renameGsvSet()` and update any stored paths/expressions
- Serialization: use `Gsv_Knob.setValue()`/`value()` to load/save screen sets in bulk if needed

## File Structure (proposed)

- `nuke_tools/screens_manager.py` — Qt panel to manage screens, formats, fps, ranges, “build switch”, and bulk edit
- `nuke_tools/gsv_utils.py` — Thin wrapper over `Gsv_Knob` for typed gets/sets and common paths
- `nuke_tools/overrides.py` — Commands to bind knobs to GSV overrides and manage expressions
- `nuke_tools/render_hooks.py` — VariableGroup wrapper helper for Write nodes
- `menu.py` — Menu items and `registerWidgetAsPanel` integration

## Milestones

1) GSV + VariableGroup scaffolding: root selector + per‑screen groups
2) Screens Manager panel: add/edit/remove + list options wiring
3) Preview ScreenSwitch helper group
4) Overrides tooling for selected nodes/knobs
5) Write VariableGroup wrapper + knob exposure polish
6) Polish + edge cases + docstrings and brief README

## Validation Plan

- Unit‑style checks (interactive):
  - Root `__default__.screen` exists, list options match panel
  - Screen groups exist and contain expected GSVs
  - ScreenSwitch “which” changes when root `screen` changes
- Overrides: changing `screen` updates visible knob values (expression or handler)
  - Write wrappers: wrap a Write and confirm the VariableGroup exposes all knobs and switches screens correctly

- Non‑Goals (initial):
  - Farm integrations beyond calling `execute()`; we’ll expose hooks to integrate later
  - Complex conflict resolution UI when nodes exist in multiple screen groups

## Notes on Using the Official API

- GSV pathing: use dot‑separated paths; with VariableGroups the path is `group_hierarchy.set.var`. When addressing via a group’s own `['gsv']`, paths are relative to that group.
- Lists: make `__default__.screen` a `List` data type with `setListOptions()` so the Variables panel shows a proper dropdown.
- Variable selection: lean on VariableGroup UI for switching; avoid bespoke callbacks where built-in nodes already handle scope changes.
- Expressions: Python expressions in knobs are supported; use sparingly for performance and keep them short.

---

This document is the plan for building the requested tools on top of Nuke 16’s GSV/VariableGroup multi‑shot APIs, minimizing custom logic while providing a friendly UI and reliable render‑time behavior.
