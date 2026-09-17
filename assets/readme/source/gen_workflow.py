# -*- coding: utf-8 -*-
"""Builds assets/readme/workflow.svg — one inverse panel: how a turn gets named
without ever blocking the conversation."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from theme import *            # noqa: F401,F403

W, H = 1200, 260
COLS = [
    ('一轮结束', 'Stop Hook 触发'),
    ('入口秒回', '派生 Worker 后秒回'),
    ('独立模型', '只读最近 3～5 轮'),
    ('保留 / 更新', '短事务写回 + 读回核验'),
]
COL_W, GAP, X0 = 234, 50, 57
LABEL_Y, SUB_Y, ARROW_Y = 136, 186, 126

p = []
a = p.append
a(svg_open(W, H, '后台命名流程',
           '一轮对话结束后触发 Stop Hook；入口立即派生独立 Worker 并返回，不阻塞对话；Worker 读取最近 3 到 5 轮的摘录交给独立模型判断；结果以短事务写回标题并读回核验。',
           radius=24, fill=DARK).rstrip('\n'))
a('  <text x="56" y="60" font-family="%s" font-size="24" fill="%s">对话之外，维护标题</text>' % (FONT, ON_DARK_DIM))
a('  <g font-family="%s" fill="%s">' % (FONT, ON_DARK))
for i, (label, sub) in enumerate(COLS):
    x = X0 + i * (COL_W + GAP)
    a('    <text x="%d" y="%d" font-size="32" font-weight="600">%s</text>' % (x, LABEL_Y, label))
    a('    <text x="%d" y="%d" font-size="22" fill="%s">%s</text>' % (x, SUB_Y, ON_DARK_MUTED, sub))
a('  </g>')
a('  <g stroke="%s" stroke-width="3" fill="none" stroke-linecap="round" stroke-linejoin="round">' % ARROW_ON_DARK)
for i in range(len(COLS) - 1):
    x = X0 + i * (COL_W + GAP) + COL_W + 6
    a('    <path d="M%d %dh34m-9-8 9 8-9 8"/>' % (x, ARROW_Y))
a('  </g>')
a('</svg>')

out = os.path.join(HERE, '..', 'workflow.svg')
open(out, 'w', encoding='utf-8').write('\n'.join(p) + '\n')
print('-> workflow.svg')
