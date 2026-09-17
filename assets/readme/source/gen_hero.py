# -*- coding: utf-8 -*-
"""Builds assets/readme/hero.svg — a warm paper board contrasting vague session
titles with the ones the plugin maintains."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from theme import *            # noqa: F401,F403

W, H = 1200, 440

BEFORE = ['新会话', '帮我看看这个', '继续修改']
AFTER = [('🔧', '邮箱注册｜验证码重发', '工具开发'),
         ('🐛', '支付回调｜重复扣款排查', '故障排查'),
         ('🚀', '邮件服务｜容器化上线', '部署上线')]

p = []
a = p.append
a(svg_open(W, H, 'kk-zcode-title：ZCode 话题实时命名',
           '左侧是自动命名前的模糊标题，右侧是命名后侧边栏里的标题：邮箱注册｜验证码重发、支付回调｜重复扣款排查、邮件服务｜容器化上线。').rstrip('\n'))

# header
a('  <g font-family="%s">' % FONT)
a('    <text x="40" y="40" font-size="20" font-weight="600" fill="%s">kk-zcode-title</text>' % MUTED)
a('    <g transform="translate(946 18)">')
a('      <rect width="214" height="34" rx="17" fill="%s"/>' % TINTS[0])
a('      <circle cx="20" cy="17" r="4" fill="#397256"/>')
a('      <text x="34" y="23" font-size="18" fill="#355D46">后台独立 Worker</text>')
a('    </g>')
a('    <text x="38" y="101" font-size="48" font-weight="700" letter-spacing="-1" fill="%s">ZCode 话题实时命名，<tspan fill="%s">一眼找回。</tspan></text>' % (INK, ACCENT))
a('    <text x="40" y="139" font-size="22" fill="%s">十二类 emoji，对象在前，目标在后。</text>' % MUTED)
a('  </g>')

# before card
a('  <g id="before" transform="translate(40 166)" font-family="%s">' % FONT)
a('    <rect width="356" height="216" rx="14" fill="%s"/>' % CARD)
a('    <text x="22" y="32" font-size="20" font-weight="600" fill="%s">原来的标题</text>' % FAINT)
a('    <path d="M22 45h312" stroke="%s"/>' % CARD_LINE)
a('    <g fill="%s" font-size="28">' % GHOST)
for i, t in enumerate(BEFORE):
    a('      <text x="24" y="%d">%s</text>' % (87 + i * 54, t))
a('    </g>')
a('  </g>')

# arrows
a('  <g fill="none" stroke="%s" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">' % ARROW)
for i in range(3):
    a('    <path d="M414 %dh43m-9-8 9 8-9 8"/>' % (243 + i * 54))
a('  </g>')

# after card
a('  <g id="after" transform="translate(476 166)">')
a('  <rect width="684" height="216" rx="14" fill="%s"/>' % PANEL)
a('    <text x="22" y="32" font-size="20" font-weight="600" fill="%s" font-family="%s">现在，一眼认出正在做什么</text>' % (ACCENT, FONT))
a('    <path d="M22 45h640" stroke="%s"/>' % HAIRLINE)
for i in range(3):
    a('    <rect x="12" y="%d" width="660" height="44" rx="9" fill="%s"/>' % (56 + i * 54, TINTS[i]))
a('    <g font-family="%s" font-size="28">' % EMOJI)
for i, (emoji, _, _) in enumerate(AFTER):
    a('      <text x="24" y="%d">%s</text>' % (88 + i * 54, emoji))
a('    </g>')
a('    <g font-family="%s" fill="#233D2F" font-size="29">' % FONT)
for i, (_, title, _) in enumerate(AFTER):
    a('      <text x="72" y="%d">%s</text>' % (88 + i * 54, title))
a('    </g>')
# category tag, right aligned inside each row
for i, (_, _, tag) in enumerate(AFTER):
    a('    <rect x="566" y="%d" width="92" height="26" rx="13" fill="#FFFFFF" fill-opacity="0.72"/>' % (65 + i * 54))
    a('    <text x="612" y="%d" font-family="%s" font-size="16" fill="%s" text-anchor="middle">%s</text>' % (83 + i * 54, FONT, ACCENT, tag))
a('  </g>')

a('  <text x="40" y="417" font-family="%s" font-size="20" fill="%s">每轮结束后自动判断 · 参考最近 3～5 轮 · 只改标题字段，不写回对话</text>' % (FONT, MUTED))
a('</svg>')

out = os.path.join(HERE, '..', 'hero.svg')
open(out, 'w', encoding='utf-8').write('\n'.join(p) + '\n')
print('-> hero.svg')
