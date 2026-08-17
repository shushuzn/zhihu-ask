#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_gbt_refs.py 单元测试：GB/T 7714-2015 参考文献合规检查"""

import os
import subprocess
import sys
import tempfile

import testutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import check_gbt_refs as gbt

PASS = 0
FAIL = 0
TOTAL = 0


def expect(name, cond, detail=""):
    global PASS, FAIL, TOTAL
    TOTAL += 1
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"  [FAIL] {name} {detail}")


GOOD = """# 测试报告

正文引用两处[1][2]，编号连续。

**参考文献（GB/T 7714-2015）**
[1] 郭璞, 注. 山海经·南山经[M/OL]. 四库全书本. [2026-08-11]. https://example.com/a.

[2] 谭其骧. 论五藏山经的地域范围[C]//中国科技史探索. 上海: 上海古籍出版社, 1982.
"""

# ---- 正向用例 ----
hard, warn = gbt.check(GOOD)
expect("good+ 合规报告零硬伤", not hard, f"hard={hard}")
expect("good+ 合规报告零提示", not warn, f"warn={warn}")

# ---- 负向：无参考文献块 ----
hard, warn = gbt.check("纯文本无参考文献")
expect("bad- 无参考文献块", any(h[1] == "硬伤" and h[2] == "无参考文献块" for h in hard))

# ---- 负向：编号跳号 ----
hard, warn = gbt.check("正文[1][2]。\n\n**参考文献**\n[1] 甲. 书一[M]. 京: 社, 2000.\n[3] 乙. 书二[M]. 京: 社, 2001.")
expect("bad- 编号跳号(1,3)", any(h[2] == "文献编号不连续" for h in hard))

# ---- 负向：缺类型标识 ----
hard, warn = gbt.check("正文[1]。\n\n**参考文献**\n[1] 甲. 书一. 京: 社, 2000.")
expect("bad- 缺类型标识", any(h[2] == "缺文献类型标识" for h in hard))

# ---- 负向：条目间缺空行（渲染黏连）----
hard, warn = gbt.check("正文[1][2]。\n\n**参考文献**\n[1] 甲. 书一[M]. 京: 社, 2000.\n[2] 乙. 书二[M]. 京: 社, 2001.")
expect("bad- 条目间缺空行", any(h[2] == "文献条目间缺空行" for h in hard), f"hard={hard}")
hard, warn = gbt.check("正文[1][2]。\n\n**参考文献**\n[1] 甲. 书一[M]. 京: 社, 2000.\n\n[2] 乙. 书二[M]. 京: 社, 2001.")
expect("good- 条目间空行不误报", not any(h[2] == "文献条目间缺空行" for h in hard), f"hard={hard}")

# ---- 负向：电子资源缺引用日期 ----
hard, warn = gbt.check("正文[1]。\n\n**参考文献**\n[1] 甲. 书一[M/OL]. https://example.com/a.")
expect("bad- 电子资源缺日期", any(h[2] == "电子资源缺引用日期" for h in hard))

# ---- 负向：正文引注悬空 ----
hard, warn = gbt.check("正文[5]。\n\n**参考文献**\n[1] 甲. 书一[M]. 京: 社, 2000.")
expect("bad- 正文引注悬空[5]", any(h[2] == "正文引注无对应文献" for h in hard))

# ---- 负向：文献未被引用 ----
hard, warn = gbt.check("正文[1]。\n\n**参考文献**\n[1] 甲. 书一[M]. 京: 社, 2000.\n[2] 乙. 书二[M]. 京: 社, 2001.")
expect("bad- 文献[2]未被引用", any(h[2] == "文献未被正文引用" for h in hard))

# ---- 参考来源清单模式：正文无 [n] 引注时，报告模式下仍须逐条引用 ----
LIST_MODE = """# 报告正文（不标来源括注）

**参考文献（GB/T 7714-2015）**
[1] 甲. 书一[M]. 京: 社, 2000.

[2] 乙. 书二[M]. 京: 社, 2001.
"""
hard, warn = gbt.check(LIST_MODE)
expect("list+ 清单模式报正文无引注", any(h[2] == "正文无引注" for h in hard), f"hard={hard}")

# ---- 负向：正文引注编号不连续 ----
hard, warn = gbt.check("正文[1][3]。\n\n**参考文献**\n[1] 甲. 书一[M]. 京: 社, 2000.\n[2] 乙. 书二[M]. 京: 社, 2001.\n[3] 丙. 书三[M]. 京: 社, 2002.")
expect("bad- 正文引注跳号[1,3]", any(h[2] == "正文引注编号不连续" for h in hard))

