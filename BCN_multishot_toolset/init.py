"""Nuke startup (init.py) for BCN multishot toolset.

Non-GUI startup tasks only. Use `menu.py` for UI registration.
"""

import nuke  # type: ignore

# Ensure this package folder is on the plugin path for nested resources if needed.
# nuke.pluginAddPath('BCN_multishot_toolset')  # Not strictly required if NUKE_PATH is set

