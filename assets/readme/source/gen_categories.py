# -*- coding: utf-8 -*-
"""Builds assets/readme/categories.webp — the 12-category taxonomy as a pill grid.

The emoji are rendered by Chrome from the local colour-emoji font and baked into
the published raster, so every viewer sees the same glyphs. The full definitions
stay in README.md where they can be searched, translated and kept current.
"""
import os, sys
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, HERE)
import render                      # noqa: E402

W, H = 1200, 384
FONT = '-apple-system, BlinkMacSystemFont, Segoe UI, PingFang SC, Microsoft YaHei, sans-serif'

# (emoji, 名称, 一行提示)
CELLS = [
    ('🎬', '内容制作', '选题、脚本、拍摄、发布'),
    ('🔧', '工具开发', '新功能、代码、插件、Skill'),
    ('🐛', '故障排查', '定位并修复已有故障'),
    ('🚀', '部署上线', '容器、流水线、发布切换'),
    ('📊', '数据分析', '日志、指标、报表结论'),
    ('🌐', '网络代理', '分流、端口、连通性'),
    ('🔎', '对比调研', '比较后形成判断'),
    ('🎨', '页面设计', '布局、视觉与动效还原'),
    ('📝', '方法整理', '文档、指南、知识产物'),
    ('📅', '日程安排', '有时间的日程与待办'),
    ('⚙️', '环境配置', '安装、连接、账号设置'),
    ('💬', '一般讨论', '有对象的其他事务'),
]

X0, CW, GAP, RH, RY0 = 48, 258, 24, 76, 84
ROW_GAP = 16


def build_svg():
    p = []
    a = p.append
    a('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" role="img" aria-labelledby="ct cd">' % (W, H, W, H))
    a('  <title id="ct">十二类话题标题</title>')
    a('  <desc id="cd">十二个类别 emoji：内容制作、工具开发、故障排查、部署上线、数据分析、网络代理、对比调研、页面设计、方法整理、日程安排、环境配置、一般讨论。完整定义见 README 表格。</desc>')
    a('  <rect width="%d" height="%d" rx="22" fill="#0A0D14"/>' % (W, H))
    a('  <rect x="0.5" y="0.5" width="%d" height="%d" rx="21.5" fill="none" stroke="#222C3C"/>' % (W - 1, H - 1))
    a('  <text x="48" y="54" font-family="%s" font-size="18" fill="#7E8AA0">类别按持续工作的产物选择，不按最后一个动作切换</text>' % FONT)
    for i, (emoji, name, hint) in enumerate(CELLS):
        x = X0 + (i % 4) * (CW + GAP)
        y = RY0 + (i // 4) * (RH + ROW_GAP)
        a('  <g id="cat-%d" transform="translate(%d %d)">' % (i + 1, x, y))
        a('    <rect x="0.5" y="0.5" width="%d" height="%d" rx="16" fill="#FFFFFF" fill-opacity="0.04" stroke="#222C3C"/>' % (CW - 1, RH - 1))
        a('    <text x="18" y="%d" font-family="%s" font-size="36">%s</text>' % (RH // 2 + 13, FONT, emoji))
        a('    <text x="74" y="34" font-family="%s" font-size="20" font-weight="600" fill="#E9EEF8">%s</text>' % (FONT, name))
        a('    <text x="74" y="58" font-family="%s" font-size="15" fill="#7E8AA0">%s</text>' % (FONT, hint))
        a('  </g>')
    a('</svg>')
    return '\n'.join(p) + '\n'


def main():
    svg_path = os.path.join(HERE, 'categories-layout.svg')
    open(svg_path, 'w', encoding='utf-8').write(build_svg())
    png = render.render_svg(svg_path, os.path.join(OUT, '_cat_base.png'), scale=2)
    Image.open(png).convert('RGB').save(os.path.join(OUT, 'categories.webp'),
                                        'WEBP', quality=92, method=6)
    os.remove(png)
    print('-> categories.webp')


main()
