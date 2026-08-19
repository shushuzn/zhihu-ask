
"""
项目健康自检工具（zhihu-ask 项目专用）

一键验证项目就绪状态，适合新会话启动或排障时运行。
检查项：
  1. Python 环境与脚本可导入
  2. git 仓库状态（分支、远程、跟踪）
  3. pre-commit hook 是否安装
  4. 隐私边界（内部文件是否被 git 跟踪）
  5. 关键文件完整性（模板、文档、工具）

用法：
    python tools/health_check.py
"""

import sys
import os
from glob import glob
import subprocess
import re

from internal_files import is_internal

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

REQUIRED_FILES = [
    "README.md",
    "LICENSE",
    ".gitignore",
    "docs/CONVENTIONS.md",
    "docs/KEYWORDS.md",
    "docs/STYLE_GUIDE.md",
    "docs/TEMPLATE_INDEX.md",
    "docs/TOOLS.md",
    "docs/IMA_INTEGRATION.md",
    "docs/IMA_LIBRARIES.md",
    "templates/research_plan_TEMPLATE.md",
    "templates/research_report_TEMPLATE.md",
    "templates/process_notes_TEMPLATE.md",
    "tools/check_all.py",
    "tools/check_progress.py",
    "tools/check_report_structure.py",
    "tools/check_ai_voice.py",
    "tools/check_gbt_refs.py",
    "tools/check_citation_validity.py",
    "tools/check_latex_syntax.py",
    "tools/check_source_consistency.py",
    "tools/check_consistency.py",
    "tools/clean_workspace.py",
    "tools/channel_state.py",
    "tools/check_flomo_note_refs.py",
    "tools/git_protect.py",
    "tools/health_check.py",
    "tools/init_research.py",
    "tools/install_git_hooks.py",
    "tools/internal_files.py",
    "tools/latex_unicode.py",
    "tools/iter_research.py",
    "tools/jspace_integration.py",
    "tools/ji_call.py",
    "tools/ji_ledger.py",
    "tools/ji_config.py",
    "tools/mark_channel.py",
    "tools/quality_check.py",
    "tools/qc_common.py",
    "tools/qc_conclusion.py",
    "tools/qc_image.py",
    "tools/qc_math.py",
    "tools/qc_ref.py",
    "tools/qc_stance.py",
    "tools/qc_structure.py",
    "tools/qc_title.py",
    "tools/flomo_upload_full.py",
    "tools/rag_build.py",
    "tools/rag_search.py",
    "tools/knowledge_store.py",
    "tools/keywords_db.py",
    "tools/report_images.py",
    "tools/ri_font.py",
    "tools/ri_ai.py",
    "tools/ri_chart.py",
    "tools/ri_inject.py",
    "tools/ri_export.py",
    "tools/report_to_docx.py",
    "tools/report_to_flomo.py",
    "tools/research_start.py",
    "tools/syllogism_check.py",
    "tools/tdx_query.py",
    "tools/wechat_search.py",
    "tools/arxiv_search.py",
    "tools/preprint_search.py",
    "tools/web_search.py",
    "tools/wechat_publish.py",
    "tools/net_check.py",
    "tools/run_pipeline.py",
    "tools/search_all.py",
    "tools/maintain.py",
    "tools/flomo_search.py",
    "tools/note_assemble.py",
    "tools/note_upload.py",
    "tools/web_fetch.py",
    "tools/env_loader.py",
    "docs/architecture.md",
    "docs/JSPACE_OPTIMIZATION.md",
    "templates/note_TEMPLATE.md",
    "tools/init.example.json",
    "tools/keywords.example.json",
    "tools/start.example.json",
    "requirements.txt",
    "tests/run_all.py",
]

def find_missing(files, base):
    """纯函数：返回 base 下不存在的文件列表（关键文件完整性检查核心）。"""
    return [f for f in files if not os.path.exists(os.path.join(base, f))]

# 文档废话模式：带日期的裁定/要求/反馈/新增/固化等注释（规则文档中属历史废话，应删除只留规则）
STALE_DOC_PATTERNS = [
    r"2026-\d{2}-\d{2}\s*用户(裁定|要求|严令|确定|改裁|进一步要求|第三轮要求|重申|二次指出|反馈)",
    r"用户(裁定|要求|严令|确定|改裁|进一步要求|第三轮要求|重申|二次指出|反馈)[（(]?\s*2026-",
    r"\(2026-\d{2}-\d{2}[^)]*用户[^)]*\)",
    r"2026-\d{2}-\d{2}\s*(?:用户硬规则|工具化|实测|加固|升级|核实|新增|固化|反复踩坑|起已弃用|起不再使用|续|修复|由串行改并行|优化|领域矩阵|严格化|改裁|重新评定|回归|扩展|改进|支持|实现|踩坑|缺陷回归)",
]

