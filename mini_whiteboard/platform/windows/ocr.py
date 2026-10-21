"""The pinned Windows wheel includes Tesseract and every native image library."""
from pathlib import Path
import sys


def data_path():
    root = Path(sys._MEIPASS) if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[3]
    return root / 'assets' / 'ocr'


def recognize_image(image):
    # Lazy import: the engine and its DLLs never enter the GUI process.
    import tesserocr
    directory = data_path()
    if not (directory / 'eng.traineddata').is_file():
        raise RuntimeError('Missing English OCR data.')
    with tesserocr.PyTessBaseAPI(path=str(directory), lang='eng',
                                oem=tesserocr.OEM.LSTM_ONLY) as engine:
        engine.SetImageBytes(bytes(image.constBits()), image.width(), image.height(),
                             1, image.bytesPerLine())
        engine.SetSourceResolution(300)
        return engine.GetUTF8Text()
