<p align="center">
  <img src="./assets/readme/hero.svg" width="100%" alt="kk-zcode-title：左侧「原来的标题」是自动命名前的模糊标题（新会话、帮我看看这个、继续修改），右侧是命名后 ZCode 侧边栏里的标题——🔧 邮箱注册｜验证码重发、🐛 支付回调｜重复扣款排查、🚀 邮件服务｜容器化上线">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/ZCode-插件-4D8DFF?style=flat-square&labelColor=0A0D14" alt="ZCode 插件">
  <img src="https://img.shields.io/badge/Python-3.10%2B-4D8DFF?style=flat-square&labelColor=0A0D14" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/%E4%BE%9D%E8%B5%96-%E9%9B%B6%E7%AC%AC%E4%B8%89%E6%96%B9-7DD3A0?style=flat-square&labelColor=0A0D14" alt="零第三方依赖">
  <img src="https://img.shields.io/badge/License-MIT-FFB454?style=flat-square&labelColor=0A0D14" alt="MIT License">
</p>

每轮对话结束后，**kk-zcode-title** 在后台用独立轻量模型读最近 3～5 轮内容，把 ZCode 话题标题维护成稳定的 **「类别 emoji + 对象｜目标」** 格式，例如 `🐛 邮箱注册｜过期修复`。它只写标题这一个字段，不碰消息、权限和其他会话状态，也不会阻塞你继续说话。

