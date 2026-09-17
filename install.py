#!/usr/bin/env python3
"""kk-zcode-title 安装/卸载脚本。

用法（在插件根目录执行）：
  python install.py              # 复制安装到 ~/.zcode/plugins/kk-zcode-title 并注册（推荐）
  python install.py --dev        # 开发模式：直接注册当前目录，改代码即时生效
  python install.py --uninstall  # 移除注册与已安装副本；数据目录保留并打印路径

安装位置在 ZCode 用户目录，与开发目录分离；配置修改前自动备份到系统临时目录。
安装/升级后需重启 ZCode。
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import uuid
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parent
INSTALL_ROOT = Path.home() / ".zcode" / "plugins" / "kk-zcode-title"
PLUGIN_ID = "kk-zcode-title@local"
REGISTRY = Path.home() / ".zcode" / "cli" / "plugins" / "installed_plugins.json"
CONFIG = Path.home() / ".zcode" / "cli" / "config.json"
DATA_DIR = Path.home() / ".zcode" / "kk-zcode-title"
EXCLUDE = shutil.ignore_patterns("__pycache__", "*.pyc", ".git", ".gitignore")


def backup(path: Path) -> Path | None:
    if not path.exists():
        return None
    target = Path(tempfile.gettempdir()) / f"kk-zcode-title-backup-{uuid.uuid4().hex[:8]}-{path.name}"
    shutil.copy2(path, target)
    return target


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def register(install_path: Path, version: str) -> None:
    registry = read_json(REGISTRY, {"version": 1, "plugins": []})
    registry.setdefault("plugins", [])
    entry = {
        "id": PLUGIN_ID, "name": "kk-zcode-title", "marketplace": "local",
        "version": version, "installPath": str(install_path),
        "installedAt": "2026-09-17T00:00:00.000Z", "updatedAt": "2026-09-17T00:00:00.000Z",
        "scope": "user", "source": {"source": str(install_path)},
    }
    registry["plugins"] = [p for p in registry["plugins"] if p.get("id") != PLUGIN_ID]
    registry["plugins"].append(entry)
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY.write_text(json.dumps(registry, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    config = read_json(CONFIG, {})
    config.setdefault("plugins", {}).setdefault("enabledPlugins", {})[PLUGIN_ID] = True
    CONFIG.write_text(json.dumps(config, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def install(dev: bool) -> int:
    manifest = read_json(SOURCE_ROOT / ".zcode-plugin" / "plugin.json", {})
    if not manifest.get("name"):
        print("错误：缺少 .zcode-plugin/plugin.json")
        return 1
    if sys.version_info < (3, 10):
        print("错误：需要 Python 3.10+")
        return 1

    if dev:
        target = SOURCE_ROOT
    else:
        if INSTALL_ROOT.resolve() == SOURCE_ROOT.resolve():
            target = SOURCE_ROOT
        else:
            if INSTALL_ROOT.exists():
                shutil.rmtree(INSTALL_ROOT)
            shutil.copytree(SOURCE_ROOT, INSTALL_ROOT, ignore=EXCLUDE)
            target = INSTALL_ROOT

    backups = [str(b) for b in (backup(REGISTRY), backup(CONFIG)) if b]
    register(target, manifest.get("version", "0"))
    mode = "开发模式（注册当前目录）" if dev else f"已安装到 {INSTALL_ROOT}"
    print(f"已注册并启用 {PLUGIN_ID}；{mode}")
    if backups:
        print(f"配置备份（系统临时目录）：{'、'.join(backups)}")
    print("请重启 ZCode 生效；首次使用执行 scripts/kk_zcode_title.py setup 配置命名模型。")
    return 0


def uninstall() -> int:
    backup(REGISTRY)
    backup(CONFIG)
    registry = read_json(REGISTRY, {"plugins": []})
    registry["plugins"] = [p for p in registry.get("plugins", []) if p.get("id") != PLUGIN_ID]
    REGISTRY.write_text(json.dumps(registry, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    config = read_json(CONFIG, {})
    config.get("plugins", {}).get("enabledPlugins", {}).pop(PLUGIN_ID, None)
    CONFIG.write_text(json.dumps(config, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    if INSTALL_ROOT.exists() and INSTALL_ROOT.resolve() != SOURCE_ROOT.resolve():
        shutil.rmtree(INSTALL_ROOT)
        print(f"已删除安装副本 {INSTALL_ROOT}")
    print(f"已移除注册；重启 ZCode 后停止自动命名。")
    print(f"数据目录保留在 {DATA_DIR}（含 API key 配置），确认弃用后可手动删除。")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="kk-zcode-title 安装/卸载")
    parser.add_argument("--dev", action="store_true", help="开发模式：注册当前目录，不复制")
    parser.add_argument("--uninstall", action="store_true", help="移除插件注册与安装副本")
    args = parser.parse_args()
    return uninstall() if args.uninstall else install(args.dev)


if __name__ == "__main__":
    raise SystemExit(main())
