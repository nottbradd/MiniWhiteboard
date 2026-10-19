"""User-visible defaults and shortcuts, shared by UI and documentation."""
from . import APP_VERSION

APP_NAME = "Mini Whiteboard"
MIN_WIDTH, MIN_HEIGHT = 160, 100
PREVIEW_INTERVAL_MS = 16
PAPER = "#ffffff"
INK = "#202124"
BORDER = "#dadce0"
SELECTION = "#73879a"
RADIUS = 12
SHADOW = 8
TOP_STRIP = 11  # Previously 32: keep a slim dedicated window drag strip.
CANVAS_INSET = 0  # Content reaches the sides/bottom; resizing uses invisible zones.
EDGE_GRIP = 7  # Invisible resize targets, independent of the canvas inset.
BORDER_WIDTH = 1  # Visible top edge only; sides and bottom have no outline.
CONTROL_WIDTH, CONTROL_HEIGHT = 24, 20
CONTROL_TOP, CONTROL_GAP, CONTROL_RIGHT = 3, 2, 5
CONTROL_FONT_SIZE = 16
DIRTY_PADDING = 3
DIRTY_RECT_LIMIT = 16  # Coalesce dense regions before Qt's raster clip becomes costly.
PREVIEW_DOT_DIAMETER = 2.5
PREVIEW_DOT_GAP = 6
PREVIEW_DOT_OPACITY = .75
PREVIEW_SHADOW_OPACITY = .16
PREVIEW_SHADOW_SPREAD = 1.25
PREVIEW_SHADOW_OFFSET = .65
PEN_SIZES = {1: 2, 2: 4, 3: 6, 4: 9, 5: 14}
FONT_SIZES = {1: 14, 2: 20, 3: 28}
TEXT_MARGIN = 8
TEXT_MIN_WIDTH, TEXT_DEFAULT_WIDTH, TEXT_MAX_WIDTH = 24, 320, 100_000
SHAPES = {1: "Rectangle", 2: "Rounded rectangle", 3: "Ellipse",
          4: "Line", 5: "Arrow", 6: "Triangle", 7: "Diamond"}
ERASER_SIZES = {1: 8, 2: 16, 3: 32, 4: 64}
DEFAULT_ERASER_KEY = 2
PASTE_OFFSET = 16
IMAGE_FIT_FRACTION = .9
MAX_IMAGE_PIXELS = 64_000_000
CLIPBOARD_MIME = "application/x-mini-whiteboard-objects+json"
MAX_CLIPBOARD_BYTES = 96_000_000
SNAP_THRESHOLD = 6
GRID_SIZE = 10
GUIDE_COLOR = "#738fae"
PALETTE_COLORS = (("Black", "#202124"), ("Red", "#e04444"), ("Blue", "#2878d0"),
                  ("Green", "#26945c"), ("Yellow", "#e5bc24"), ("Purple", "#9052c8"),
                  ("White", "#ffffff"))
ERASER_CURSOR_PADDING = 4
HANDLE_DIAMETER = 8  # Physical pixels; independent of object and Windows scaling.
HANDLE_HIT_RADIUS = 10  # Logical pixels for comfortable pointer targets.
ROTATION_HANDLE_DISTANCE = 24  # Physical pixels from the top midpoint.
CONTAINMENT_TOLERANCE = .01
DRAG_THRESHOLD = 3
TOOL_KEYS = {"D": "Draw", "T": "Text", "S": "Shape", "A": "Select", "V": "Select", "E": "Eraser"}
SHORTCUT_REFERENCE = f"""<b>Mini Whiteboard · Version {APP_VERSION}</b><br>
Ctrl+Alt+W — first corner → dotted preview → press again<br>
Ctrl+Alt+S — click, drag, release → screenshot board · Esc cancels<br><br>
<b>D</b> Draw · 1–5: 2 / 4 / 6 / 9 / 14 px<br>
<b>T</b> Text · 1–3: 14 / 20 / 28 pt (finish editing first)<br>
<b>S</b> Shapes · 1 Rectangle · 2 Rounded rectangle · 3 Ellipse<br>
4 Line · 5 Arrow · 6 Triangle · 7 Diamond<br>
<b>A / V</b> Select · drag empty paper to fully enclose objects<br>
Shift+click toggles · Shift+marquee adds · drag inside the box to move<br>
Round handles resize · handle above the box rotates<br>
Corners / text / images keep ratio · Shift: keep ratio / rotate by 15°<br>
<b>E</b> Eraser · 1–4: 8 / 16 / 32 / 64 px · 5: toggle whole stroke<br>
5 again returns to 16 px · 1–4 always select circular mode<br>
Solid circle: partial cuts · dashed circle: whole freehand strokes only<br>
Shift + shape creation — square / circle / snap line angle<br>
In S mode, line/arrow endpoints remain editable<br>
<b>C</b> Colour · 1–7 presets · custom / recent colours<br><br>
Ctrl+C / X / V / D — copy / cut / paste / duplicate objects<br>
Ctrl+V also pastes screenshots · drop PNG/JPG/WEBP files<br>
Ctrl+A — select all unlocked objects<br>
Arrows — nudge 1 px · Shift+Arrows — nudge 10 px<br>
Alt while moving/resizing — temporarily disable snapping<br>
Tray → Snap &amp; Guides: Smart Guides on / Grid Snap off by default<br>
Right-click — editing, front/back, lock / unlock<br><br>
Ctrl+Z — undo · Ctrl+Y / Ctrl+Shift+Z — redo<br>
Delete / Backspace — delete all selected objects (one undo)<br>
Esc — cancel interaction / clear selection · F1 — toggle this reference<br><br>
<b>Editing text</b><br>
Text wraps to its stored width. Tool letters, C and numbers type normally.<br>
Enter adds a real new line; soft wraps leave the text unchanged.<br>
Ctrl+Enter / Esc / click outside — finish editing.<br>
Double-click text to edit. Text undo stays inside the editor.<br><br>
Drag the empty top edge to move; edges/corners to resize the board.<br>
− hides to tray · × deletes this board · tray menu exits the application.
"""
