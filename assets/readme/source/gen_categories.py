# -*- coding: utf-8 -*-
"""Builds assets/readme/categories.svg — the 12-category taxonomy as a light pill
grid. Definitions live in README.md; the picture only makes the set scannable."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from theme import *            # noqa: F401,F403

W, H = 1200, 384
CELLS = [
    ('🎬', '内容制作', '选题、脚本、剪辑'),
    ('🔧', '工具开发', '功能、代码、插件'),
    ('🐛', '故障排查', '定位并修复故障'),
    ('🚀', '部署上线', '容器、流水线、上线'),
    ('📊', '数据分析', '日志、指标、报表'),
    ('🌐', '网络代理', '分流、端口、连通'),
    ('🔎', '对比调研', '比较后形成判断'),
    ('🎨', '页面设计', '布局、视觉、动效'),
    ('📝', '方法整理', '文档、指南、方法'),
    ('📅', '日程安排', '日程、提醒、待办'),
    ('⚙️', '环境配置', '安装、连接、账号'),
    ('💬', '一般讨论', '有对象的其他事务'),
]
X0, CW, GAP, RH, RY0, ROW_GAP = 48, 258, 24, 76, 84, 16

p = []
a = p.append
a(svg_open(W, H, '十二类话题标题',
           '十二个类别及其 emoji：内容制作、工具开发、故障排查、部署上线、数据分析、网络代理、对比调研、页面设计、方法整理、日程安排、环境配置、一般讨论。完整定义见 README 表格。').rstrip('\n'))
a('  <text x="48" y="54" font-family="%s" font-size="18" fill="%s">类别按持续工作的产物选择，不按最后一个动作切换</text>' % (FONT, MUTED))
for i, (emoji, name, hint) in enumerate(CELLS):
    x = X0 + (i % 4) * (CW + GAP)
    y = RY0 + (i // 4) * (RH + ROW_GAP)
    a('  <g transform="translate(%d %d)">' % (x, y))
    a('    <rect x="0.5" y="0.5" width="%d" height="%d" rx="16" fill="%s" stroke="%s"/>' % (CW - 1, RH - 1, PANEL, HAIRLINE))
    a('    <text x="18" y="50" font-family="%s" font-size="36">%s</text>' % (EMOJI, emoji))
    a('    <text x="74" y="34" font-family="%s" font-size="20" font-weight="600" fill="%s">%s</text>' % (FONT, INK, name))
    a('    <text x="74" y="58" font-family="%s" font-size="15" fill="%s">%s</text>' % (FONT, GHOST, hint))
    a('  </g>')
a('</svg>')

out = os.path.join(HERE, '..', 'categories.svg')
open(out, 'w', encoding='utf-8').write('\n'.join(p) + '\n')
print('-> categories.svg')
