
"""
通道完成态登记核心逻辑（zhihu-ask 项目专用）

把 mark_channel.py 的写入逻辑抽成可 import 的纯函数，供：
  - mark_channel.py（CLI 入口）
  - wechat_search.py（写 gathered_wechat.md 后自动登记通道 A）
  - arxiv_search.py（写 gathered_arxiv.md 后自动登记通道 P；arxiv 归入 P）

设计要点：
  - mark() 仅在 research/<slug>/.progress.json 已存在时才写入，避免凭空创建进度文件。
  - 从标准输出路径 research/<slug>/gathered_*.md 反推 slug，使工具「写到标准位置即自动登记」，
    无需调用方额外传 --slug（仍兼容显式 --slug）。
"""

import os
import json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CHANNEL_ORDER = ["F", "E", "A", "B", "C", "P"]
CHANNEL_NAMES = {
    "F": "flomo 查重",
    "E": "ima 知识库",
    "A": "公众号",
    "B": "Web",
    "C": "领域数据源（企查查/通达信/智慧芽）",
    "P": "学术预印本聚合（arxiv/bioRxiv/浪淘沙/PSSXiv 哲学社科）",
}
CHANNEL_FILE = {
    "E": "gathered_ima.md",
    "A": "gathered_wechat.md",
    "B": "gathered_web.md",
    "C": "gathered_c.md",
    "P": "gathered_preprints.md",
}
# P 通道的多素材文件（arxiv 平台与其余平台分文件落盘，但同属通道 P）
CHANNEL_FILE_MULTI = {
    "P": ("gathered_arxiv.md", "gathered_preprints.md"),
}
VALID_STATUS = ("done", "empty", "skip")


def file_to_channel():
    """生成 gathered 文件 → (通道字母, 通道名) 统一映射（含多文件通道展开）。

    check_progress 等工具据此推导证据校验映射，消除各工具手写
    第三份通道清单导致的维护漂移。F 通道无 gathered 文件，不在此映射。
    """
    m = {}
    for ch, fname in CHANNEL_FILE.items():
        if fname:
            m[fname] = (ch, CHANNEL_NAMES[ch])
    for ch, files in CHANNEL_FILE_MULTI.items():
        for fn in files:
            m[fn] = (ch, CHANNEL_NAMES[ch])
    return m


def files_for(channel):
    """通道的素材文件列表（含多文件通道展开）；无素材文件返回 []。"""
    out = []
    fname = CHANNEL_FILE.get(channel)
    if fname:
        out.append(fname)
    for fn in CHANNEL_FILE_MULTI.get(channel, ()):
        if fn not in out:
            out.append(fn)
    return out


def progress_path(slug):
    return os.path.join(ROOT, "research", slug, ".progress.json")


def load(slug):
    p = progress_path(slug)
    if not os.path.exists(p):
        return p, None
    try:
        with open(p, "r", encoding="utf-8") as f:
            return p, json.load(f)
    except (OSError, ValueError):
        return p, None


