"""channel_state.py 回归测试：登记纯函数的正向/负向用例（13 项）。

覆盖：derive_slug_from_out（标准/非research/反斜杠路径）、load/save 往返、
mark 校验（非法通道/非法status/进度文件缺失返回False）、done/empty/skip 写入、
note 保留语义、channels_done 字典创建与多通道共存。

运行：python tests/test_channel_state.py
"""
import os
import sys
import json
import shutil
import tempfile
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import channel_state as cs

PASS = 0
FAIL = 0


def expect(label, got, must_be):
    global PASS, FAIL
    if got == must_be:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL {label}: got {got!r}, expected {must_be!r}")


def make_slug(prog=None):
    """在 ROOT/research/<slug> 造临时 slug 目录（channel_state 的 load/mark 解析到此路径）。
    返回 (slug_dir, slug)。可选预置 .progress.json。"""
    slug = "cs_" + uuid.uuid4().hex[:10]
    slug_dir = os.path.join(ROOT, "research", slug)
    os.makedirs(slug_dir, exist_ok=True)
    if prog is not None:
        with open(os.path.join(slug_dir, ".progress.json"), "w", encoding="utf-8") as f:
            json.dump(prog, f, ensure_ascii=False, indent=2)
    return slug_dir, slug


def cleanup(slug_dir):
    shutil.rmtree(slug_dir, ignore_errors=True)


# ---- derive_slug_from_out ----
expect("slug+ 标准路径", cs.derive_slug_from_out("research/foo/gathered_wechat.md"), "foo")
expect("slug- 非research路径", cs.derive_slug_from_out("/tmp/x/gathered_wechat.md"), None)
expect("slug+ 反斜杠路径", cs.derive_slug_from_out("research\\foo\\gathered_arxiv.md"), "foo")
expect("slug- 空串", cs.derive_slug_from_out(""), None)

# ---- load/save 往返 ----
d, s = make_slug()
p, prog = cs.load(s)
expect("load- 文件不存在返回None", prog, None)
cleanup(d)

d, s = make_slug({"stage": "phase1_done", "data": {}})
p, prog = cs.load(s)
expect("load+ 读回", prog.get("stage"), "phase1_done")
cs.save(p, {"stage": "x", "data": {"k": 1}})
p2, prog2 = cs.load(s)
expect("save+ 写回可读", prog2.get("data", {}).get("k"), 1)
cleanup(d)

# ---- mark 校验 ----
d, s = make_slug({"stage": "phase1_done", "data": {}})
try:
    cs.mark(s, "Z", "done")
    expect("mark- 非法通道抛错", False, True)
except ValueError:
    expect("mark- 非法通道抛错", True, True)
try:
    cs.mark(s, "A", "bogus")
    expect("mark- 非法status抛错", False, True)
except ValueError:
    expect("mark- 非法status抛错", True, True)
cleanup(d)

d, s = make_slug(None)  # 无 .progress.json
expect("mark- 进度文件缺失返回False", cs.mark(s, "A", "done", note="x"), False)
cleanup(d)

# ---- done / empty / skip 写入 ----
d, s = make_slug({"stage": "phase1_done", "data": {}})
expect("mark+ done有note", cs.mark(s, "A", "done", note="命中10"), True)
_, prog = cs.load(s)
expect("mark+ done落盘", prog["data"]["channels_done"]["A"], {"status": "done", "note": "命中10"})
cleanup(d)

d, s = make_slug({"stage": "phase1_done", "data": {}})
expect("mark+ empty有note", cs.mark(s, "P", "empty", note="无有效素材"), True)
_, prog = cs.load(s)
expect("mark+ empty落盘", prog["data"]["channels_done"]["P"]["status"], "empty")
cleanup(d)

d, s = make_slug({"stage": "phase1_done", "data": {}})
expect("mark+ skip有note", cs.mark(s, "E", "skip", note="ima未连接"), True)
_, prog = cs.load(s)
expect("mark+ skip落盘", prog["data"]["channels_done"]["E"]["status"], "skip")
cleanup(d)

# ---- note 保留语义（二次登记不传note则保留旧note）----
d, s = make_slug({"stage": "phase1_done", "data": {}})
cs.mark(s, "A", "done", note="初次note")
cs.mark(s, "A", "done")  # 不传 note
_, prog = cs.load(s)
expect("note+ 二次不传保留旧note", prog["data"]["channels_done"]["A"]["note"], "初次note")
cleanup(d)

# ---- 多通道共存 ----
d, s = make_slug({"stage": "phase1_done", "data": {"channels_done": {"E": {"status": "skip", "note": "x"}}}})
cs.mark(s, "A", "done", note="y")
_, prog = cs.load(s)
cd = prog["data"]["channels_done"]
expect("multi+ 多通道共存", cd.get("E", {}).get("note"), "x")
expect("multi+ 新通道写入", cd.get("A", {}).get("note"), "y")
cleanup(d)

# ---- file_to_channel / files_for ----
m = cs.file_to_channel()
expect("map+ arxiv文件归P", m.get("gathered_arxiv.md", (None,))[0], "P")
expect("map+ preprints文件归P", m.get("gathered_preprints.md", (None,))[0], "P")
expect("map+ wechat归A", m.get("gathered_wechat.md", (None,))[0], "A")
expect("map+ 五通道全覆盖", sorted({v[0] for v in m.values()}), ["A", "B", "C", "E", "P"])
expect("files+ P双文件", sorted(cs.files_for("P")), ["gathered_arxiv.md", "gathered_preprints.md"])
expect("files+ A单文件", cs.files_for("A"), ["gathered_wechat.md"])
expect("files+ F无文件(已移除)", cs.files_for("F"), [])

