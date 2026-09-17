# kk-zcode-title — README 视觉规范（冻结）

## 项目故事
- **Audience**：中文 ZCode 用户，尤其是同时开很多话题的开发者与 AI 创作者
- **One-sentence value**：每轮对话结束后，后台独立模型把话题标题维护成「类别 emoji + 对象｜目标」，侧边栏一眼可辨
- **Primary proof**：真实的标题前后对照（新会话 → 🔧 邮箱注册｜验证码重发）
- **First successful action**：python install.py → 重启 ZCode → python kk_zcode_title.py setup
- **Visual theme**：暖米白纸感 + 深墨绿墨色，排版驱动，全程无渐变、无阴影、无深色底

## 调色板
| 角色 | 值 | 用在哪 |
| --- | --- | --- |
| 纸底 | `#F4F3ED` | 所有画布的底色 |
| 白色卡片 | `#FFFFFF` | 「现在」侧卡片、类别胶囊 |
| 灰卡片 | `#EAEAE3` | 「原来的标题」侧卡片 |
| 深绿反白 | `#21382E` | 仅流程图一处 |
| 主墨色 | `#193A2B` | 标题、类别名 |
| 强调绿 | `#397B51` | 高亮词、箭头、卡片小标题 |
| 次要文字 | `#62766A` | 副标题、页脚说明 |
| 弱文字 | `#778177` / `#7B857B` | 灰卡片标签 / 「原来的标题」正文 |
| 分隔线 | `#E3EAE1` / `#D1D7CD` | 白卡 / 灰卡 |
| 箭头 | `#76A287` / `#89B69C` | 浅底 / 深绿反白面板 |
| 淡色行底 | `#E8F1E7` `#EFF2FA` `#F6EEF4` | 三行一组，循环使用 |

反白面板配色：底 `#21382E`，正文 `#F4F2EC`，次要 `#B9CEC2`，小标题 `#A8C1B2`。

## 字体
- 正文：`-apple-system, BlinkMacSystemFont, Segoe UI, PingFang SC, Microsoft YaHei, sans-serif`
- emoji：`Apple Color Emoji, Segoe UI Emoji, Noto Color Emoji, sans-serif`
- 字重：主标题 700，卡片小标题 600，正文 400。不使用 mono。

## 形状
- 画布圆角 22，流程图 24；卡片 14；行底 9；胶囊 16

## Motif（唯一复用动机）
「标题胶囊」= 一个类别 emoji + 全角分隔符「｜」+ 对象 / 目标。
只出现在 hero 的「现在」三行和类别网格；不做壁纸式重复。

## 构图
克制的编辑感。信息靠字号与留白分层，不靠边框、色块或阴影。

## 资产
| 文件 | 画布 | 用途 |
| --- | --- | --- |
| assets/readme/hero.svg | 1200×440 | 第一屏：名称 + 一句话 + 前后对照板 |
| assets/readme/workflow.svg | 1200×260 | 深绿反白：一轮结束 → 入口秒回 → 独立模型 → 写回核验 |
| assets/readme/categories.svg | 1200×384 | 12 个类别胶囊网格 |

三张全部是纯 SVG，没有位图，没有浏览器渲染步骤。emoji 由阅读者的系统彩色 emoji 字体渲染，
与参考仓库 oil-oil/oil-codex-title 的做法一致。

## 重建
```bash
cd assets/readme && python source/build.py     # 生成三张 SVG
python source/preview.py 2                     # 可选：渲染 PNG 预览到 %TEMP%
```

设计令牌集中在 `source/theme.py`，改配色只改这一个文件。
