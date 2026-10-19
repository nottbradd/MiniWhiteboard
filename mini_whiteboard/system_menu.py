"""Shared compact tray/status-item menu; native lifetime belongs to Runtime."""
from . import APP_VERSION
from .platform.base import CREATE_HOTKEY, CAPTURE_HOTKEY
from .shortcuts import ShortcutPolicy


def rebuild_menu(controller):
    c, menu = controller, controller.menu
    menu.clear()
    menu.addAction(f"Mini Whiteboard {APP_VERSION}").setEnabled(False)
    for label, key in (("New Whiteboard", "W"), ("Screenshot to Whiteboard", "S")):
        shortcut = c.platform.shortcuts.global_label(key)
        menu.addAction(f"{label} · hold {shortcut}",
                       lambda checked=False, s=shortcut: c.notify(f"Point at the first corner, hold {s}, move, then release."))
    if c.placement.state.active or c.capture.active:
        def cancel():
            c.placement.cancel()
            c.capture.cancel()
        menu.addAction("Cancel placement / screenshot", cancel)
    menu.addSeparator()
    boards_menu = menu.addMenu("Whiteboards")
    if c.boards:
        for board in c.boards:
            label = board.name + (" (minimised)" if not board.isVisible() else "")
            boards_menu.addAction(label, lambda checked=False, b=board: c.restore_board(b))
    else:
        boards_menu.addAction("No whiteboards").setEnabled(False)
    menu.addSeparator()
    snap = menu.addMenu("Snap & Guides")
    for label, enabled, callback in (("Smart Guides", c.preferences.smart_guides, c.preferences.set_smart),
                                     ("Grid Snap", c.preferences.grid_snap, c.preferences.set_grid)):
        action = snap.addAction(label)
        action.setCheckable(True)
        action.setChecked(enabled)
        action.toggled.connect(callback)
    if c.platform.shortcuts.mac:
        presets = menu.addMenu("Global shortcuts")
        for preset in ("default", "alternate"):
            policy = ShortcutPolicy(mac=True, preset=preset)
            action = presets.addAction(policy.global_label("W / S"))
            action.setCheckable(True)
            action.setChecked(c.preferences.shortcut_preset == preset)
            action.triggered.connect(lambda checked=False, p=preset: c.change_shortcut_preset(p))
    menu.addSeparator()
    menu.addAction("Keyboard shortcuts", c.show_shortcuts)
    menu.addAction("About Mini Whiteboard", c.show_about)
    if not {CREATE_HOTKEY, CAPTURE_HOTKEY}.issubset(c.hotkeys.registered):
        menu.addAction("Retry global shortcut", c.retry_hotkey)
    menu.addSeparator()
    menu.addAction(c.platform.shortcuts.quit_label, c.app.quit)
