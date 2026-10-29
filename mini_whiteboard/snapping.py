"""Bounds-only smart targets captured once per gesture; optional persistent prefs."""
from bisect import bisect_left, bisect_right
from dataclasses import dataclass
import math

from PySide6.QtCore import QObject, QRectF, QSettings, Signal
from .settings import GRID_SIZE, SNAP_THRESHOLD
from .transforms import translation, resize_transform
from .document import ImageObject


class SnapPreferences(QObject):
    changed = Signal()
    appearance_changed = Signal()

    def __init__(self, persist=False, settings=None):
        super().__init__()
        self.settings = settings if settings is not None else QSettings("MiniWhiteboard", "MiniWhiteboard") if persist else None
        self.smart_guides = self.settings.value("snap/smart", True, type=bool) if self.settings else True
        self.grid_snap = self.settings.value("snap/grid", False, type=bool) if self.settings else False
        preset = self.settings.value("shortcuts/preset", "default") if self.settings else "default"
        self.shortcut_preset = preset if preset in ("default", "alternate") else "default"
        hide = self.settings.value('shortcuts/windows_hide', 'default') if self.settings else 'default'
        self.windows_hide = hide if hide in ('default', 'shift') else 'default'
        theme = self.settings.value('appearance/theme', 'White') if self.settings else 'White'
        self.theme = theme if theme in ('White', 'Glass') else 'White'
        self.custom_hotkeys = {}
        from .hotkey_config import HotkeyConfig
        for platform in ('windows', 'mac'):
            raw = self.settings.value('shortcuts/custom_' + platform, '') if self.settings else ''
            if raw:
                try:
                    self.custom_hotkeys[platform] = HotkeyConfig.from_json(raw)
                except ValueError:
                    pass  # Invalid/external data must not prevent access to Settings.

    def hotkey_configuration(self, mac=False):
        from .hotkey_config import defaults
        return self.custom_hotkeys.get('mac' if mac else 'windows',
                                       defaults(mac, self.shortcut_preset, self.windows_hide))

    def set_hotkey_configuration(self, configuration, mac=False):
        configuration.validate()
        platform = 'mac' if mac else 'windows'
        self.custom_hotkeys[platform] = configuration
        if self.settings is not None:
            self.settings.setValue('shortcuts/custom_' + platform, configuration.to_json())
            self.settings.sync()

    def set_theme(self, theme):
        if theme not in ('White', 'Glass'):
            raise ValueError('Unknown appearance.')
        if theme == self.theme:
            return
        self.theme = theme
        if self.settings is not None:
            self.settings.setValue('appearance/theme', theme)
            self.settings.sync()
        self.appearance_changed.emit()

    def set_shortcut_preset(self, preset):
        if preset not in ("default", "alternate"):
            raise ValueError("Unknown global shortcut preset.")
        self.shortcut_preset = preset
        self.save()

    def set_windows_hide(self, choice):
        if choice not in ('default', 'shift'):
            raise ValueError('Unknown Hide All shortcut.')
        self.windows_hide = choice
        if self.settings is not None:
            self.settings.setValue('shortcuts/windows_hide', choice)
            self.settings.sync()

    def set_smart(self, enabled):
        self.smart_guides = bool(enabled)
        self.save()

    def set_grid(self, enabled):
        self.grid_snap = bool(enabled)
        self.save()

    def save(self):
        if self.settings is not None:
            self.settings.setValue("snap/smart", self.smart_guides)
            self.settings.setValue("snap/grid", self.grid_snap)
            self.settings.setValue("shortcuts/preset", self.shortcut_preset)
            self.settings.sync()
        self.changed.emit()


@dataclass(frozen=True)
class Target:
    value: float
    low: float
    high: float


