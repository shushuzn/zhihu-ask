# -*- coding: utf-8 -*-
"""控制台编码容错（zhihu-ask 工具链共享）。

Windows 下 stdout/stderr 默认 GBK，任一工具打印含 GBK 不可编码字符
（如 ²/希腊字母/emoji）的正文或报告片段时，strict 模式会抛
UnicodeEncodeError 中断整条流水线。统一为 utf-8 + replace：中文
正常显示，不可编码字符替换为 �/ ?，不中断。

用法：在工具顶层（import 之后、逻辑之前）调用：

    from tools.console_encoding import setup
    setup()
"""

import sys


def setup():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
