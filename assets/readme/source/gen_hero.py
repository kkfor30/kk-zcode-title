# -*- coding: utf-8 -*-
"""Builds assets/readme/source/hero-layout.svg, the editable layout source of the
hybrid hero (generated background plate + generated 3D category icons).

Icon placement is exported as ICON_PLACEMENTS in SVG units and applied by
build.py after Chrome renders the SVG.
"""
import os

W, H = 1200, 560
FONT = '-apple-system, BlinkMacSystemFont, Segoe UI, PingFang SC, Microsoft YaHei, sans-serif'
MONO = 'ui-monospace, SFMono-Regular, Consolas, monospace'

BG_HREF = 'hero-bg.webp'
HAS_BG = os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), BG_HREF))

# (icon index, centre x, centre y) in SVG units, for the three "after" rows
ICON_SIZE = 58
ICON_PLACEMENTS = [(0, 494, 342), (7, 494, 404), (6, 494, 466)]

BEFORE = ['新会话', '帮我看下这个页面', '继续修改']
AFTER = ['产品短片｜分镜调整', '登录页｜视觉还原', '推理模型｜选型对比']
ROW_Y = [342, 404, 466]

p = []
a = p.append
a('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" role="img" aria-labelledby="hero-t hero-d">' % (W, H, W, H))
a('  <title id="hero-t">kk-zcode-title</title>')
a('  <desc id="hero-d">ZCode 插件。左侧是自动命名前的模糊标题，右侧是命名后侧边栏里看到的具体标题：邮箱注册｜修复、产品短片｜分镜调整、登录页｜视觉还原。每轮对话结束后由后台独立模型判断是否更新。</desc>')
a('  <defs>')
a('    <linearGradient id="scrimH" x1="0" y1="0" x2="1" y2="0">')
a('      <stop offset="0" stop-color="#070A11" stop-opacity="0.86"/>')
a('      <stop offset="0.5" stop-color="#070A11" stop-opacity="0.48"/>')
a('      <stop offset="1" stop-color="#070A11" stop-opacity="0.68"/>')
a('    </linearGradient>')
a('    <linearGradient id="scrimV" x1="0" y1="0" x2="0" y2="1">')
a('      <stop offset="0" stop-color="#070A11" stop-opacity="0.72"/>')
a('      <stop offset="0.3" stop-color="#070A11" stop-opacity="0.06"/>')
a('      <stop offset="1" stop-color="#070A11" stop-opacity="0.6"/>')
a('    </linearGradient>')
a('  </defs>')
a('')
a('  <!-- generated raster plate -->')
a('  <rect width="%d" height="%d" fill="#0A0D14"/>' % (W, H))
if HAS_BG:
    a('  <image href="%s" x="0" y="0" width="%d" height="%d" preserveAspectRatio="xMidYMid slice"/>' % (BG_HREF, W, H))
a('  <rect width="%d" height="%d" fill="url(#scrimH)"/>' % (W, H))
a('  <rect width="%d" height="%d" fill="url(#scrimV)"/>' % (W, H))
a('')

a('  <g id="title-block">')
a('    <text x="64" y="76" font-family="%s" font-size="18" letter-spacing="1" fill="#8B98AE">ZCODE 插件 · 话题自动命名</text>' % MONO)
a('    <rect x="64" y="88" width="44" height="3" rx="1.5" fill="#4D8DFF"/>')
a('    <text x="64" y="158" font-family="%s" font-size="62" font-weight="700" letter-spacing="-1" fill="#E9EEF8">kk-zcode-title</text>' % FONT)
a('    <text x="64" y="202" font-family="%s" font-size="21" fill="#B9C4D6">每轮对话结束后，后台独立模型把话题标题</text>' % FONT)
a('    <text x="64" y="230" font-family="%s" font-size="21" fill="#B9C4D6">维护成稳定的「类别 emoji + 对象｜目标」</text>' % FONT)
a('  </g>')
a('')

a('  <g id="meta">')
for label, x, w in (('Python 3.10+', 752, 146), ('零第三方依赖', 910, 124), ('MIT', 1046, 90)):
    a('    <rect x="%d" y="58" width="%d" height="36" rx="10" fill="#FFFFFF" fill-opacity="0.06" stroke="#2C3A50"/>' % (x, w))
    a('    <text x="%d" y="81" font-family="%s" font-size="16" fill="#9AA8BE" text-anchor="middle">%s</text>' % (x + w / 2, MONO, label))
a('  </g>')
a('')

LX, LY, LW, LH = 64, 274, 296, 238
RX, RW = 436, 700
a('  <g id="board">')
a('    <rect x="%d" y="%d" width="%d" height="%d" rx="16" fill="#0B111A" fill-opacity="0.66" stroke="#253145"/>' % (LX, LY, LW, LH))
a('    <text x="%d" y="%d" font-family="%s" font-size="18" fill="#7E8AA0">原来的标题</text>' % (LX + 24, LY + 36, FONT))
a('    <line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#253145"/>' % (LX + 24, LY + 50, LX + LW - 24, LY + 50))
for i, t in enumerate(BEFORE):
    a('    <text x="%d" y="%d" font-family="%s" font-size="25" fill="#6E7A90">%s</text>'
      % (LX + 24, ROW_Y[i] + 9, FONT, t))

a('    <rect x="%d" y="%d" width="%d" height="%d" rx="16" fill="#0E141F" fill-opacity="0.9" stroke="#2C3A50"/>' % (RX, LY, RW, LH))
a('    <text x="%d" y="%d" font-family="%s" font-size="18" fill="#4D8DFF">ZCode 侧边栏 · 每轮自动维护</text>' % (RX + 24, LY + 36, FONT))
a('    <line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#2C3A50"/>' % (RX + 24, LY + 50, RX + RW - 24, LY + 50))
for i, t in enumerate(AFTER):
    a('    <text x="%d" y="%d" font-family="%s" font-size="26" font-weight="600" fill="#E9EEF8">%s</text>'
      % (RX + 98, ROW_Y[i] + 9, FONT, t))

# slots the generated 3D icons are composited into
for _, cx, cy in ICON_PLACEMENTS:
    a('    <rect x="%d" y="%d" width="%d" height="%d" rx="14" fill="#080B11"/>'
      % (cx - ICON_SIZE / 2, cy - ICON_SIZE / 2, ICON_SIZE, ICON_SIZE))

a('    <g fill="none" stroke="#4D8DFF" stroke-opacity="0.75" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">')
for y in ROW_Y:
    a('      <path d="M376 %d h44 m-9-8 9 8 -9 8"/>' % y)
a('    </g>')
a('  </g>')
a('</svg>')

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hero-layout.svg')
open(out, 'w', encoding='utf-8').write('\n'.join(p) + '\n')
print('bg plate:', HAS_BG, '->', out)
