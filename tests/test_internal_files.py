"""internal_files.is_internal 回归测试：隐私红线单一真相源（27 项）。

覆盖核心陷阱：
- INTERNAL_PATTERNS 直配（plan.md / research/ / docs/PLAN__ARCHIVE.md / .codebuddy/ / .workbuddy/ / .commit_msg.tmp / .desc.tmp.txt）
- 临时 config 双重限定（前缀 tools/init./init_/keywords./keywords_/start./start_ + 必须 .json 后缀）
- PUBLIC_EXCEPTIONS 豁免（*.example.json）
- 关键负例：tools/init_research.py 等核心脚本不得被前缀误伤
- Windows 反斜杠路径归一化

is_internal 是 git_protect（pre-commit 拦截）与 health_check 共用的隐私守卫，
此处回归直接守护「内部文件（plan.md / research/ 含问题原文）不会被静默泄漏到公开仓库」。
本模块为纯函数测试，无需文件系统。

运行：python tests/test_internal_files.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import internal_files as inf

PASS = 0
FAIL = 0


def expect(label, got, must_be):
    global PASS, FAIL
    if got == must_be:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL {label}: got {got!r}, expected {must_be!r}")


# ---- 直配内部模式（True）----
expect("internal+ plan.md", inf.is_internal("plan.md"), True)
expect("internal+ research 子文件", inf.is_internal("research/foo/report.md"), True)
expect("internal+ research gathered", inf.is_internal("research/foo/gathered_wechat.md"), True)
expect("internal+ docs 归档", inf.is_internal("docs/PLAN__ARCHIVE.md"), True)
expect("internal+ .codebuddy", inf.is_internal(".codebuddy/hooks/pre-commit"), True)
expect("internal+ .workbuddy", inf.is_internal(".workbuddy/memory/2026-08-11.md"), True)
expect("internal+ commit_msg.tmp", inf.is_internal(".commit_msg.tmp"), True)
expect("internal+ desc.tmp", inf.is_internal(".desc.tmp.txt"), True)

# ---- 临时 config 双重限定（前缀 + .json 后缀 = True）----
expect("internal+ init.json", inf.is_internal("tools/init.json"), True)
expect("internal+ init_meta.json", inf.is_internal("tools/init_meta.json"), True)
expect("internal+ init_ 下划线前缀", inf.is_internal("tools/init_xxx.json"), True)
expect("internal+ keywords.json", inf.is_internal("tools/keywords.json"), True)
expect("internal+ keywords_meta.json", inf.is_internal("tools/keywords_meta.json"), True)
expect("internal+ start.json", inf.is_internal("tools/start.json"), True)
expect("internal+ start_meta.json", inf.is_internal("tools/start_meta.json"), True)
expect("internal+ init.research.json", inf.is_internal("tools/init.research.json"), True)

# ---- Windows 反斜杠归一化 ----
expect("internal+ 反斜杠 research", inf.is_internal(r"research\foo\report.md"), True)
expect("internal+ 反斜杠 codebuddy", inf.is_internal(r".codebuddy\hooks\pre-commit"), True)

# ---- PUBLIC_EXCEPTIONS 豁免（False）----
expect("public- init.example.json", inf.is_internal("tools/init.example.json"), False)
expect("public- keywords.example.json", inf.is_internal("tools/keywords.example.json"), False)
expect("public- start.example.json", inf.is_internal("tools/start.example.json"), False)

# ---- 关键负例：核心脚本不得被前缀误伤（False）----
expect("safe- init_research.py", inf.is_internal("tools/init_research.py"), False)
expect("safe- keywords_research.py", inf.is_internal("tools/keywords_search.py"), False)
expect("safe- start_pipeline.py", inf.is_internal("tools/start_pipeline.py"), False)
expect("safe- init 前缀非json", inf.is_internal("tools/init_helpers/foo.py"), False)

# ---- 一般公开文件（False）----
expect("safe- README", inf.is_internal("README.md"), False)
expect("safe- 核心工具脚本", inf.is_internal("tools/quality_check.py"), False)
expect("safe- mark_channel", inf.is_internal("tools/mark_channel.py"), False)
expect("safe- docs 常规", inf.is_internal("docs/TOOLS.md"), False)
expect("safe- LICENSE", inf.is_internal("LICENSE"), False)
expect("internal+ research 目录本身", inf.is_internal("research"), True)


print(f"TOTAL: PASS={PASS} FAIL={FAIL}")
