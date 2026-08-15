
"""
内部文件保护公共模块（zhihu-ask 项目专用）

定义"不应进入公开仓库的内部文件"模式与判断函数，供 git_protect.py（提交前拦截）
与 health_check.py（体检）共用——单一真相源，避免两处清单漂移。

用法：
    from internal_files import is_internal
    is_internal("plan.md")                  # True
    is_internal("research/x/report.md")     # True
    is_internal("tools/init.example.json")  # False（公开示例）
"""

INTERNAL_PATTERNS = [
    "plan.md",
    "research/",
    "docs/PLAN__ARCHIVE.md",
    ".codebuddy/",
    ".workbuddy/",
    ".commit_msg.tmp",
    ".desc.tmp.txt",
]

# 临时 config 含知乎问题原文（隐私红线），需前缀 + 后缀双重限定。
# 点分隔与下划线分隔两种命名都要覆盖：实战用的是 init_meta.json / keywords_meta.json，
# 此前仅匹配 "tools/init." 导致 git_protect 与 .gitignore 双双漏防。
# 必须同时限定 .json 后缀——只用前缀会误伤 tools/init_research.py 等核心工具脚本。
INTERNAL_CONFIG_PREFIXES = (
    "tools/init.",
    "tools/init_",
    "tools/keywords.",
    "tools/keywords_",
    "tools/start.",
    "tools/start_",
)

PUBLIC_EXCEPTIONS = [
    "tools/init.example.json",
    "tools/keywords.example.json",
    "tools/start.example.json",
]

def is_internal(path):
    """判断路径是否为不应进入公开仓库的内部文件。"""
    p = path.replace("\\", "/")
    if p in PUBLIC_EXCEPTIONS:
        return False
    if p.endswith(".json") and p.startswith(INTERNAL_CONFIG_PREFIXES):
        return True
    return any(
        p == pat.rstrip("/") or p.startswith(pat)
        for pat in INTERNAL_PATTERNS
    )
