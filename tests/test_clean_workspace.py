#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""clean_workspace.py 单元测试：识别并清理缓存/临时文件，不触碰普通文件。"""

import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import clean_workspace as cw

PASS = 0
FAIL = 0
TOTAL = 0
_TMP_DIRS = []


def make_tmp_dir():
    tmp_root = os.path.join(ROOT, ".tmp", "test_clean_workspace")
    os.makedirs(tmp_root, exist_ok=True)
    d = tempfile.mkdtemp(dir=tmp_root)
    _TMP_DIRS.append(d)
    return d


def expect(name, cond, detail=""):
    global PASS, FAIL, TOTAL
    TOTAL += 1
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"  [FAIL] {name} {detail}")


def test_collect():
    d = make_tmp_dir()
    # 缓存/临时文件
    os.makedirs(os.path.join(d, "__pycache__"))
    os.makedirs(os.path.join(d, ".tmp"))
    open(os.path.join(d, "a.pyc"), "w", encoding="utf-8").write("x")
    open(os.path.join(d, "b.tmp"), "w", encoding="utf-8").write("x")
    # 普通文件应保留
    open(os.path.join(d, "keep.py"), "w", encoding="utf-8").write("x")
    open(os.path.join(d, "keep.md"), "w", encoding="utf-8").write("x")

    paths = cw.collect(root=d)
    rels = [os.path.relpath(p, d).replace("\\", "/") for p in paths]
    expect("clean+ 识别 __pycache__", any("__pycache__" in r for r in rels), rels)
    expect("clean+ 识别 .tmp", any(r == ".tmp" for r in rels), rels)
    expect("clean+ 识别 pyc", any(r == "a.pyc" for r in rels), rels)
    expect("clean+ 识别 tmp", any(r == "b.tmp" for r in rels), rels)
    expect("clean- 保留普通文件", not any(r in ("keep.py", "keep.md") for r in rels), rels)


def test_clean():
    d = make_tmp_dir()
    os.makedirs(os.path.join(d, "__pycache__"))
    open(os.path.join(d, "a.pyc"), "w", encoding="utf-8").write("x")
    open(os.path.join(d, "keep.py"), "w", encoding="utf-8").write("x")

    for p in cw.collect(root=d):
        if os.path.isdir(p):
            shutil.rmtree(p)
        else:
            os.remove(p)

    expect("clean+ 删除后缓存不存在", not os.path.exists(os.path.join(d, "__pycache__")), "")
    expect("clean+ 删除后 pyc 不存在", not os.path.exists(os.path.join(d, "a.pyc")), "")
    expect("clean- 普通文件保留", os.path.exists(os.path.join(d, "keep.py")), "")


test_collect()
test_clean()

for d in _TMP_DIRS:
    shutil.rmtree(d, ignore_errors=True)

print(f"\nPASS={PASS} FAIL={FAIL}")
if FAIL > 0:
    sys.exit(1)