> 移植自 [oil-oil/oil-codex-title](https://github.com/oil-oil/oil-codex-title)，适配 ZCode 宿主。

## 效果

同一个话题持续推进时，标题不会跟着最后一句话乱跳，而是稳定在一条主线上：

| 对话进展 | 标题 | 动作 |
| --- | --- | --- |
| 起初在排查邮箱验证码过期 | `🛠️ 邮箱注册修复` | 旧格式，迁移 |
| 补充验证码过期测试并提交 | `🐛 邮箱注册｜过期修复` | rename |
| 又要求补边界测试 | `🐛 邮箱注册｜过期修复` | keep |
| 修完后把服务发上线 | `🚀 邮件服务｜容器化上线` | rename |

三条规则决定了它为什么不乱：

- **keep 优先** —— 已有标题主线准确、格式合规时原样保留。提交、推送、补测试这类补充动作属于现有主线，不会顶掉目标。
- **语言跟随你** —— 按你自己最近几轮说话的语言命名；一句外语或技术名词不会触发语言切换，也不会因为旧标题是另一种语言就来回翻译。
- **类别按产物选** —— 不按最后一个动作切换：定位并修复故障是 🐛，把修好的东西部署上线是 🚀，写新功能才是 🔧。修一个视频发布工具，也仍然属于工具开发而不是内容制作。

> **旧版类别是 8 个，开发类统一用 🧩。** 现版本拆成 🔧 工具开发 / 🐛 故障排查 / 🚀 部署上线 / 📊 数据分析 / 🌐 网络代理。模型遇到 🧩 旧标题会重估一次，**只换 emoji，不改对象与目标的措辞**。

## 快速开始

需要 Python 3.10 及以上，无第三方依赖。

**1. 安装插件**

```bash
cd kk-zcode-title        # 插件根目录
python install.py        # 自动注册、自动启用；卸载用 python install.py --uninstall
```

**2. 重启 ZCode** —— 新注册的插件 Hook 需要重启后才会挂载。

**3. 配置命名模型**

```bash
cd scripts
python kk_zcode_title.py setup                            # 检测 ZCode 已接入厂商 + 真实调用测试 + 挑轻量档模型
python kk_zcode_title.py setup --use <厂商A> --use <厂商B>  # 按优先级写入（厂商名来自上一步的检测结果）
python kk_zcode_title.py doctor                           # 全检：Python、会话库、模型配置、Hook 注册状态
```

之后在话题里正常聊天就行。每轮结束后自动命名，日志在 `~/.zcode/kk-zcode-title/logs/`。

> `doctor` 通过只说明环境就绪，**不能证明 Hook 已经自动触发**。以审计日志里出现 `renamed` / `kept` 记录为准。

## 它怎么工作

<p align="center">
  <img src="./assets/readme/workflow.svg" width="100%" alt="流程：对话结束触发 Stop Hook，入口解析事件后立即派生独立 Worker 并返回空 JSON；Worker 读取会话库最近 3 到 5 轮，调用独立轻量模型判断 keep 或 rename，最后以短事务写回 session.title 并读回核验，同时落审计日志">
</p>

对话结束时会触发 Stop Hook。入口进程只做一件事：解析事件、派生一个独立 Worker、立刻返回空 JSON——所以它**不会拖慢你的对话**。真正的判断在后台完成，模型拿到的只是最近几轮的摘录，不是完整对话记录。

写入走 `session.title` 的短事务，写完立刻读回核验。ZCode 官方没有改名接口，这是当前唯一通道。

## 类别体系

<p align="center">
  <img src="./assets/readme/categories.svg" width="100%" alt="十二个类别 emoji：🎬 内容制作、🔧 工具开发、🐛 故障排查、🚀 部署上线、📊 数据分析、🌐 网络代理、🔎 对比调研、🎨 页面设计、📝 方法整理、📅 日程安排、⚙️ 环境配置、💬 一般讨论">
</p>

| 类别 | 覆盖的工作 |
| --- | --- |
| 🎬 内容制作 | 视频选题、脚本、拍摄、镜头、剪辑、发布。视频返工或修复导出仍属此类 |
| 🔧 工具开发 | 软件功能、代码、插件、Skill、自动化工具的开发与新建 |
| 🐛 故障排查 | 定位和修复已有系统的故障、报错、异常，以恢复原有功能为目标。开发新功能时顺手修缺陷仍归 🔧 |
| 🚀 部署上线 | 容器化、流水线、服务器部署、发布切换，以把成果投入运行为目标 |
| 📊 数据分析 | 日志统计、数据核查、指标分析、报表产出，以从数据得出结论为目标 |
| 🌐 网络代理 | 网络分流、代理配置、端口开通、连通性等网络层事务 |
| 🔎 对比调研 | 模型对比、资料分析、公司岗位研究，以形成判断为目标 |
| 🎨 页面设计 | 页面布局、视觉设计、网站动效与样式还原 |
| 📝 方法整理 | 方法论、操作指南、文档、文章、演示文稿等知识产物。整理还原方法用 📝，实际还原页面用 🎨 |
| 📅 日程安排 | 有明确时间安排的日程、提醒和待办 |
| ⚙️ 环境配置 | 安装、连接、账号或运行环境设置；开发配置工具本身仍用 🔧 |
| 💬 一般讨论 | 有明确对象，但确实不属于以上类型 |

类别未变且已合适时沿用原 emoji。每轮只输出一个 emoji，正文里不再放 emoji，也不加彩色圆点、阶段标签或完成状态。

## 可选：闲置话题归档

归档走独立入口，**不由 Stop Hook 触发，默认关闭**。开启前一律先预览，不会自动动手：

```bash
python scripts/archive_policy.py scan --current-id <当前话题 ID>   # 预览候选，不调用模型
python scripts/archive_policy.py scan --live --limit 10           # 允许对新候选做模型评估（消耗额度）
python scripts/archive_policy.py enable                          # 确认规则与预览后开启
python scripts/archive_policy.py archive <话题 ID>                # 复核通过后归档
python scripts/archive_policy.py protect <话题 ID>                # 永久保护，不再参与评估
python scripts/archive_policy.py pause / status                   # 暂停 / 查看配置
```

- **只写时间戳，不删数据**：归档改的是会话库里的 `time_archived`，会话内容原样保留。
- **永不归档**：当前会话、手动 `protect` 的话题、标题已 `lock` 的话题、子代理会话。
- **评估只做一次**：同一内容版本的判断结果会被缓存；已归档话题不再读取内容、不再调用模型，失败也不自动重试。
- 判定为「已完成」（默认闲置 14 天）或「无待办」（默认 30 天），由模型依据最近 5 轮判断。

## 常用命令

在 `scripts/` 目录下执行，`<话题 ID>` 是 `sess_` 开头的标识，可从 `status` 或审计日志获取。

| 命令 | 作用 |
| --- | --- |
| `python kk_zcode_title.py doctor [--thread <话题 ID>]` | 只读检查运行环境，可附带验证某个话题能否正常读取 |
| `python kk_zcode_title.py status` | 显示配置位置与已记录话题数（密钥显示为 `***`） |
| `python kk_zcode_title.py rename <话题 ID>` | 生成新标题预览，不写入 |
| `python kk_zcode_title.py rename <话题 ID> --apply` | 写入并读回核验 |
| `python kk_zcode_title.py pause` / `resume` | 暂停 / 恢复自动命名 |
| `python kk_zcode_title.py lock <话题 ID>` / `unlock` | 固定当前标题 / 恢复自动命名 |
| `python kk_zcode_title.py setup` | 检测 ZCode 已接入的模型厂商，并真实测试推荐模型 |
| `python kk_zcode_title.py configure --model <模型> --base-url <地址> --api-key <密钥>` | 手动指定 OpenAI 兼容或 anthropic 协议接口 |

不想敲命令也可以直接对 ZCode 说：「预览这个话题的新标题」「固定这个话题的标题」「暂停 / 恢复自动命名」「换命名模型 / 加一个兜底厂商」「预览可以归档的闲置话题」。

## 命名模型与兜底

命名模型由插件直连 OpenAI 兼容接口，**与 ZCode 客户端使用的模型配置互不影响**，需要单独配置 API key（推荐 flash / turbo 之类的轻量档）。

`setup` 会读取 ZCode 已接入厂商的明文 API key 与协议，为每家启发式挑一个轻量模型并真实调用一次微型请求验证可用性。你可以用重复的 `--use` 把它们排成一条兜底链：

```bash
python kk_zcode_title.py setup --use <厂商A> --use <厂商B> --use <厂商C>
```

当前一家额度耗尽时，链上的下一家自动接管；失败的厂商冷却 30 分钟后恢复。写入配置前会再次真实测试，测试失败不落盘。

## 已知边界

- **直接写 ZCode 私有会话库是当前唯一的改名通道。** ZCode 升级若调整表结构，`doctor` 会报告 `db_status: error`，届时按下方「回滚」处理。
- **内置标题生成器与本插件的写入共存。** 实测已结束的会话不会被覆盖；进行中会话的表现以日志为准。
- **归档默认关闭。** 需要显式 `enable` 才生效，且只写时间戳、不删数据，细节见上方「可选：闲置话题归档」。
- **失败时保留原标题。** 命令失败不会写坏标题，先按 `doctor` 的报告处理（会话库不可读、模型未配置、网络错误），再重试。

## 回滚

1. **停用**：在 `installed_plugins.json` 中删除本条目，或把 `enabledPlugins` 置为 `false`，然后重启 ZCode。
2. **清数据**：删除 `~/.zcode/kk-zcode-title/`（配置、状态、审计日志都在这里）。
3. **标题无需恢复**：标题本身存在会话库里；想回到 ZCode 内置命名，删除该会话即可重建。

运行数据全部集中在 `~/.zcode/kk-zcode-title/`，插件目录本身不产生任何运行时文件。

## 更多

<details>
<summary><b>单独封装与分发</b></summary>

本插件是一个自包含目录，无第三方依赖（纯标准库），可整体打包分发：

```bash
cd kk-zcode-title 的上级目录
python -c "import shutil; shutil.make_archive('kk-zcode-title', 'zip', root_dir='kk-zcode-title')"
```

- **接收方安装**：解压到任意固定路径（注册后不要移动目录），执行 `python install.py`，重启 ZCode，再跑 `setup` 配置模型。
- **包内容**：`.zcode-plugin/plugin.json`（清单）、`hooks/hooks.json`（Stop Hook）、`scripts/`（主程序 + 适配层 + 归档策略 + 文件锁）、`skills/kk-zcode-title/`（管理技能）、`prompts/naming.md`（命名提示词）、`install.py`。
- **升级**：覆盖插件目录后重跑 `install.py`（注册是幂等的），数据目录不受影响。

</details>

<details>
<summary><b>与 Codex 原版的主要差异</b></summary>

- **会话读写**：不走 App Server 协议，直接读 `~/.zcode/cli/db/db.sqlite`（`message` / `part` 表读对话，`session.title` 写标题，短事务 + 读回核验）。
- **命名模型**：ZCode 没有 headless CLI，无法复用客户端登录额度；改为插件直连 OpenAI 兼容接口，需要单独配置 API key。
- **Stop Hook**：ZCode 的 hook 内联执行（`async` 无效），入口进程立即派生独立 Worker 后返回空 JSON，不阻塞对话。
- **类别体系**：本版扩到 12 类并重估旧 🧩 标题；原版为 5 类。
- **跨平台**：改用 `type: process` 参数向量调用，不再依赖 `commandWindows`。

</details>

## 排查

后台日志只记录状态、标题和用量，不保留完整对话。排查 Hook 派生问题时可以设置环境变量捕获 Worker 堆栈：

```bash
KK_ZCODE_TITLE_DEBUG=<日志路径> python kk_zcode_title.py hook
```

---

[MIT 许可证](LICENSE) · 原项目致敬 [oil-oil/oil-codex-title](https://github.com/oil-oil/oil-codex-title)