# 文档废话扫描范围：规则类文档（模板/流程/风格/工具/清单/约定）、脚本（tools/*.py）与测试注释；
# 不含历史变更日志与数据快照。
STALE_DOC_SCAN = [
    "templates", "docs", "skills", "tools", "tests",
]
STALE_DOC_EXCLUDE = ["plan.md", "IMA_LIBRARIES.md", "KEYWORDS.md",
                     "health_check.py", "test_health_check.py", "test_consistency.py"]  # 历史变更日志/数据快照/检测器自身与测试夹具保留


def find_stale_docs(base, patterns, scan_dirs, exclude_names):
    """纯函数：返回 (文件路径, 命中行号) 列表——规则文档中带日期的裁定注释。"""
    regexes = [re.compile(p) for p in patterns]
    hits = []
    for d in scan_dirs:
        root = os.path.join(base, d)
        if not os.path.isdir(root):
            continue
        for dirpath, _, files in os.walk(root):
            for fn in files:
                if not (fn.endswith(".md") or fn.endswith(".py")):
                    continue
                if fn in exclude_names:
                    continue
                fp = os.path.join(dirpath, fn)
                try:
                    with open(fp, encoding="utf-8") as f:
                        lines = f.read().splitlines()
                except Exception:
                    continue
                for i, line in enumerate(lines, 1):
                    if any(r.search(line) for r in regexes):
                        hits.append((os.path.relpath(fp, base), i, line.strip()[:60]))
    return hits

def git_synced(status_out):
    """纯函数：git status --short --branch 输出是否为「与 origin/main 同步」。

    branch 信息位于首行，含 origin/main 且无 ahead/behind 即视为同步。
    """
    return ("origin/main" in status_out
            and "ahead" not in status_out
            and "behind" not in status_out)

def run_git(*args):
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                       text=True, encoding="utf-8")
    return r.returncode, r.stdout.strip(), r.stderr.strip()

def check(name, ok, detail=""):
    status = "OK " if ok else "FAIL"
    print(f"[{status}] {name}" + (f"  ({detail})" if detail else ""))
    return ok

def main():
    print("=" * 60)
    print("zhihu-ask 项目健康自检")
    print("=" * 60)
    all_ok = True

    py_ok = sys.version_info >= (3, 8)
    all_ok &= check("Python 3.8+", py_ok, sys.version.split()[0])

    rc, out, _ = run_git("status", "--short", "--branch")
    branch_info = out.splitlines()[0] if out else "?"
    all_ok &= check("git 仓库状态", rc == 0, branch_info)

    rc, out, _ = run_git("remote", "-v")
    has_remote = "origin" in out
    ssh_detail = "SSH" if "git@github.com" in out else "HTTPS"
    all_ok &= check("远程 origin 已配置", has_remote,
                    out.splitlines()[0] if out else "未配置")

    rc, out, _ = run_git("status", "--short", "--branch")
    synced = git_synced(out)
    all_ok &= check("main 与 origin/main 同步", synced,
                    "ahead/behind" if not synced else "已同步")

    hook = os.path.join(ROOT, ".git", "hooks", "pre-commit")
    hook_ok = os.path.exists(hook)
    all_ok &= check("pre-commit hook 已安装", hook_ok,
                    "未安装，运行 python tools/install_git_hooks.py" if not hook_ok else "")

    rc, out, _ = run_git("ls-files")
    tracked = out.splitlines()
    leaks = [f for f in tracked if is_internal(f)]
    all_ok &= check("内部文件未被 git 跟踪", not leaks,
                    "发现跟踪: " + ", ".join(leaks) if leaks else "")

    missing = find_missing(REQUIRED_FILES, ROOT)
    all_ok &= check("关键文件完整", not missing,
                    "缺失: " + ", ".join(missing) if missing else "")

    stale = find_stale_docs(ROOT, STALE_DOC_PATTERNS, STALE_DOC_SCAN, STALE_DOC_EXCLUDE)
    all_ok &= check("规则文档无历史裁定废话", not stale,
                    "; ".join(f"{f}:{ln}" for f, ln, _ in stale[:5]) if stale else "")

    # 信息性检查（不计入 all_ok）：python-docx 可用性
    try:
        import docx  # noqa: F401
        docx_ok = True
        docx_detail = "已安装"
    except ImportError:
        venv_py = os.path.join(ROOT, "venv", "Scripts", "python.exe")
        if not os.path.exists(venv_py):
            venv_py = os.path.join(ROOT, "venv", "bin", "python")
        docx_ok = os.path.exists(venv_py) and (
            os.path.exists(os.path.join(ROOT, "venv", "Lib", "site-packages", "docx"))
            or bool(glob(os.path.join(ROOT, "venv", "lib", "python*", "site-packages", "docx"))))
        docx_detail = "venv 中可用" if docx_ok else "未安装（report_to_docx 将自动建 venv 安装）"
    check("python-docx 可用（信息）", docx_ok, docx_detail)

    print("=" * 60)
    print("结论: " + ("全部就绪" if all_ok else "存在问题，请按上方 FAIL 项处理"))
    print("=" * 60)
    sys.exit(0 if all_ok else 1)

if __name__ == "__main__":
    main()
