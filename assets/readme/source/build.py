# -*- coding: utf-8 -*-
"""Regenerate every published README asset.

    python source/build.py

Outputs: assets/readme/hero.svg, workflow.svg, categories.svg
Everything is plain SVG — no raster, no browser step.
"""
import os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
README_DIR = os.path.normpath(os.path.join(HERE, '..'))
PY = sys.executable

if __name__ == '__main__':
    for script in ('gen_hero.py', 'gen_workflow.py', 'gen_categories.py'):
        r = subprocess.run([PY, os.path.join(HERE, script)], cwd=HERE,
                           capture_output=True, text=True)
        print('$', script, r.stdout.strip())
        if r.returncode:
            print(r.stderr[-2000:])
            raise SystemExit(1)
    print('---')
    for f in ('hero.svg', 'workflow.svg', 'categories.svg'):
        p = os.path.join(README_DIR, f)
        print('OK  ' if os.path.exists(p) else 'MISS', f,
              os.path.getsize(p) if os.path.exists(p) else '')
