"""运行时导入冒烟测试：逐个真实导入所有模块，捕获符号级错误。"""
import importlib
import os
import sys

sys.path.insert(0, os.getcwd())

SKIP = (".venv", "node_modules", "__pycache__", "frontend", ".git", "scripts")


def collect():
    mods = []
    for root, _dirs, files in os.walk("."):
        norm = root.replace("\\", "/")
        if any(s in norm for s in SKIP):
            continue
        for f in files:
            if f.endswith(".py") and f != "__init__.py":
                p = os.path.join(root, f).replace("\\", "/")
                if p.startswith("./"):
                    p = p[2:]
                mods.append(p[:-3].replace("/", "."))
    return sorted(mods)


def main():
    mods = collect()
    fails = []
    for m in mods:
        try:
            importlib.import_module(m)
        except Exception as e:
            line = (str(e).splitlines() or [""])[0]
            fails.append((m, type(e).__name__, line))
    print(f"TOTAL {len(mods)} modules, {len(fails)} failed")
    for m, t, e in fails:
        print(f"  FAIL {m}: {t}: {e[:90]}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