class SnapTargets:
    def __init__(self, records, selected_ids, viewport):
        x, y = [], []
        def add(rect):
            x.extend(Target(v, rect.top(), rect.bottom()) for v in (rect.left(),rect.center().x(),rect.right()))
            y.extend(Target(v, rect.left(), rect.right()) for v in (rect.top(),rect.center().y(),rect.bottom()))
        add(viewport)
        nearby = viewport.adjusted(-160,-160,160,160)
        for record in records:
            if isinstance(record.obj, ImageObject) and record.obj.locked:
                continue
            if record.obj.id not in selected_ids and not record.bounds.isEmpty() and record.bounds.intersects(nearby):
                add(record.bounds)
        self.axes = tuple(tuple(sorted(axis, key=lambda t:t.value)) for axis in (x,y))
        self.values = tuple(tuple(t.value for t in axis) for axis in self.axes)

    def candidate(self, axis, values, low, high):
        best = None
        for value in values:
            start = bisect_left(self.values[axis], value-SNAP_THRESHOLD)
            end = bisect_right(self.values[axis], value+SNAP_THRESHOLD)
            for target in self.axes[axis][start:end]:
                if target.low > high+160 or target.high < low-160:
                    continue
                delta = target.value-value
                if best is None or abs(delta) < abs(best[0]):
                    best = delta, target
        return best

    @staticmethod
    def guide(axis, target, bounds):
        if axis == 0:
            return target.value, min(target.low,bounds.top()), target.value, max(target.high,bounds.bottom())
        return min(target.low,bounds.left()), target.value, max(target.high,bounds.right()), target.value

    def move(self, bounds, dx, dy, preferences, disabled=False):
        if disabled or not (preferences.smart_guides or preferences.grid_snap):
            return translation(dx,dy), ()
        proposed = bounds.translated(dx,dy)
        sources = ((proposed.left(),proposed.center().x(),proposed.right()),
                   (proposed.top(),proposed.center().y(),proposed.bottom()))
        guides, adjustments = [], []
        for axis, values in enumerate(sources):
            low, high = (proposed.top(),proposed.bottom()) if axis == 0 else (proposed.left(),proposed.right())
            candidate = self.candidate(axis, values, low, high) if preferences.smart_guides else None
            if candidate is not None:
                adjustments.append(candidate[0])
                guides.append(self.guide(axis, candidate[1], proposed))
            else:
                adjustments.append(round(values[0]/GRID_SIZE)*GRID_SIZE-values[0] if preferences.grid_snap else 0)
        return translation(dx+adjustments[0],dy+adjustments[1]), tuple(guides)

    def resize(self, frame, handle, matrix, proportional, preferences, disabled=False):
        if disabled or not (preferences.smart_guides or preferences.grid_snap):
            return matrix, ()
        point = matrix.map(frame.handle(handle))
        anchor = frame.handle((handle+4)%8)
        vector = point[0]-anchor[0], point[1]-anchor[1]
        options = []
        for axis in (0,1):
            if abs(vector[axis]) < 1e-8:
                continue
            candidate = self.candidate(axis, (point[axis],), point[1-axis], point[1-axis]) if preferences.smart_guides else None
            if candidate:
                delta, target = candidate
                priority = 0
            elif preferences.grid_snap:
                delta = round(point[axis]/GRID_SIZE)*GRID_SIZE-point[axis]
                target, priority = None, 1
            else:
                continue
            ratio = 1+delta/vector[axis]
            if ratio <= 0 or not math.isfinite(ratio):
                continue
            options.append((priority, abs(ratio-1)*math.hypot(*vector), axis, ratio, target))
        if not options:
            return matrix, ()
        # Constrained handles must stay on their resize ray. Snap the closest
        # reachable axis rather than breaking image/text proportions to hit both.
        _, _, axis, ratio, target = min(options, key=lambda o:o[:2])
        corrected = anchor[0]+vector[0]*ratio, anchor[1]+vector[1]*ratio
        result = resize_transform(frame, handle, frame.handle(handle), corrected, proportional)
        final_point = result.map(frame.handle(handle))
        guides = ()
        if target is not None and abs(final_point[axis]-target.value) < .01:
            r = QRectF(rendering_point(anchor), rendering_point(final_point)).normalized()
            guides = (self.guide(axis,target,r),)
        return result, guides


def rendering_point(p):
    from PySide6.QtCore import QPointF
    return QPointF(*p)