# ---- 领域分类与通道计划 ----
expect("dtype+ 数学→学术科研", cs.classify_domain("数学/概率论/测度论"), "学术科研")
expect("dtype+ 物理→学术科研", cs.classify_domain("物理/宇宙学/流体动力学"), "学术科研")
expect("dtype+ 财经→财经时政", cs.classify_domain("财经/电力设备/电网投资"), "财经时政")
expect("dtype+ AI→科技产业", cs.classify_domain("AI/大模型/后训练"), "科技产业")
expect("dtype+ 机器人→科技产业", cs.classify_domain("机器人/具身智能/运动控制"), "科技产业")
expect("dtype+ 空领域默认科技产业", cs.classify_domain(""), "科技产业")
p_acad = {ch: p for ch, p, _ in cs.channel_plan("学术科研")}
expect("plan+ 学术科研 P为P0", p_acad.get("P"), "P0")
expect("plan+ 学术科研 A为P2", p_acad.get("A"), "P2")
p_fin = {ch: p for ch, p, _ in cs.channel_plan("财经时政")}
expect("plan+ 财经时政 A为P0", p_fin.get("A"), "P0")
expect("plan+ 财经时政 P为P2", p_fin.get("P"), "P2")
expect("plan+ 通用P0含B", all(p_acad.get(c) == "P0" for c in ("B",)), True)

# ---- 环境级未配置通道（自动 skip，跨研究共享） ----
import os as _os
_saved = _os.environ.get("ZHIHU_ASK_UNCONFIGURED_CHANNELS")
_os.environ.pop("ZHIHU_ASK_UNCONFIGURED_CHANNELS", None)
expect("env+ 默认 E/C 未配置", cs.env_unconfigured_channels(), ("E", "C"))
_os.environ["ZHIHU_ASK_UNCONFIGURED_CHANNELS"] = "C"
expect("env+ 覆盖为仅 C", cs.env_unconfigured_channels(), ("C",))
_os.environ["ZHIHU_ASK_UNCONFIGURED_CHANNELS"] = ""
expect("env+ 空=全部已配置", cs.env_unconfigured_channels(), ())
_os.environ["ZHIHU_ASK_UNCONFIGURED_CHANNELS"] = "E,X,c "
expect("env+ 非法项过滤并大写", cs.env_unconfigured_channels(), ("E", "C"))
if _saved is None:
    _os.environ.pop("ZHIHU_ASK_UNCONFIGURED_CHANNELS", None)
else:
    _os.environ["ZHIHU_ASK_UNCONFIGURED_CHANNELS"] = _saved
expect("env+ skip 条目 status", cs.env_skip_entry("E")["status"], "skip")
expect("env+ skip 条目 note 含未配置", "未配置" in cs.env_skip_entry("C")["note"], True)

# ---- 并发写安全（omniscientist 案例：search_all 并行子进程与手动登记
#      同时 mark 同一 .progress.json 曾致 JSON 叠加损坏）----
import subprocess as _sp

def _worker_mark_cmd(slug, channel):
    return [sys.executable, "-c",
            ("import sys; sys.path.insert(0, 'tools'); "
             "import channel_state as cs; "
             f"ok = cs.mark({slug!r}, {channel!r}, 'done', note='并发{channel}'); "
             "sys.exit(0 if ok else 1)")]

d_c, s_c = make_slug({"stage": "phase1_done", "data": {}})
procs = [_sp.Popen(_worker_mark_cmd(s_c, ch), cwd=ROOT,
                   stdout=_sp.PIPE, stderr=_sp.PIPE) for ch in ("E", "A", "B", "P")]
rcs = [p.wait(timeout=60) for p in procs]
expect("conc+ 4 并发 mark 全成功", rcs, [0, 0, 0, 0])
p_c, prog_c = cs.load(s_c)
cd_c = (prog_c or {}).get("data", {}).get("channels_done", {})
expect("conc+ 文件仍为合法 JSON 且 4 通道齐",
       (prog_c is not None and all(ch in cd_c for ch in ("E", "A", "B", "P"))),
       True)
expect("conc- 无锁残留", not os.path.exists(p_c + ".lock"), True)
cleanup(d_c)

# 锁的互斥性：持锁期间第二次获取应等待（不破坏临界区）
d_l, s_l = make_slug({"stage": "phase1_done", "data": {}})
p_l, _ = cs.load(s_l)
lock1 = cs.file_lock(p_l, timeout=1.0)
lock1.__enter__()
lock2 = cs.file_lock(p_l, timeout=0.3)
lock2.__enter__()   # 超时应放行（保守策略）而非死锁
lock2.__exit__(None, None, None)
lock1.__exit__(None, None, None)
expect("lock- 锁释放后无残留", not os.path.exists(p_l + ".lock"), True)
cleanup(d_l)

print(f"\n==== channel_state 回归测试：PASS={PASS} FAIL={FAIL} ====")

if __name__ == "__main__":
    sys.exit(1 if FAIL else 0)
