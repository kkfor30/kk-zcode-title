# -*- coding: utf-8 -*-
"""Cut the 8 category icons out of the generated 4x2 sheet and composite them
into the rendered README modules as rounded icon tiles.

The sheet is a dark plate. Each crop is re-based onto the module's tile colour
(subtract this crop's own background, add TILE_BG) so the rounded tile has no
visible seam, then composited through an anti-aliased rounded-rect mask.
"""
import os
import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
SHEET = os.path.join(HERE, 'category-icons.webp')
TILE = 320          # working resolution per icon
COLS, ROWS = 4, 2
CROP = 0.70         # fraction of a sheet cell kept around each icon
TILE_BG = (8, 11, 17)
_SS = 4             # supersampling for the mask

_cache = {}


def tiles():
    """Raw crops of the 8 icons, in reading order (left to right, top to bottom)."""
    if 'v' in _cache:
        return _cache['v']
    sheet = Image.open(SHEET).convert('RGB')
    sw, sh = sheet.size
    cw, ch = sw / COLS, sh / ROWS
    side = min(cw, ch) * CROP
    out = []
    for i in range(COLS * ROWS):
        col, row = i % COLS, i // COLS
        cx, cy = (col + 0.5) * cw, (row + 0.5) * ch
        box = (int(cx - side / 2), int(cy - side / 2),
               int(cx + side / 2), int(cy + side / 2))
        out.append(sheet.crop(box).resize((TILE, TILE), Image.LANCZOS))
    _cache['v'] = out
    return out


def _rounded_mask(size, radius):
    n = size * _SS
    m = Image.new('L', (n, n), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, n - 1, n - 1],
                                        radius=int(radius * _SS), fill=255)
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
