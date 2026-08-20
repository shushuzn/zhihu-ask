# -*- coding: utf-8 -*-
"""报告文件定位共享（zhihu-ask 质检链专用）。

收敛 tools/quality_check.py / tools/check_report_structure.py /
tools/check_ai_voice.py 三处的 resolve_target 重复实现。
"""

import os
import sys


def resolve_report_target(argv, tool_name, extra_usage=""):
    """解析 --file / --slug（互为别名）到 report.md 绝对路径。

    ``--slug <slug>`` 等价于 ``--file research/<slug>/report.md``。
    未提供路径或文件不存在即打印用法并退出码 1（保持既有行为）。
    """
    filepath = None
    if "--file" in argv:
        idx = argv.index("--file")
        if idx + 1 < len(argv):
            filepath = argv[idx + 1]
    if not filepath and "--slug" in argv:
        idx = argv.index("--slug")
        if idx + 1 < len(argv):
            root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            filepath = os.path.join(root, "research", argv[idx + 1], "report.md")
    if not filepath or not os.path.exists(filepath):
        print(f"用法: python tools/{tool_name} (--file <文件> | --slug <slug>){extra_usage}")
        if filepath:
            print(f"  [错误] 文件不存在: {filepath}")
        sys.exit(1)
    return filepath
