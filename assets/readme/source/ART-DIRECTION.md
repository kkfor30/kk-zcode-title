# kk-zcode-title — README 视觉规范（冻结）

## 项目故事
- Audience: 中文 ZCode 用户，尤其是同时开很多话题的开发者与 AI 创作者
- One-sentence value: 每轮对话结束后，后台独立轻量模型把话题标题维护成「类别 emoji + 对象｜目标」，侧边栏一眼可辨
- Primary proof: 真实的标题前后对照（🛠️ 邮箱注册修复 → 🧩 邮箱注册｜修复），以及 keep 稳定性规则
- First successful action: python install.py → 重启 ZCode → python kk_zcode_title.py setup
- Visual theme: 夜间终端 + 会话侧边栏 + 类别 emoji 色板 + 全角分隔符「｜」

## 调色板
| 角色 | 值 |
| --- | --- |
| background | #0A0D14 |
| surface | #0E141F |
| line | #222C3C |
| foreground | #E9EEF8 |
| muted | #7E8AA0 |
| primary（冷蓝，当前模型/写入成功） | #4D8DFF |
| accent（暖橙，仅用于「改名前」） | #FFB454 |

类别色（仅作极轻的点缀，不铺满）：
🎬 #FF7A9C · 🧩 #4D8DFF · 🔎 #7DD3A0 · 🎨 #C08CFF · 📝 #F2C14E · 📅 #5AD2E6 · ⚙️ #9AA7BE · 💬 #8FA6FF

## 字体
- UI: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif
- Mono（命令、ID、元信息、eyebrow）: ui-monospace, "SFMono-Regular", Consolas, monospace

## 形状
- 圆角家族: 8 / 14 / 22
- 描边: 1px #222C3C
- 间距单位: 8

## Motif（唯一复用动机）
「标题胶囊」= 一个类别 emoji + 全角分隔符「｜」+ 对象/目标。
出现在 hero 的侧栏行、类别模块、章节过渡的极小标记；不做壁纸式重复。

## 构图
技术冷峻、克制的留白。侧栏卡片是画面唯一的主体物。不用装饰性边框和重阴影。

## 资产清单
| 文件 | 类型 | 用途 |
| --- | --- | --- |
| assets/readme/hero.webp | 混合合成 → 发布 WebP | 第一屏：名称 + 价值 + 侧栏前后对照 |
| assets/readme/how-it-works.svg | 纯 SVG | Stop Hook → Worker → 模型 → 写回 流程 |
| assets/readme/categories.webp | 纯 SVG 渲染 → 发布 WebP | 12 个类别 emoji 胶囊网格 |
| assets/readme/source/hero-layout.svg | 布局源 | hero 可编辑布局 |
| assets/readme/source/categories-layout.svg | 布局源 | 类别模块可编辑布局 |
| assets/readme/source/hero-bg.webp | GPT 生成 | hero 背景板（原图 1.17 MB → 29 KB） |
| assets/readme/source/category-icons.webp | GPT 生成 | 3D 类别图标，供 hero 的行图标使用（1.42 MB → 101 KB） |

类别模块用系统彩色 emoji 直接渲染成位图，保证所有平台看到同一套字形；类别定义留在
README 表格里，便于检索、翻译与随提示词更新。3D 图标只用在 hero 的三行，因为类别体系
会随命名规则演进（本次已由 8 类扩到 12 类），把它绑到固定的生成图上会很快过时。

## 重建
```bash
cd assets/readme && python source/build.py
```
发布资产统一用 WebP。hero 是混合合成（GPT 背景板 + 3D 图标，用圆角图标卡片方式合成，
不用 screen 叠加——深色物件在 screen 下会消失）。
