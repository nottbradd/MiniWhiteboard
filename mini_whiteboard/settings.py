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
BORDER_WIDTH = 1  # White's top edge; Glass has a separate thin optical rim.
CONTROL_WIDTH, CONTROL_HEIGHT = 24, 24  # 20px surface inside a modest 2px hit pad.
CONTROL_HIT_PADDING = 2
CONTROL_TOP, CONTROL_GAP, CONTROL_RIGHT = 10, 4, 10
DIRTY_PADDING = 3
DIRTY_RECT_LIMIT = 16  # Coalesce dense regions before Qt's raster clip becomes costly.
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
# Sections are shared by the responsive reference and the plain help export.
HELP_SECTIONS = (
    ('Create & windows',
     'Win+Alt+Shift+W — hold at the first corner → move → release to place.<br>'
     'Win+Alt+Shift+Q — hold → move → release for a screenshot board. Esc cancels.<br>'
     'Ctrl+Alt+H — Hide All / Restore All without taking focus.<br>'
     'Drag the empty top edge to move; edges/corners resize.<br>'
     '− hides to tray · × deletes this board · tray menu exits.<br>'
     'Tray → Appearance: White (default) / Glass.'),
    ('Draw & colour',
     '<b>D</b> Draw · 1–5: 2 / 4 / 6 / 9 / 14 px.<br>'
     '<b>S</b> Shapes · 1 Rectangle · 2 Rounded rectangle · 3 Ellipse · '
     '4 Line · 5 Arrow · 6 Triangle · 7 Diamond.<br>'
     'Shift during creation: square / circle / snap line angle.<br>'
     'In S mode, line/arrow endpoints remain editable.<br>'
     '<b>C</b> Colour · 1–7 presets · custom / recent colours.'),
    ('Select & transform',
     '<b>A / V</b> Select · drag empty paper to fully enclose objects.<br>'
     'Shift+click toggles · Shift+marquee adds.<br>'
     'Drag inside the box to move. Round handles resize; the handle above rotates.<br>'
     'Corners / text / images keep ratio. Shift keeps ratio or rotates by 15°.<br>'
     'Arrows nudge 1 px · Shift+Arrows nudge 10 px.'),
    ('Text editing',
     '<b>T</b> Text · 1–3: 14 / 20 / 28 pt (finish editing first).<br>'
     'Text wraps to its stored width. Tool letters, C and numbers type normally.<br>'
     'Enter adds a real new line; soft wraps leave text unchanged.<br>'
     'Ctrl+Enter / Esc / click outside — finish editing.<br>'
     'Every outside click finishes and deselects text. Click separately to insert/edit.<br>'
     'Blank drafts disappear without history; clearing existing text is undoable.<br>'
     'Double-click text to edit. Text undo stays inside the editor.'),
    ('Edit & arrange',
     'Ctrl+C / X / V / D — copy / cut / paste / duplicate objects.<br>'
     'Ctrl+V also pastes screenshots; drop PNG/JPG/WEBP files.<br>'
     'Ctrl+A selects all unlocked objects.<br>'
     'Right-click for editing, front/back and lock / unlock.<br>'
     'Ctrl+Z — undo · Ctrl+Y / Ctrl+Shift+Z — redo.<br>'
     'Delete / Backspace deletes selected objects (one undo).<br>'
     'Esc cancels interaction / clears selection · F1 toggles this reference.'),
    ('Eraser & guides',
     '<b>E</b> Eraser · 1–4: 8 / 16 / 32 / 64 px.<br>'
     '5 toggles whole stroke; 5 again returns to 16 px.<br>'
     '1–4 always select circular mode. Solid circle: partial cuts; '
     'dashed circle: whole freehand strokes only.<br>'
     'Alt while moving/resizing temporarily disables snapping.<br>'
     'Tray → Snap &amp; Guides: Smart Guides on / Grid Snap off by default.'),
)
SHORTCUT_REFERENCE = (f'<b>Mini Whiteboard · Version {APP_VERSION}</b><br><br>' +
                      '<br><br>'.join(f'<b>{title}</b><br>{body}' for title, body in HELP_SECTIONS))
