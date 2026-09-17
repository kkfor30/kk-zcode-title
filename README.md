# kk-zcode-title

让 ZCode 的话题标题跟上你正在做的事情。每轮对话结束后，后台独立模型参考最近 3～5 轮内容，把标题维护为稳定的 **「类别 emoji + 对象｜目标」** 格式，例如 `🧩 邮箱验证码｜过期排查`。移植自 [oil-oil/oil-codex-title](https://github.com/oil-oil/oil-codex-title)，适配 ZCode 宿主。

## 与 Codex 原版的主要差异

- **会话读写**：不走 App Server 协议，直接读 `~/.zcode/cli/db/db.sqlite`（`message`/`part` 表读对话，`session.title` 写标题，短事务 + 读回核验）。
- **命名模型**：ZCode 没有 headless CLI，无法复用客户端登录额度；改为插件直连 OpenAI 兼容接口（推荐 flash/turbo 轻量档），单独配置 API key。
- **Stop Hook**：ZCode 的 hook 内联执行（`async` 无效），入口进程立即派生独立 Worker 后返回空 JSON，不阻塞对话。
- **跨平台**：`type: process` 参数向量调用，不再依赖 `commandWindows`。

## 安装与配置

1. Python 3.10+（`python --version` 可用）。
2. 在插件根目录执行安装脚本（自动注册、自动启用、备份写入系统临时目录）：

```bash
python install.py        # 安装；python install.py --uninstall 卸载
```

3. 重启 ZCode，然后配置命名模型（初始化向导）：

```bash
cd scripts
python kk_zcode_title.py setup    # 检测 ZCode 已接入厂商 + 真实测试 + 挑轻量模型
python kk_zcode_title.py setup --use "Z.ai - API Key" --use deepseek   # 按优先级写入（可多家兜底）
python kk_zcode_title.py doctor   # 全检
```

4. 新话题里正常聊天，每轮结束后自动命名；日志见 `~/.zcode/kk-zcode-title/logs/`。

## 单独封装与分发

本插件是一个自包含目录，无第三方依赖（纯标准库），可整体打包分发：

```bash
cd kk-zcode-title 的上级目录
python -c "import shutil; shutil.make_archive('kk-zcode-title', 'zip', root_dir='kk-zcode-title')"
```

- **接收方安装**：解压到任意固定路径（注册后不要移动目录），执行 `python install.py`，重启 ZCode，跑 `setup` 配置模型。
- **包内容**：`.zcode-plugin/plugin.json`（清单）、`hooks/hooks.json`（Stop Hook）、`scripts/`（主程序 + 适配层 + 文件锁）、`skills/kk-zcode-title/`（管理技能）、`prompts/naming.md`（命名提示词）、`install.py`。
- **运行数据全部集中在** `~/.zcode/kk-zcode-title/`（配置、状态、审计日志），插件目录本身不产生任何运行时文件；批量操作等临时产物由调用方在系统临时目录自行清理。
- 升级 = 覆盖插件目录后重跑 `install.py`（注册幂等）；数据目录不受影响。

## 日常使用

直接对 ZCode 说：「预览这个话题的新标题」「固定这个话题的标题」「暂停/恢复自动命名」，或手动执行：

```bash
python kk_zcode_title.py rename <话题ID>          # 预览
python kk_zcode_title.py rename <话题ID> --apply  # 写入
python kk_zcode_title.py status / pause / resume
```

## 已知边界

- 直接写 ZCode 私有会话库是当前唯一改名通道；ZCode 升级若调整表结构，`doctor` 会报告 `db_status: error`，届时回滚方式见下。
- 内置标题生成器与插件的写入共存：实测已结束会话不会被覆盖；进行中会话的表现以日志为准。
- 闲置归档功能暂未迁移。

## 回滚

1. 停用：`installed_plugins.json` 删除本条目或 `enabledPlugins` 置 false，重启 ZCode。
2. 清数据：删除 `~/.zcode/kk-zcode-title/`。
3. 标题本身存于会话库，无需恢复；如需恢复 ZCode 内置命名，删除该会话即可重建。

[MIT 许可证](LICENSE) · 原项目致敬 [oil-oil/oil-codex-title](https://github.com/oil-oil/oil-codex-title)
