# -*- coding: utf-8 -*-
"""Render the published SVGs to PNG previews in %TEMP% for visual review.

    python source/preview.py [scale]

Dev tool only — it is not part of the published assets.
"""
import os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import render                      # noqa: E402

README_DIR = os.path.normpath(os.path.join(HERE, '..'))
OUT = os.path.join(tempfile.gettempdir(), 'kk-zcode-title-preview')

if __name__ == '__main__':
    scale = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    os.makedirs(OUT, exist_ok=True)
    for f in ('hero.svg', 'workflow.svg', 'categories.svg'):
        p = render.render_svg(os.path.join(README_DIR, f),
                              os.path.join(OUT, f.replace('.svg', '.png')), scale=scale)
        print(p)
