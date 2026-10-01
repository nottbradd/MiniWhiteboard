"""ScreenCaptureKit still captures, serialized onto Qt's main thread for composition."""
from PySide6.QtCore import QCoreApplication, QObject, QRectF, QTimer, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QImage, QPainter

from ..base import CapturePermissionError
from ..capture_geometry import plan_capture

PERMISSION_MESSAGE = (
    "Mini Whiteboard needs Screen Recording permission to turn the selected desktop region "
    "into a whiteboard. In System Settings → Privacy & Security → Screen Recording "
    "(or Screen & System Audio Recording), enable Mini Whiteboard, then quit and reopen it "
    "if macOS asks. Microphone and Accessibility access are not required."
)


def image_from_cgimage(image):
    import AppKit
    # NSBitmapImageRep normalizes row order/color format. This encoding is only
    # at capture time; the existing immutable source/display cache owns drawing.
    rep = AppKit.NSBitmapImageRep.alloc().initWithCGImage_(image)
    png = rep.representationUsingType_properties_(AppKit.NSBitmapImageFileTypePNG, {})
    if png is None:
        raise OSError("ScreenCaptureKit returned an unreadable image.")
    result = QImage.fromData(bytes(png), "PNG")
    if result.isNull():
        raise OSError("ScreenCaptureKit returned an empty image.")
    result.setDevicePixelRatio(1)
    return result


class MacCaptureService:
    """Platform selection occurs before QApplication; defer all Qt objects."""

    def __init__(self, desktop):
        self.desktop = desktop
        self._capture = None

    def _get(self):
        if self._capture is None:
            self._capture = MacCapture(self.desktop)
        return self._capture

    def prepare(self):
        self._get().prepare()

    def capture_region(self, rect, success, failure, excluded=()):
        self._get().capture_region(rect, success, failure, excluded)

    def open_permission_settings(self):
        self._get().open_permission_settings()

    def cancel(self):
        if self._capture is not None:
            self._capture.cancel()


class MacCapture(QObject):
    dispatch = Signal(object)

    def __init__(self, desktop):
        app = QCoreApplication.instance()
        if app is None:
            raise RuntimeError("Create QApplication before starting screen capture.")
        # QApplication must outlive the callback dispatcher and its timer.
        super().__init__(app)
        self.desktop = desktop
        self.generation = 0
        self.job = None
        self.dispatch.connect(self._dispatch, Qt.ConnectionType.QueuedConnection)
        self.timeout = QTimer(self)
        self.timeout.setSingleShot(True)
        self.timeout.setInterval(15000)
        self.timeout.timeout.connect(lambda: self._fail(OSError("ScreenCaptureKit did not respond within 15 seconds.")))

    @Slot(object)
    def _dispatch(self, callback):
        callback()

    def prepare(self):
        import Quartz
        if not Quartz.CGPreflightScreenCaptureAccess():
            Quartz.CGRequestScreenCaptureAccess()
            if not Quartz.CGPreflightScreenCaptureAccess():
                raise CapturePermissionError(PERMISSION_MESSAGE)

    def open_permission_settings(self):
        QDesktopServices.openUrl(QUrl("x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture"))

    def capture_region(self, rect, success, failure, excluded=()):
        import ScreenCaptureKit as SC
        self.cancel()
        generation = self.generation
        try:
            self.prepare()
            plan = plan_capture(rect, self.desktop.displays())
            output = QImage(plan.width, plan.height, QImage.Format.Format_ARGB32_Premultiplied)
            if output.isNull():
                raise MemoryError("Not enough memory for the screenshot.")
            output.fill(Qt.GlobalColor.white)
            self.job = dict(generation=generation, plan=plan, output=output, success=success,
                            failure=failure, excluded=set(excluded), remaining=len(plan.pieces))
            self.timeout.start()
            def content_ready(content, error):
                self.dispatch.emit(lambda: self._content(generation, content, error))
            SC.SCShareableContent.getShareableContentExcludingDesktopWindows_onScreenWindowsOnly_completionHandler_(
                False, True, content_ready)
        except Exception as error:
            if self.job is not None:
                self._fail(error)
            else:
                failure(error)

    def _current(self, generation):
        return self.job is not None and generation == self.generation

    def _content(self, generation, content, error):
        if not self._current(generation):
            return
        if error is not None or content is None:
            self._fail(self._native_error(error))
            return
        import ScreenCaptureKit as SC
        import Quartz
        try:
            displays = {int(d.displayID()): d for d in content.displays()}
            excluded = [w for w in content.windows() if int(w.windowID()) in self.job["excluded"]]
            # Retain native configuration/filter objects through completion.
            self.job["native"] = []
            for piece in self.job["plan"].pieces:
                display = displays.get(piece.display_id)
                if display is None:
                    raise OSError("A selected display disconnected before capture.")
                source = piece.source
                content_filter = SC.SCContentFilter.alloc().initWithDisplay_excludingWindows_(display, excluded)
                configuration = SC.SCStreamConfiguration.alloc().init()
                configuration.setSourceRect_(Quartz.CGRectMake(source.x, source.y, source.width, source.height))
                configuration.setWidth_(piece.pixels[0])
                configuration.setHeight_(piece.pixels[1])
                configuration.setShowsCursor_(False)
                configuration.setCapturesAudio_(False)
                configuration.setScalesToFit_(True)
                self.job["native"].append((content_filter, configuration))
                def captured(image, capture_error, p=piece):
                    self.dispatch.emit(lambda: self._piece(generation, p, image, capture_error))
                SC.SCScreenshotManager.captureImageWithFilter_configuration_completionHandler_(
                    content_filter, configuration, captured)
        except Exception as exception:
            self._fail(exception)

    def _piece(self, generation, piece, image, error):
        if not self._current(generation):
            return
        if error is not None or image is None:
            self._fail(self._native_error(error))
            return
        try:
            tile = image_from_cgimage(image)
            painter = QPainter(self.job["output"])
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            target = piece.target
            painter.drawImage(QRectF(target.x, target.y, target.width, target.height), tile)
            painter.end()
            self.job["remaining"] -= 1
            if self.job["remaining"] == 0:
                job = self.job
                self.cancel()
                job["success"](job["output"])
        except Exception as exception:
            self._fail(exception)

    @staticmethod
    def _native_error(error):
        import Quartz
        if not Quartz.CGPreflightScreenCaptureAccess():
            return CapturePermissionError(PERMISSION_MESSAGE)
        detail = str(error.localizedDescription()) if error is not None else "No screen content was returned."
        return OSError(detail)

    def _fail(self, error):
        if self.job is not None:
            failure = self.job["failure"]
            self.cancel()
            failure(error)

    def cancel(self):
        self.generation += 1
        self.timeout.stop()
        self.job = None
