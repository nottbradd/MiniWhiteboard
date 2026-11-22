"""Check screenshot pixels and board visibility on an owned physical test scene."""
from dataclasses import replace
import json
from pathlib import Path
import sys

from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from mini_whiteboard.appearance import DisplayPolicy, LIQUID, THEMES
from mini_whiteboard.app import WhiteboardApplication
from mini_whiteboard.clipboard import mime_data, rendered_image
from mini_whiteboard.geometry import Rect
from mini_whiteboard.images import decoded
from mini_whiteboard.platform import get_platform
from mini_whiteboard.platform.windows import native
from mini_whiteboard.snapping import SnapPreferences
from tests.fake_platform import FakeHotkeys
from .glass_optics import RemoteBackground


def check(folder):
    folder.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    bg = RemoteBackground()
    prefs = SnapPreferences()
    services = replace(get_platform(), hotkey_factory=FakeHotkeys)
    controller = WhiteboardApplication(app, prefs, platform=services)
    controller.tray.hide()
    checks = {}
    original_policy = services.desktop.display_policy
    try:
        scale = bg.ratio
        x, y = bg.origin.toTuple()
        region = Rect(*(round(v*scale) for v in (x + 68, y + 68, 420, 220)))

        def frame():
            QTest.qWait(160)
            return native.capture_rect(region).convertToFormat(QImage.Format.Format_RGB32)

        bg.palette_name, bg.phase = 'busy', 0
        bg.update()
        original = frame()
        original.save(str(folder / 'original.png'))
        controller.create_screenshot_board(region, original)
        image_board = controller.boards[-1]
        objects = image_board.canvas.document.objects
        checks['stored source pixels'] = decoded(objects[0].png).convertToFormat(original.format()) == original
        flattened = rendered_image(objects)
        if scale == 1:
            source_pixels = flattened.copy(2, 2, original.width(), original.height())
            checks['entire screenshot in artwork export'] = source_pixels.convertToFormat(original.format()) == original

        bg.palette_name, bg.phase = 'reel', 12
        bg.update()
        interior = original.rect().adjusted(14, 14, -14, -14)
        for theme in THEMES:
            prefs.set_theme(theme)
            slug = theme.lower().split()[0]
            frame().save(str(folder / f'{slug}-controls.png'))
            controller.capture.chrome_suspended.emit(True)
            output = frame()
            output.save(str(folder / f'{slug}-capture.png'))
            checks[f'{theme} clean desktop capture'] = output.copy(interior) == original.copy(interior)
            checks[f'{theme} artwork and clipboard pixels'] = (
                rendered_image(objects) == flattened and mime_data(objects, 'review').imageData() == flattened
            )
            checks[f'{theme} screenshot body has no material host'] = not image_board.native_glass
            controller.capture.chrome_suspended.emit(False)
        board = controller.create_board(region)
        prefs.set_theme(LIQUID)
        checks['normal board has reported finish'] = board.native_glass == services.desktop.available_finish(
            LIQUID, board.display_policy, board.screen()
        )
        image_board.minimize_to_tray()
        controller.toggle_visibility()
        checks['Hide All releases native host'] = not board.isVisible() and not getattr(board, '_backdrop', None)
        controller.toggle_visibility()
        checks['Restore All restores eligible boards only'] = board.isVisible() and not image_board.isVisible()
        recover_to = board.native_glass or 'Opaque'
        services.desktop.display_policy = lambda: DisplayPolicy(transparency=False, motion=False, high_contrast=True)
        board.refresh_appearance()
        checks['opaque policy keeps saved Liquid'] = not board.native_glass and prefs.theme == LIQUID
        services.desktop.display_policy = original_policy
        board.refresh_appearance()
        checks['appearance recovers on the open board'] = (board.native_glass or 'Opaque') == recover_to
    finally:
        services.desktop.display_policy = original_policy
        controller.cleanup()
        bg.close()
        app.processEvents()
        (folder / 'content.json').write_text(json.dumps(checks, indent=2), encoding='utf-8')
    if not all(checks.values()):
        raise RuntimeError(str([name for name, passed in checks.items() if not passed]))


if __name__ == '__main__':
    check(Path(sys.argv[1]))
