"""Shared compact tray/status-item menu; native lifetime belongs to Runtime."""
from PySide6.QtGui import QActionGroup
from . import APP_VERSION
from .platform.base import CREATE_HOTKEY, CAPTURE_HOTKEY, HIDE_HOTKEY
from .shortcuts import ShortcutPolicy


def rebuild_menu(controller):
    c, menu = controller, controller.menu
    menu.clear()
    menu.add_heading(f"Mini Whiteboard {APP_VERSION}")
    for label, key in (("New Whiteboard", "W"), ("Screenshot to Whiteboard", "S")):
        shortcut = c.platform.shortcuts.global_label(key)
        identifier = CREATE_HOTKEY if key == 'W' else CAPTURE_HOTKEY
        available = identifier in c.hotkeys.registered
        menu.addAction(f"{label} · hold {shortcut}" + ('' if available else ' · unavailable'),
                       lambda checked=False, s=shortcut, ready=available: c.notify(
                           f"Point at the first corner, hold {s}, move, then release.") if ready else c.show_hotkey_settings())
    if c.placement.state.active or c.capture.active:
        def cancel():
            c.placement.cancel()
            c.capture.cancel()
        menu.addAction("Cancel placement / screenshot", cancel)
    menu.addSeparator()
    label = "Restore All" if c.hidden_batch else "Hide All"
    menu.addAction(f"{label} · {c.platform.shortcuts.global_label('H')}" +
                   ('' if HIDE_HOTKEY in c.hotkeys.registered else ' · shortcut unavailable'), c.toggle_visibility)
    boards_menu = menu.addMenu("Whiteboards")
    if c.boards:
        for board in c.boards:
            label = board.name + (" (minimised)" if not board.isVisible() else "")
            boards_menu.addAction(label, lambda checked=False, b=board: c.restore_board(b))
    else:
        boards_menu.addAction("No whiteboards").setEnabled(False)
    menu.addSeparator()
    settings = menu.addMenu('Settings')
    settings.addAction('Hotkeys…', c.show_hotkey_settings)
    appearance = menu.addMenu('Appearance')
    group = QActionGroup(appearance)
    group.setExclusive(True)
    for theme in ('White', 'Glass'):
        action = appearance.addAction(theme)
        action.setCheckable(True)
        action.setChecked(c.preferences.theme == theme)
        group.addAction(action)
        action.triggered.connect(lambda checked=False, value=theme: c.preferences.set_theme(value))
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
            action = presets.addAction(policy.global_label("W / S / H"))
            action.setCheckable(True)
            from .hotkey_config import defaults
            action.setChecked(c.preferences.hotkey_configuration(True) == defaults(True, preset))
            action.triggered.connect(lambda checked=False, p=preset: c.change_shortcut_preset(p))
    else:
        choices = menu.addMenu('Hide All shortcut')
        group = QActionGroup(choices)
        group.setExclusive(True)
        for choice in ('default', 'shift'):
            action = choices.addAction(ShortcutPolicy(hide_shortcut=choice).global_label('H'))
            action.setCheckable(True)
            from .hotkey_config import defaults
            action.setChecked(c.preferences.hotkey_configuration().hide == defaults(hide=choice).hide)
            group.addAction(action)
            action.triggered.connect(lambda checked=False, value=choice: c.change_hide_shortcut(value))
    menu.addSeparator()
    state = c.platform.login.state()
    login = menu.addAction('Open at login')
    login.setCheckable(True)
    login.setChecked(state.enabled)
    login.setEnabled(state.available)
    login.setToolTip(state.detail or 'Launch quietly in the tray or menu bar when you sign in.')
    login.triggered.connect(c.change_login)
    if state.detail:
        detail = menu.addAction(state.detail)
        detail.setEnabled(False)
    if state.approval_required:
        menu.addAction('Open startup settings…', c.open_login_settings)
    if state.registered and not state.enabled:
        menu.addAction('Turn off Open at login', lambda: c.change_login(False))
    menu.addSeparator()
    menu.addAction("Keyboard shortcuts", c.show_shortcuts)
    menu.addAction("About Mini Whiteboard", c.show_about)
    if not {CREATE_HOTKEY, CAPTURE_HOTKEY, HIDE_HOTKEY}.issubset(c.hotkeys.registered):
        menu.addAction("Retry global shortcut", c.retry_hotkey)
    menu.addSeparator()
    menu.addAction(c.platform.shortcuts.quit_label, c.app.quit)
