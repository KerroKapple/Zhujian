"""静态检查内部 import 是否可解析（基于 AST，不加载第三方依赖）。"""
import ast
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INTERNAL = {"app", "agents", "tools", "core", "models", "repository", "utils", "services", "scripts", "docker"}


def module_exists(mod: str) -> bool:
    """判断点分模块名是否存在对应文件或包。"""
    parts = mod.split(".")
    # 文件 a/b/c.py
    p = ROOT.joinpath(*parts)
    if p.with_suffix(".py").exists():
        return True
    # 包 a/b/c/__init__.py
    if (p / "__init__.py").exists():
        return True
    # 父包里的符号（from a.b import C，其中 C 是 a/b.py 里的类）
    if len(parts) >= 1:
        parent = ROOT.joinpath(*parts[:-1])
        if parent.with_suffix(".py").exists():
            return True
        if (parent / "__init__.py").exists():
            return True
    return False


def check(file: Path):
    try:
        tree = ast.parse(file.read_text(encoding="utf-8"), filename=str(file))
    except Exception as e:
        print(f"[PARSE-ERR] {file.relative_to(ROOT)}: {e}")
        return
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                continue
            mod = node.module or ""
            top = mod.split(".")[0]
            if top not in INTERNAL:
                continue
            # 解析 from mod import name -> 优先看 mod 是否为包/模块
            mod_path = ROOT.joinpath(*mod.split("."))
            mod_ok = mod_path.with_suffix(".py").exists() or (mod_path / "__init__.py").exists()
            if mod_ok:
                continue
            # mod 不是模块，可能 from pkg import submodule
            print(f"[BAD-IMPORT] {file.relative_to(ROOT)}:{node.lineno}: from {mod} import "
                  f"{', '.join(a.name for a in node.names)}")
        elif isinstance(node, ast.Import):
            for a in node.names:
                top = a.name.split(".")[0]
                if top not in INTERNAL:
                    continue
                if not module_exists(a.name):
                    print(f"[BAD-IMPORT] {file.relative_to(ROOT)}:{node.lineno}: import {a.name}")


for f in ROOT.rglob("*.py"):
    if any(part in {".venv", "venv", "__pycache__", ".git"} for part in f.parts):
        continue
    check(f)
