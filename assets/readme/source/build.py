# -*- coding: utf-8 -*-
"""Rebuild every published README asset from source.

    python source/build.py

Inputs  : source/hero-layout.svg, source/categories-layout.svg, plus the two
          generated raster plates (source/hero-bg.png, source/category-icons.png)
Outputs : hero.webp, how-it-works.svg, categories.webp
"""
import os, subprocess, sys, tempfile
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))          # assets/readme/source
README_DIR = os.path.normpath(os.path.join(HERE, '..'))    # assets/readme
TMP = os.path.join(tempfile.gettempdir(), 'kk-zcode-title-preview')
os.makedirs(TMP, exist_ok=True)
sys.path.insert(0, HERE)
PY = sys.executable


def run(script, *args):
    r = subprocess.run([PY, os.path.join(HERE, script), *args], cwd=HERE,
                       capture_output=True, text=True)
    print('$', script, r.stdout.strip())
    if r.returncode:
        print(r.stderr[-2000:])
        raise SystemExit(1)


def to_webp(png, name, quality=90):
    out = os.path.join(README_DIR, name)
    Image.open(png).convert('RGB').save(out, 'WEBP', quality=quality, method=6)
    os.remove(png)
    return out


if __name__ == '__main__':
    run('gen_howitworks.py')
    run('gen_categories.py')
    run('gen_hero.py')

    import gen_hero, icons, render

    hero_png = os.path.join(TMP, 'hero.png')
    render.render_svg(os.path.join(HERE, 'hero-layout.svg'), hero_png, scale=2)
    print('$ render.py hero-layout.svg')
    hero = Image.open(hero_png).convert('RGBA')
    for idx, cx, cy in gen_hero.ICON_PLACEMENTS:
        icons.blend(hero, idx, cx * 2, cy * 2, gen_hero.ICON_SIZE * 2)
    hero.convert('RGB').save(hero_png, 'PNG')
    to_webp(hero_png, 'hero.webp', 92)

    render.render_svg(os.path.join(README_DIR, 'how-it-works.svg'),
                      os.path.join(TMP, 'how-it-works.png'), scale=2)
    print('$ render.py how-it-works.svg')

    print('---')
    for f in ('hero.webp', 'how-it-works.svg', 'categories.webp'):
        p = os.path.join(README_DIR, f)
        print('OK  ' if os.path.exists(p) else 'MISS', f,
              os.path.getsize(p) if os.path.exists(p) else '')
