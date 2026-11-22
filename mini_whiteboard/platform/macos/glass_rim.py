"""A faint channel separation from a second, inset native glass sample."""


class GlassRim:
    def __init__(self, parent, base):
        import AppKit
        import Quartz
        self.view = AppKit.NSGlassEffectView.alloc().initWithFrame_(base.frame())
        self.view.setStyle_(AppKit.NSGlassEffectViewStyleClear)
        self.view.setAppearance_(base.appearance())
        self.view.setTintColor_(AppKit.NSColor.colorWithSRGBRed_green_blue_alpha_(.20,.60,.80,.52))
        self.view.setWantsLayer_(True)
        self.view.setAlphaValue_(0.25)
        self.mask = Quartz.CAShapeLayer.layer()
        self.mask.setFillRule_(Quartz.kCAFillRuleEvenOdd)
        self.view.layer().setMask_(self.mask)
        self.key = None
        parent.addSubview_positioned_relativeTo_(self.view, AppKit.NSWindowAbove, base)

    def resize(self, frame, radius):
        import Quartz
        key = (frame.origin.x, frame.origin.y, frame.size.width, frame.size.height, radius)
        if key == self.key:
            return
        width, height = frame.size.width, frame.size.height
        if min(width,height) < 12 or radius < 5:
            self.view.setHidden_(True)
            return
        self.view.setHidden_(False)
        self.key = key
        Quartz.CATransaction.begin()
        try:
            Quartz.CATransaction.setDisableActions_(True)
            inset, band = 1.6, 4.5
            width, height = width-2*inset, height-2*inset
            radius -= inset
            self.view.setFrame_(((frame.origin.x+inset,frame.origin.y+inset),(width,height)))
            self.view.setCornerRadius_(radius)
            ring = Quartz.CGPathCreateMutable()
            for d in (0.0,band):
                rounded = Quartz.CGPathCreateWithRoundedRect(
                    ((d,d),(width-2*d,height-2*d)), max(0,radius-d),max(0,radius-d),None)
                Quartz.CGPathAddPath(ring,None,rounded)
            self.mask.setFrame_(self.view.bounds())
            self.mask.setPath_(ring)
        finally:
            Quartz.CATransaction.commit()

    def close(self):
        self.view.removeFromSuperview()
