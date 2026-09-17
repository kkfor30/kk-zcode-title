# -*- coding: utf-8 -*-
"""Cut the category icons out of the generated sheet and composite them into the
rendered README modules as rounded icon tiles.

The sheet is a dark plate laid out as a COLS x ROWS grid. Each tile is located by
its own bright bounding box (so a slightly off-centre generation still crops
cleanly), clamped inside its cell so neighbouring icons can never bleed in, then
re-based onto TILE_BG and composited through an anti-aliased rounded-rect mask.
"""
import os
import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
SHEET = os.path.join(HERE, 'category-icons.webp')
COLS, ROWS = 4, 3
COUNT = COLS * ROWS

TILE = 320          # working resolution per icon
PAD = 1.16          # margin kept around the detected bounding box
BG_MARGIN = 22      # luminance above local background that counts as "the icon"
TILE_BG = (8, 11, 17)
_SS = 4             # supersampling for the rounded mask

_cache = {}


def _cell_box(i, cw, ch):
    c, r = i % COLS, i // COLS
    return c * cw, r * ch


def tiles():
    """Raw crops of the COUNT icons, in reading order (left to right, top to bottom)."""
    if 'v' in _cache:
        return _cache['v']
    sheet = Image.open(SHEET).convert('RGB')
    w, h = sheet.size
    cw, ch = w / COLS, h / ROWS
    out = []
    for i in range(COUNT):
        ox, oy = _cell_box(i, cw, ch)
        cell = np.asarray(sheet.crop((int(ox), int(oy), int(ox + cw), int(oy + ch)))).astype(np.float32)
        lum = cell.mean(axis=2)
        bg = np.median(np.concatenate([lum[:8].ravel(), lum[-8:].ravel(),
                                       lum[:, :8].ravel(), lum[:, -8:].ravel()]))
        ys, xs = np.where(lum > bg + BG_MARGIN)
        if len(xs) == 0:
            bx0, bx1, by0, by1 = 0, cw - 1, 0, ch - 1
        else:
            bx0, bx1, by0, by1 = xs.min(), xs.max(), ys.min(), ys.max()
        side = min(max(bx1 - bx0, by1 - by0) * PAD, min(cw, ch) * 0.98)
        cx, cy = (bx0 + bx1) / 2, (by0 + by1) / 2
        x0 = min(max(cx - side / 2, 0), cw - side)
        y0 = min(max(cy - side / 2, 0), ch - side)
        box = (int(ox + x0), int(oy + y0), int(ox + x0 + side), int(oy + y0 + side))
        out.append(sheet.crop(box).resize((TILE, TILE), Image.LANCZOS))
    _cache['v'] = out
    return out


def _rounded_mask(size, radius):
    n = size * _SS
    m = Image.new('L', (n, n), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, n - 1, n - 1],
                                        radius=int(round(radius * _SS)), fill=255)
    return np.asarray(m.resize((size, size), Image.LANCZOS)).astype(np.float32) / 255.0


def tile_image(index, size, radius_ratio=0.24):
    """Icon crop re-based onto TILE_BG, plus its rounded alpha mask."""
    src = tiles()[index].resize((size, size), Image.LANCZOS)
    arr = np.asarray(src).astype(np.float32)
    b = max(2, size // 16)
    ring = np.concatenate([arr[:b].reshape(-1, 3), arr[-b:].reshape(-1, 3),
                           arr[:, :b].reshape(-1, 3), arr[:, -b:].reshape(-1, 3)])
    arr = arr - np.median(ring, axis=0)[None, None, :] + np.array(TILE_BG, dtype=np.float32)
    return np.clip(arr, 0, 255), _rounded_mask(size, size * radius_ratio)


def blend(base, index, cx, cy, size, radius_ratio=0.24):
    """Composite one icon tile centred at pixel (cx, cy) of base (an RGBA image)."""
    arr, m = tile_image(index, size, radius_ratio)
    x0, y0 = int(round(cx - size / 2)), int(round(cy - size / 2))
    reg = np.asarray(base.crop((x0, y0, x0 + size, y0 + size)).convert('RGB')).astype(np.float32)
    out = reg * (1 - m[..., None]) + arr * m[..., None]
    base.paste(Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)), (x0, y0))
