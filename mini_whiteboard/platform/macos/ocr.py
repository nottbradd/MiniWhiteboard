"""System Vision, available below the application's macOS 14 minimum."""


def recognize_image(image):
    import Vision
    from Foundation import NSData
    from PySide6.QtCore import QByteArray, QBuffer, QIODevice
    encoded = QByteArray()
    buffer = QBuffer(encoded)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, 'PNG'):
        raise RuntimeError('Could not prepare OCR image.')
    data = NSData.dataWithBytes_length_(bytes(encoded), len(encoded))
    request = Vision.VNRecognizeTextRequest.alloc().init()
    request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    request.setRecognitionLanguages_(['en-US'])
    request.setUsesLanguageCorrection_(True)
    request.setAutomaticallyDetectsLanguage_(False)
    handler = Vision.VNImageRequestHandler.alloc().initWithData_options_(data, {})
    success, error = handler.performRequests_error_([request], None)
    if not success:
        raise RuntimeError('Vision could not recognize this image.')
    # Vision returns lines in reading order with their original punctuation.
    return '\n'.join(str(candidates[0].string()) for observation in request.results() or []
                     if (candidates := observation.topCandidates_(1)))
