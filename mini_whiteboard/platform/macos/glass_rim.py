"""A narrow band of live AppKit glass samples below the Qt artwork."""


class GlassRim:
    def __init__(self, parent, base, *, compact=False):
        import AppKit
        import Quartz

        # Inset moves the native sampling edge. Both board samples share one
        # rounded band in window coordinates, so their colours overlap on a
        # still field and separate where a bright line moves under the rim.
        if compact:
            self.start, self.width = 0.9, 2.4
            layers = ((0.9, 0.14, (0.20, 0.60, 0.80, 0.52)),)
        else:
            self.start, self.width = 3.0, 3.3
            layers = ((2.6, 0.93, (0.99, 0.49, 0.015, 0.91)),
                      (-3.0, 0.49, (0.03, 0.42, 0.88, 0.93)))

        self.samples = []
        self.key = None
        below = base
        try:
            for inset, opacity, tint in layers:
                view = AppKit.NSGlassEffectView.alloc().initWithFrame_(base.frame())
                view.setStyle_(AppKit.NSGlassEffectViewStyleClear)
                view.setAppearance_(base.appearance())
                view.setTintColor_(AppKit.NSColor.colorWithSRGBRed_green_blue_alpha_(*tint))
                view.setAlphaValue_(opacity)
                view.setWantsLayer_(True)
                mask = Quartz.CAShapeLayer.layer()
                mask.setFillRule_(Quartz.kCAFillRuleEvenOdd)
                view.layer().setMask_(mask)
                self.samples.append((view, mask, inset))
                parent.addSubview_positioned_relativeTo_(view, AppKit.NSWindowAbove, below)
                below = view
        except Exception:
            self.close()
            raise

    def resize(self, frame, radius):
        import Quartz

        x, y = frame.origin.x, frame.origin.y
        width, height = frame.size.width, frame.size.height
        key = (x, y, width, height, radius)
        if key == self.key:
            return
        too_small = min(width, height) <= 2 * (self.start + self.width) or radius < 5
        Quartz.CATransaction.begin()
        try:
            Quartz.CATransaction.setDisableActions_(True)
            for view, mask, inset in self.samples:
                view.setHidden_(too_small)
                if too_small:
                    continue
                view.setFrame_(((x + inset, y + inset), (width - 2 * inset, height - 2 * inset)))
                view.setCornerRadius_(max(0, radius - inset))
                ring = Quartz.CGPathCreateMutable()
                for d in (self.start, self.start + self.width):
                    rect = ((d - inset, d - inset), (width - 2 * d, height - 2 * d))
                    r = max(0, radius - d)
                    outline = Quartz.CGPathCreateWithRoundedRect(rect, r, r, None)
                    Quartz.CGPathAddPath(ring, None, outline)
                mask.setFrame_(view.bounds())
                mask.setPath_(ring)
            self.key = key
        finally:
            Quartz.CATransaction.commit()

    def close(self):
        for view, _mask, _inset in reversed(self.samples):
            view.removeFromSuperview()
        self.samples.clear()
        self.key = None
