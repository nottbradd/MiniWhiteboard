"""A faint channel separation from a second, inset native glass sample."""


class GlassRim:
    def __init__(self, parent, base):
        import AppKit
        import Quartz
        self.view = AppKit.NSView.alloc().initWithFrame_(base.frame())
        self.view.setWantsLayer_(True)
        self.sample = AppKit.NSGlassEffectView.alloc().initWithFrame_(self.view.bounds())
        self.sample.setStyle_(AppKit.NSGlassEffectViewStyleClear)
        self.sample.setAppearance_(base.appearance())
        self.view.addSubview_(self.sample)
        # min(base, (sample.red,1,1)) changes only the red channel where the
        # second optical sample actually darkens. A uniform field stays neutral.
        matrix = Quartz.CIFilter.filterWithName_('CIColorMatrix')
        vector = Quartz.CIVector.vectorWithX_Y_Z_W_
        zero = vector(0,0,0,0)
        matrix.setValue_forKey_(zero,'inputGVector')
        matrix.setValue_forKey_(zero,'inputBVector')
        matrix.setValue_forKey_(vector(0,1,1,0),'inputBiasVector')
        self.view.setContentFilters_([matrix])
        self.view.setCompositingFilter_(Quartz.CIFilter.filterWithName_('CIDarkenBlendMode'))
        self.view.setAlphaValue_(0.22)
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
            self.view.setFrame_(frame)
            inset, band = 1.8, 6.0
            self.sample.setFrame_(((inset,inset),(width-2*inset,height-2*inset)))
            self.sample.setCornerRadius_(max(0,radius-inset))
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