# ---- 提示级：转引未标注中间文献 ----
hard, warn = gbt.check("正文[1]。\n\n**参考文献**\n[1] 甲. 书一[M]. 见: .")
expect("warn+ 转引无中间文献", any(w[2] == "转引未标注中间文献" for w in warn))
# 正常转引不误报（中文书名）
hard, warn = gbt.check("正文[1]。\n\n**参考文献**\n[1] 甲. 书一[M]. 见: 钦定皇舆西域图志: 卷八[M]. 四库全书本.")
expect("warn- 正常转引不误报", not any(w[2] == "转引未标注中间文献" for w in warn))

# ---- 提示级：标题未标注国标 ----
hard, warn = gbt.check("正文[1]。\n\n**参考文献**\n[1] 甲. 书一[M]. 京: 社, 2000.")
expect("warn+ 标题只需参考文献", not any(w[2] == "参考文献标题未标注国标" for w in warn))

# ---- 笔记模式：文献段「来源:」行 ----
NOTE_OK = """#标签1 #标签2 #主题/x

笔记标题

正文内容[1][2]。

来源:
[1] 甲. 书一[M]. 京: 社, 2000.

[2] 乙. 书二[EB/OL]. (2026-01-01)[2026-08-13]. https://example.com/b.
来源类型: 一手
"""
hard, warn = gbt.check(NOTE_OK, note_mode=True)
expect("note+ 来源段零硬伤", not hard, f"hard={hard}")

# 笔记模式：文献须与正文 [n] 一一对应（b8a26a3 起笔记同报告强制对应）
NOTE_SHORT = """#标签1 #标签2 #主题/x

笔记标题

正文内容[1]。

来源:
[1] 甲. 书一[M]. 京: 社, 2000.

[2] 乙. 书二[EB/OL]. (2026-01-01)[2026-08-13]. https://example.com/b.
来源类型: 一手
"""
hard, warn = gbt.check(NOTE_SHORT, note_mode=True)
expect("note- 文献[2]未被引用仍报", any(h[2] == "文献未被正文引用" for h in hard), f"hard={hard}")

# 笔记模式：悬空引注仍拦截
hard, warn = gbt.check("正文[9]。\n\n来源:\n[1] 甲. 书一[M]. 京: 社, 2000.\n\n来源类型: 一手", note_mode=True)
expect("note- 悬空引注仍报", any(h[2] == "正文引注无对应文献" for h in hard), f"hard={hard}")

# 笔记模式：条目间缺空行仍报
hard, warn = gbt.check("正文。\n\n来源:\n[1] 甲. 书一[M]. 京: 社, 2000.\n[2] 乙. 书二[M]. 京: 社, 2001.\n\n来源类型: 一手", note_mode=True)
expect("note- 缺空行仍报", any(h[2] == "文献条目间缺空行" for h in hard), f"hard={hard}")

# 报告模式不认「来源:」段（防报告正文行首"来源:"误判；仅 ## 参考文献 有效）
hard, warn = gbt.check("正文\n\n来源: 网络转载\n[1] 甲. 书一[M]. 京: 社, 2000.")
expect("note- 报告模式不认来源段", any(h[2] == "无参考文献块" for h in hard), f"hard={hard}")

# ---- CLI 冒烟 ----
good_path = testutil.mktestfile(suffix=".md")
with open(good_path, "w", encoding="utf-8") as f:
    f.write(GOOD)
rc = subprocess.call([sys.executable, os.path.join(ROOT, "tools", "check_gbt_refs.py"),
                      "--file", good_path], stdout=subprocess.DEVNULL)
expect("cli+ 合规文件 RC=0", rc == 0)
os.unlink(good_path)

bad_doc = "正文[1][3]。\n\n**参考文献**\n[1] 甲. 书一[M]. 京: 社, 2000.\n[3] 乙. 书二[M]. 京: 社, 2001."
bad_path = testutil.mktestfile(suffix=".md")
with open(bad_path, "w", encoding="utf-8") as f:
    f.write(bad_doc)
rc = subprocess.call([sys.executable, os.path.join(ROOT, "tools", "check_gbt_refs.py"),
                      "--file", bad_path], stdout=subprocess.DEVNULL)
expect("cli- 违规文件 RC=1", rc == 1)
os.unlink(bad_path)

print(f"\n==== check_gbt_refs 回归测试：PASS={PASS} FAIL={FAIL} ====")
sys.exit(1 if FAIL else 0)
