import nuke
nuke.pluginAddPath('./nuke_tools')
try:
    from render_hooks import install_render_callbacks  # type: ignore
    install_render_callbacks()
except Exception:
    pass