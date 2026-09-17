# -*- coding: utf-8 -*-
"""Write 900px / 360px GitHub-width previews of the published assets into %TEMP%."""
import os, tempfile
from PIL import Image

README_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
OUT = os.path.join(tempfile.gettempdir(), 'kk-zcode-title-preview')

if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    for name in ('hero.webp', 'categories.webp'):
        im = Image.open(os.path.join(README_DIR, name))
        for w in (900, 360):
            p = os.path.join(OUT, '%s-%d.png' % (name.split('.')[0], w))
            im.resize((w, int(im.height * w / im.width)), Image.LANCZOS).save(p)
            print(p)
