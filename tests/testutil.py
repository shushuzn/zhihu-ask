"""测试临时目录/文件工厂（zhihu-ask 项目专用）。

背景：DSH 沙箱环境下 tempfile.mkdtemp / NamedTemporaryFile
创建的目录/文件继承受限 ACL，写入被拒（PermissionError，连 icacls 都无法读取），
导致 tests/run_all.py 大量模块启动即失败。本工具把临时产物统一放到工作区
.tmp/tests/ 下（沙箱允许写入的区域），语义与 mkdtemp/NamedTemporaryFile 对齐：
返回唯一路径、调用方负责清理（shutil.rmtree / os.unlink 照常工作）。

用法（各测试文件顶部 `import testutil`，同目录可直接导入）：

    d = testutil.mktestdir("prefix_")      # 等价 tempfile.mkdtemp(prefix=...)
    p = testutil.mktestfile(suffix=".md")  # 等价 NamedTemporaryFile(delete=False).name
    with open(p, "w", encoding="utf-8") as f:
        f.write(content)

可用环境变量 TEST_TMPDIR 覆盖基座目录（默认 <项目根>/.tmp/tests）。
"""
import os
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.environ.get("TEST_TMPDIR") or os.path.join(ROOT, ".tmp", "tests")


def _ensure_base():
    os.makedirs(BASE, exist_ok=True)
    return BASE


def mktestdir(prefix=""):
    """创建唯一临时目录，返回路径（调用方负责清理）。"""
    base = _ensure_base()
    d = os.path.join(base, prefix + uuid.uuid4().hex[:12])
    os.makedirs(d)
    return d


def mktestfile(prefix="", suffix=""):
    """生成唯一临时文件路径（不创建文件，调用方 open 写入；调用方负责清理）。"""
    base = _ensure_base()
    return os.path.join(base, prefix + uuid.uuid4().hex[:12] + suffix)