def save(path, prog):
    """原子写：写临时文件后 os.replace 替换，避免写一半被读/被并发写叠加。

    配合 file_lock 使用（mark 已包锁）；单独调用时不加锁，仅保证单次写原子。
    """
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(prog, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


class file_lock:
    """跨进程互斥锁（锁文件 O_CREAT|O_EXCL 原子创建）。

    保护 .progress.json 的「读-改-写」临界区：search_all 并行子进程与主代理
    手动登记可能同时写同一进度文件（实测并发导致 JSON 叠加损坏——
    omniscientist-ai-scientist 案例）。用法：

        with file_lock(progress_path(slug)):
            path, prog = load(slug)
            ... 修改 ...
            save(path, prog)

    获取失败（锁已被占）时重试，超时后打印警告并继续（保守策略：
    不阻塞调用方；并发极端场景下宁可最后写入者覆盖，也不无限等待）。
    """

    def __init__(self, path, timeout=15.0, retry=0.05):
        self.lock_path = path + ".lock"
        self.timeout = timeout
        self.retry = retry
        self.fd = None

    def __enter__(self):
        import time
        deadline = time.time() + self.timeout
        while True:
            try:
                self.fd = os.open(self.lock_path,
                                  os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                return self
            except FileExistsError:
                if time.time() > deadline:
                    print(f"[提示] 进度文件锁 {self.lock_path} 获取超时，继续执行（可能并发写）")
                    return self
                time.sleep(self.retry)

    def __exit__(self, exc_type, exc, tb):
        if self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass
            try:
                os.remove(self.lock_path)
            except OSError:
                pass
        return False


def derive_slug_from_out(out_path):
    """从 research/<slug>/gathered_*.md 反推 slug；不匹配则返回 None。

    取「文件名所在目录的最后一级」作为 slug（标准布局 research/<slug>/gathered_*.md）。
    路径须包含 research 段，避免任意路径被误判。
    兼容反斜杠分隔符（Windows 用户传 research\\foo\\gathered_*.md 时
    Linux 环境 os.sep='/' 无法切分——统一把 / 与 \\ 都视为路径分隔符）。
    """
    if not out_path:
        return None
    norm = os.path.normpath(out_path).replace("\\", "/")
    parts = [p for p in norm.split("/") if p]
    if "research" not in parts or len(parts) < 2:
        return None
    return parts[-2]


def mark(slug, channel, status, note=None):
    """登记单通道完成态。成功返回 True；.progress.json 不存在时返回 False（不创建）。

    并发安全：整个读-改-写临界区由 file_lock 保护（search_all 并行子进程
    与手动登记可能同时写；无锁时并发读-改-写会损坏 JSON，见 omniscientist 案例）。
    """
    channel = channel.upper()
    if channel not in CHANNEL_ORDER:
        raise ValueError(f"非法通道 {channel!r}（仅允许 {','.join(CHANNEL_ORDER)}）")
    if status not in VALID_STATUS:
        raise ValueError(f"非法 status {status!r}（仅允许 {','.join(VALID_STATUS)}）")

    path, prog = load(slug)
    if prog is None:
        return False

    with file_lock(path):
        # 锁内重读（等待期间其他进程可能已写入），再合并本次登记
        _, prog = load(slug)
        if prog is None:
            return False
        data = prog.get("data") or {}
        cd = data.get("channels_done") or {}
        if not isinstance(cd, dict):
            cd = {}
        existing = cd.get(channel) if isinstance(cd.get(channel), dict) else {}
        new_note = note if note is not None else (existing.get("note", "") if isinstance(existing, dict) else "")
        cd[channel] = {"status": status, "note": new_note}
        data["channels_done"] = cd
        prog["data"] = data
        save(path, prog)
    return True


# ---------- 领域分类与通道优先级计划（矩阵工具化） ----------

# 领域类型 → 通道优先级（P0/P1/P2）。F 查重与 B Web 为通用 P0，不列出。
DOMAIN_PRIORITY = {
    "学术科研": {"P": "P0", "C": "P1", "A": "P2", "E": "P1"},
    "科技产业": {"P": "P2", "C": "P0", "A": "P1", "E": "P1"},
    "财经时政": {"P": "P2", "C": "P0", "A": "P0", "E": "P1"},
}
DOMAIN_TYPES = ("学术科研", "科技产业", "财经时政")

# 领域判定关键词（子串匹配，命中即归类；多档命中按出现顺序取首个）
DOMAIN_KEYWORDS = {
    "学术科研": ("数学", "物理", "化学", "生物", "医学", "哲学", "社会学", "经济学",
                "量子", "凝聚态", "天文", "考古", "历史", "语言", "心理", "材料科学",
                "理论", "学术", "预印本", "论文", "cs."),
    "科技产业": ("AI", "人工智能", "半导体", "芯片", "机器人", "人形", "具身",
                "3D", "生成", "扩散模型", "大模型", "算力", "软件", "硬件",
                "互联网", "科技", "自动驾驶", "无人机", "新能源车", "储能"),
    "财经时政": ("股票", "股市", "基金", "券商", "银行", "保险", "期货", "宏观",
                "经济", "政策", "财政", "货币", "民生", "消费", "房价", "地产",
                "贸易", "关税", "时政", "新闻", "财经", "上市公司", "指数"),
}


# ---------- 环境级连接器状态（未配置通道自动 skip，跨研究共享） ----------

# 本环境未配置连接器的通道（默认按实况：ima E 与领域连接器 C 未配置）。
# 连接器接入后用环境变量 ZHIHU_ASK_UNCONFIGURED_CHANNELS 覆盖
# （逗号分隔通道字母，如 "C" 表示仅 C 未配置；空字符串 = 全部已配置）。
DEFAULT_ENV_UNCONFIGURED = ("E", "C")


def env_unconfigured_channels():
    """返回本环境未配置连接器的通道元组（环境级，跨研究共享）。

    默认 E/C（ima 与企查查/通达信/智慧芽连接器未配置）——这些通道
    由初始化流程自动登记为 skip，无需逐篇手动检查。
    环境变量 ZHIHU_ASK_UNCONFIGURED_CHANNELS 覆盖默认（逗号分隔；空 = 全部已配置）。
    """
    import os
    raw = os.environ.get("ZHIHU_ASK_UNCONFIGURED_CHANNELS")
    if raw is None:
        return DEFAULT_ENV_UNCONFIGURED
    raw = raw.strip()
    if not raw:
        return ()
    return tuple(ch.upper().strip() for ch in raw.split(",")
                 if ch.strip().upper() in CHANNEL_ORDER)


def env_skip_entry(channel):
    """环境级 skip 登记项：{status: skip, note: 环境未配置原因}。"""
    return {
        "status": "skip",
        "note": f"通道 {channel} 连接器未配置（环境级默认 skip，无需逐篇检查）",
    }


def classify_domain(domain):
    """按领域关键词判定领域类型：返回 学术科研/科技产业/财经时政。

    未命中关键词 → 默认"科技产业"（产业科技主题居多，且 P0 通道可执行性强）；
    调用方可用 --domain-type 显式覆盖。
    """
    if not domain:
        return "科技产业"
    d = domain.lower()
    for dtype, kws in DOMAIN_KEYWORDS.items():
        if any(k.lower() in d for k in kws):
            return dtype
    return "科技产业"


def channel_plan(domain_type):
    """返回领域类型的通道优先级计划：[(通道, 优先级, 通道名), ...]（含通用 P0）。"""
    pri = DOMAIN_PRIORITY.get(domain_type, DOMAIN_PRIORITY["科技产业"])
    plan = [("F", "P0", CHANNEL_NAMES["F"]), ("B", "P0", CHANNEL_NAMES["B"])]
    for ch in ("E", "A", "C", "P"):
        plan.append((ch, pri.get(ch, "P2"), CHANNEL_NAMES[ch]))
    return plan
