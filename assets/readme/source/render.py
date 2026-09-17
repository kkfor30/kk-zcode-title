import os, re, subprocess, sys

CHROME = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
FONT = '-apple-system, BlinkMacSystemFont, Segoe UI, PingFang SC, Microsoft YaHei, sans-serif'
MONO = 'ui-monospace, SFMono-Regular, Consolas, monospace'


def render_svg(svg_path, out_png, scale=2, bg='00000000'):
    """Inline the SVG into a stage HTML next to it (so relative image hrefs resolve)
    and screenshot it with headless Chrome."""
    svg_path = os.path.abspath(svg_path)
    src = open(svg_path, encoding='utf-8').read()
    m = re.search(r'width="([\d.]+)"\s+height="([\d.]+)"', src)
    w, h = float(m.group(1)), float(m.group(2))
    stage = os.path.join(os.path.dirname(svg_path), '_stage.html')
    with open(stage, 'w', encoding='utf-8') as f:
        f.write('<!doctype html><html><head><meta charset="utf-8"><style>'
                'html,body{margin:0;padding:0;background:transparent;overflow:hidden}'
                'svg{display:block;width:%dpx;height:%dpx}'
                '</style></head><body>%s</body></html>' % (w, h, src))
    out = os.path.abspath(out_png)
    subprocess.run([CHROME, '--headless=new', '--disable-gpu', '--hide-scrollbars',
                    '--force-device-scale-factor=%d' % scale,
                    '--default-background-color=' + bg,
                    '--window-size=%d,%d' % (int(w), int(h)),
                    '--screenshot=' + out, stage],
                   capture_output=True, text=True, check=True)
    os.remove(stage)
    return out


if __name__ == '__main__':
    print(render_svg(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 2))
