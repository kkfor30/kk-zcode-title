
import io, os

W, H = 1200, 360
CARDS = [
    ("01", "对话结束", ["Stop Hook 触发", "只更新标题", "不改其他状态"], "#4D8DFF"),
    ("02", "入口秒回", ["解析事件", "派生 Worker", "返回空 JSON"], "#4D8DFF"),
    ("03", "读取会话", ["db.sqlite", "最近 3–5 轮", "只取机器摘要"], "#7E8AA0"),
    ("04", "独立模型", ["keep / rename", "厂商兜底链", "额度耗尽自动切换"], "#7E8AA0"),
    ("05", "写回核验", ["短事务写入", "读回核验", "落审计日志"], "#7DD3A0"),
]

p = []
p.append('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" role="img" aria-labelledby="t d">' % (W, H, W, H))
p.append('  <title id="t">kk-zcode-title 的工作流程</title>')
p.append('  <desc id="d">对话结束后 Stop Hook 入口立即返回并派生独立 Worker；Worker 读取会话库最近 3 到 5 轮，调用独立轻量模型判断 keep 或 rename，再以短事务写回 session.title 并读回核验。</desc>')
p.append('  <defs>')
p.append('    <linearGradient id="bg" x1="0" y1="0" x2="0.8" y2="1">')
p.append('      <stop offset="0" stop-color="#0C1119"/>')
p.append('      <stop offset="1" stop-color="#080B11"/>')
p.append('    </linearGradient>')
p.append('    <marker id="arw" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto">')
p.append('      <path d="M0 1 L9 5 L0 9 Z" fill="#39445A"/>')
p.append('    </marker>')
p.append('  </defs>')
p.append('  <rect width="%d" height="%d" rx="22" fill="url(#bg)"/>' % (W, H))
p.append('  <rect x="0.5" y="0.5" width="%d" height="%d" rx="21.5" fill="none" stroke="#222C3C"/>' % (W - 1, H - 1))
p.append('  <text x="48" y="54" font-family="ui-monospace, SFMono-Regular, Consolas, monospace" font-size="18" fill="#7E8AA0">对话结束 → 入口秒回 → 后台 Worker → 写回核验</text>')

CW, CH, GAP, X0, Y0 = 200, 178, 28, 48, 96
for i, (num, title, lines, accent) in enumerate(CARDS):
    x = X0 + i * (CW + GAP)
    p.append('  <g transform="translate(%d %d)">' % (x, Y0))
    p.append('    <rect x="0.5" y="0.5" width="%d" height="%d" rx="14" fill="#0E141F" stroke="#222C3C"/>' % (CW - 1, CH - 1))
    p.append('    <rect x="0" y="18" width="3" height="26" rx="1.5" fill="%s"/>' % accent)
    p.append('    <text x="22" y="40" font-family="ui-monospace, SFMono-Regular, Consolas, monospace" font-size="16" fill="#5A6478">%s</text>' % num)
    p.append('    <text x="22" y="80" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, PingFang SC, Microsoft YaHei, sans-serif" font-size="22" font-weight="600" fill="#E9EEF8">%s</text>' % title)
    for j, ln in enumerate(lines):
        p.append('    <text x="22" y="%d" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, PingFang SC, Microsoft YaHei, sans-serif" font-size="18" fill="#7E8AA0">%s</text>' % (116 + j * 24, ln))
    p.append('  </g>')
    if i < len(CARDS) - 1:
        cy = Y0 + CH / 2
        p.append('  <line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#39445A" stroke-width="1.5" marker-end="url(#arw)"/>'
                 % (x + CW + 5, cy, x + CW + 20, cy))

p.append('  <line x1="48" y1="306" x2="476" y2="306" stroke="#4D8DFF" stroke-opacity="0.55" stroke-width="2"/>')
p.append('  <text x="48" y="332" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, PingFang SC, Microsoft YaHei, sans-serif" font-size="18" fill="#8FA0BC">主对话侧：Hook 秒回，不阻塞你继续说话</text>')
p.append('  <line x1="504" y1="306" x2="1160" y2="306" stroke="#7E8AA0" stroke-opacity="0.4" stroke-width="2"/>')
p.append('  <text x="504" y="332" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, PingFang SC, Microsoft YaHei, sans-serif" font-size="18" fill="#7E8AA0">后台进程：独立 Worker，只落标题与审计日志，从不改消息</text>')
p.append('</svg>')

OUT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'how-it-works.svg'))
open(OUT, 'w', encoding='utf-8').write('\n'.join(p) + '\n')
print('written', len('\n'.join(p)))
