"""Explicit desktop-point to per-display pixel conversion, independent of Cocoa."""
from dataclasses import dataclass
import math

from ..geometry import Rect
from ..images import check_size


@dataclass(frozen=True)
class CapturePiece:
    display_id: int | str
    source: Rect       # display-local desktop points
    pixels: tuple[int, int]
    target: Rect       # output image pixels


@dataclass(frozen=True)
class CapturePlan:
    width: int
    height: int
    scale: float
    pieces: tuple[CapturePiece, ...]


def plan_capture(rect, displays):
    if not all(math.isfinite(v) for v in (rect.x, rect.y, rect.width, rect.height)) or min(rect.width, rect.height) <= 0:
        raise ValueError("Invalid screenshot rectangle.")
    displays = [d for d in displays if d.rect.intersection_area(rect) > 0]
    if not displays:
        raise ValueError("The screenshot region does not intersect a display.")
    scale = max(d.scale for d in displays)
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError("Invalid display scale.")
    width, height = math.ceil(rect.width*scale), math.ceil(rect.height*scale)
    check_size(width, height)
    pieces = []
    for display in displays:
        x, y = max(rect.x, display.rect.x), max(rect.y, display.rect.y)
        right, bottom = min(rect.right, display.rect.right), min(rect.bottom, display.rect.bottom)
        left_px, top_px = round((x-rect.x)*scale), round((y-rect.y)*scale)
        right_px, bottom_px = round((right-rect.x)*scale), round((bottom-rect.y)*scale)
        source = Rect(x-display.rect.x, y-display.rect.y, right-x, bottom-y)
        pixels = math.ceil(source.width*display.scale), math.ceil(source.height*display.scale)
        check_size(*pixels)
        pieces.append(CapturePiece(display.identifier, source, pixels,
                                   Rect(left_px, top_px, right_px-left_px, bottom_px-top_px)))
    return CapturePlan(width, height, scale, tuple(pieces))
