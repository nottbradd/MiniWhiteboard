"""Compare native optical samples clipped to the same band on one review board."""
def paired_trial(board, modes):
    import AppKit
    import Quartz
    content, base, parent = board._visual_effect
    frame = base.frame()
    x,y = frame.origin.x,frame.origin.y
    w,h = frame.size.width,frame.size.height
    radius = board.corner_radius()
    views = []
    below = base
    for inset, start, band, alpha, tint in modes:
        view = AppKit.NSGlassEffectView.alloc().initWithFrame_(((x+inset,y+inset),(w-2*inset,h-2*inset)))
        view.setStyle_(AppKit.NSGlassEffectViewStyleClear)
        view.setAppearance_(base.appearance())
        view.setCornerRadius_(radius-inset)
        view.setTintColor_(AppKit.NSColor.colorWithSRGBRed_green_blue_alpha_(*tint))
        view.setAlphaValue_(alpha)
        view.setWantsLayer_(True)
        mask=Quartz.CAShapeLayer.layer()
        mask.setFrame_(view.bounds())
        mask.setFillRule_(Quartz.kCAFillRuleEvenOdd)
        ring=Quartz.CGPathCreateMutable()
        for d in (start,start+band):
            rounded=Quartz.CGPathCreateWithRoundedRect(
                ((d-inset,d-inset),(w-2*d,h-2*d)),max(0,radius-d),max(0,radius-d),None)
            Quartz.CGPathAddPath(ring,None,rounded)
        mask.setPath_(ring)
        view.layer().setMask_(mask)
        parent.addSubview_positioned_relativeTo_(view,AppKit.NSWindowAbove,below)
        views.append(view)
        below=view
    return views


def paired_samples(board, background, folder, report, capture):
    board._glass_rim.view.setHidden_(True)
    blue=(.03,.42,.88,.93)
    gold=(.99,.49,.015,.91)
    from PySide6.QtTest import QTest
    for name,config in (
        ('thin-a',[(2.6,3,3.3,.93,gold),(-3,3,3.3,.49,blue)]),
        ('thin-b',[(1.8,2,3.6,.90,(.99,.47,.09,.92)),(-4,2,3.6,.50,(.03,.46,.83,.95))]),
        ('thin-c',[(-4,1.9,3.2,.91,gold),(1.5,1.9,3.2,.48,blue)]),
        ('thin-d',[(2.0,2.2,2.9,.83,(.90,.32,.11,.90)),(-3.5,2.2,2.9,.48,(.04,.55,.82,.92))]),
    ):
        views=paired_trial(board,config)
        try:
            QTest.qWait(250)
            report['samples'][name]=capture(background,folder,name)
            for scene in ('light','dark'):
                background.palette_name=scene;background.phase=None;background.update()
                from .glass_optics import photograph
                photograph(background,folder/f'{scene}-{name}-bare.png')
        finally:
            for view in reversed(views):
                view.removeFromSuperview()
    board._glass_rim.view.setHidden_(False)
