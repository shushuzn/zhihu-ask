"""env_loader.py 回归测试：.env 解析与优先级（12 项）。

覆盖：加载键值、注释/空行跳过、引号剥除、已存在环境变量不覆盖、
重复键首个优先、文件缺失/空返回 0、不抛异常。

运行：python tests/test_env_loader.py
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import env_loader as el

PASS = 0
FAIL = 0


def expect(label, got, must_be):
    global PASS, FAIL
    if got == must_be:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL {label}: got {got!r}, expected {must_be!r}")


def write_tmp(content):
    fd, path = tempfile.mkstemp(suffix=".env")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def test_basic():
    p = write_tmp("KEY1=value1\nKEY2=value2\n")
    n = el.load_dotenv(p)
    expect("基础加载2键", n, 2)
    expect("值正确", os.environ.get("KEY1"), "value1")
    os.environ.pop("KEY1", None)
    os.environ.pop("KEY2", None)
    os.unlink(p)


def test_comments_blanks():
    p = write_tmp("# 注释\n\nKEY=value\n  \n# 另一注释\n")
    n = el.load_dotenv(p)
    expect("注释空行跳过", n, 1)
    expect("值正确", os.environ.get("KEY"), "value")
    os.environ.pop("KEY", None)
    os.unlink(p)


def test_quotes():
    p = write_tmp('Q1="quoted val"\nQ2=\'single\'\nQ3=bare\n')
    n = el.load_dotenv(p)
    expect("三键加载", n, 3)
    expect("双引号剥除", os.environ.get("Q1"), "quoted val")
    expect("单引号剥除", os.environ.get("Q2"), "single")
    expect("无引号保留", os.environ.get("Q3"), "bare")
    for k in ("Q1", "Q2", "Q3"):
        os.environ.pop(k, None)
    os.unlink(p)


def test_no_overwrite():
    p = write_tmp("EXISTING=file_value\n")
    os.environ["EXISTING"] = "real_env"
    n = el.load_dotenv(p)
    expect("环境变量优先", os.environ.get("EXISTING"), "real_env")
    expect("不覆盖仍计数0", n, 0)
    os.environ.pop("EXISTING", None)
    os.unlink(p)


def test_dup_first_wins():
    p = write_tmp("DUP=first\nDUP=second\n")
    n = el.load_dotenv(p)
    expect("重复键计数1", n, 1)
    expect("首个优先", os.environ.get("DUP"), "first")
    os.environ.pop("DUP", None)
    os.unlink(p)


def test_missing_and_empty():
    expect("文件缺失返回0", el.load_dotenv("/nonexistent/.env"), 0)
    p = write_tmp("")
    expect("空文件返回0", el.load_dotenv(p), 0)
    os.unlink(p)


def test_invalid_lines():
    p = write_tmp("=novalue\nKEY=\nNOVAL\n  =x\n")
    n = el.load_dotenv(p)
    expect("非法行跳过（KEY= 空值算合法）", n, 1)
    expect("空值键存在", os.environ.get("KEY"), "")
    os.environ.pop("KEY", None)
    os.unlink(p)


if __name__ == "__main__":
    test_basic()
    test_comments_blanks()
    test_quotes()
    test_no_overwrite()
    test_dup_first_wins()
    test_missing_and_empty()
    test_invalid_lines()
    print(f"TOTAL: PASS={PASS} FAIL={FAIL}")
