
"""
微信公众号检索包装工具（zhihu-ask 项目专用）

解决 PowerShell 命令行向 Python 传递中文参数乱码的问题：
绕开命令行传参，改为从 UTF-8 关键词文件读取。

用法:
    python tools/wechat_search.py --keywords tools/keywords.json --days 30
    python tools/wechat_search.py --keywords tools/keywords.json --time-range YYYY-MM-DD YYYY-MM-DD

keywords.json 格式:
    {
      "queries": ["<主题词> 突破", "<主题词> 产业化"],
      "count": 10
    }

输出: 每个关键词的搜索结果（标题 / 公众号 / 时间 / 摘要 / 链接），UTF-8。

重试: 默认对搜狗验证码 / 限流类错误自动退避重试（最多 3 次，间隔 5s/10s）；
      退避后仍受限则明确标注「关键词受限」而非静默空结果。传 --no-retry 可关闭。
"""

import sys
import json
import os
import re
import time
import urllib.request
from html import unescape
from datetime import datetime, timezone, timedelta

import channel_state as cs

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# 与 tools/web_search.py 相同的处理：Windows 下 ssl 加载系统证书存储失败时
# C 层直接向 stderr 打印噪音（不走 warnings）。用 certifi 的 CA bundle 指定
# SSL_CERT_FILE 使其改走文件证书（须在 fetch_wechat_meta 等 urlopen 之前）。
try:
    import certifi as _certifi
    os.environ.setdefault("SSL_CERT_FILE", _certifi.where())
except ImportError:
    pass

# wechat-article-search 技能脚本所在目录。
# 优先使用环境变量 WECHAT_ARTICLE_SEARCH_SCRIPTS 指定；未设置时回退到仓库根同级的
# .codebuddy 插件默认安装路径。跨机器 / 环境部署请设置该环境变量。
_SKILL_ENV = os.environ.get("WECHAT_ARTICLE_SEARCH_SCRIPTS")


def _normalize_skill_path(p):
    """归一化环境变量路径为 Windows 可识别形式（纯函数）。

    实测踩坑：Git Bash 里 export WECHAT_ARTICLE_SEARCH_SCRIPTS
    为 /c/Users/... 时，Windows Python 的 os.path.exists 判定 False（路径风格
    不识别），导致「未找到 sogou_search.py」。把 /c/... 与 /C:/... 转成 c:/... /
    C:/...（Windows 驱动器大小写不敏感）。原生 Windows 路径原样返回。
    """
    m = re.match(r"^/([a-zA-Z]):(.*)$", p)
    if m:
        return m.group(1) + ":" + m.group(2)
    m = re.match(r"^/([a-zA-Z])/(.*)$", p)
    if m:
        return m.group(1) + ":/" + m.group(2)
    return p


SKILL_PATHS = [_normalize_skill_path(_SKILL_ENV)] if _SKILL_ENV else []
SKILL_PATHS.append(
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        ".codebuddy", "plugins", "marketplaces", "cb_teams_marketplace",
        "plugins", "deep-research", "skills", "wechat-article-search", "scripts",
    )
)
sogou = None
for p in SKILL_PATHS:
    script = os.path.join(p, "sogou_search.py")
    if os.path.exists(script):
        import importlib.util
        spec = importlib.util.spec_from_file_location("sogou_search", script)
        sogou = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sogou)
        break

SOGOU_AVAILABLE = sogou is not None
if not SOGOU_AVAILABLE:
    print("[降级] 未找到 sogou_search.py（可设 WECHAT_ARTICLE_SEARCH_SCRIPTS 指向技能 scripts 目录）")
    print("       自动降级为 ddgs 检索 site:mp.weixin.qq.com（实测可行，无需安装）")


# ---- ddgs 降级检索（sogou_search.py 缺失时）--------------------------------
# 实测：ddgs 搜「site:mp.weixin.qq.com <关键词>」可命中真实公众号文章链接，
# 再用 urllib 抓文章页补标题/公众号名（微信 PC 页结构：h1#activity-name / a#js_name）。
_DDGS_QUERY_TMPL = "site:mp.weixin.qq.com {}"
_WECHAT_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def fetch_wechat_meta(url, timeout=8):
    """抓取微信文章页，返回 (标题, 公众号名)；失败返回 (None, None)。"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _WECHAT_UA})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            html = resp.read().decode("utf-8", "ignore")
    except Exception:
        return None, None
    m = re.search(r'<h1[^>]*id="activity-name"[^>]*>(.*?)</h1>', html, re.S)
    title = _strip_html(m.group(1)) if m else None
    n = re.search(r'id="js_name"[^>]*>(.*?)</', html, re.S)
    name = re.sub(r"\s+", " ", n.group(1)).strip() if n else None
    return (title or None), (name or None)


def _simplify_query(q):
    """去掉常见虚词/动作词后重试（DDG 对中文 site: 查询敏感，实测词序与虚词影响命中）。"""
    for w in ("怎么样", "怎么看", "为什么", "如何", "值得", "发布", "上市", "开售",
              "评测", "解析", "解读", "对比", "分析", "是否", "的", "了"):
        q = q.replace(w, " ")
    return " ".join(q.split())


def search_fallback(q, count, fetch_titles=True, workers=6):
    """ddgs site:mp.weixin.qq.com 降级检索，归一化为搜狗格式记录。

    原词失败自动用简化词重试一次；fetch_titles=True 时对命中文章并行抓取真实
    标题/公众号名（ThreadPoolExecutor 并发，每条约 1-3 秒，串行是主要瓶颈；
    用户反馈检索慢后由串行改并行），抓取失败回退 ddgs 原标题。
    """
    from web_search import search as ddgs_search
    last_err = None
    for qq in (q, _simplify_query(q)):
        try:
            items = ddgs_search(_DDGS_QUERY_TMPL.format(qq), max_results=count)
        except Exception as e:
            last_err = e
            continue
        hits = [it for it in items if "mp.weixin.qq.com" in it.get("href", "")]
        out = []
        if fetch_titles and hits:
            import concurrent.futures as cf
            with cf.ThreadPoolExecutor(max_workers=workers) as ex:
                metas = list(ex.map(
                    lambda it: fetch_wechat_meta(it.get("href", "")), hits))
            for it, (title, account) in zip(hits, metas):
                out.append({
                    "title": title or it.get("title", "") or "（标题未获取，点链接查看）",
                    "account": account or "",
                    "time": "",
                    "digest": it.get("body", ""),
                    "sogou_link": it.get("href", ""),
                })
        else:
            for it in hits:
                out.append({
                    "title": it.get("title", "") or "（标题未获取，点链接查看）",
                    "account": "",
                    "time": "",
                    "digest": it.get("body", ""),
                    "sogou_link": it.get("href", ""),
                })
        return out
    raise RuntimeError(f"ddgs 检索失败（原词与简化词均未命中）：{last_err}")


# ---- 解析结果防御性归一化 -------------------------------------------------
# 上游 sogou_search.py 用正则 / HTML 结构提取搜狗微信结果，站内改版极易失效，
# 返回畸形记录（裸 HTML 字符串、缺字段字典、标签残留在标题/摘要中）。本层在消费端
# 做防御：① 非字典记录直接丢弃并记录原因；② 文本字段剥离 HTML 标签与实体；
# ③ 标题与公众号均空视为噪声丢弃；④ 原始有内容但无一有效记录 → 判定为解析结构漂移，
# 合成错误（而非静默「真无结果」），避免坏解析污染通道 ledger。
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_EXPECTED_KEYS = ("title", "account", "time", "digest", "sogou_link")
_TEXT_FIELDS = ("title", "account", "digest")


def _strip_html(value):
    """剥离 HTML 标签并反转义；非字符串先转字符串。"""
    if not isinstance(value, str):
        value = "" if value is None else str(value)
    value = _HTML_TAG_RE.sub("", value)
    value = unescape(value)
    value = _WS_RE.sub(" ", value).strip()
    return value


def _normalize_record(raw, idx, stats):
    """单条记录归一化；返回干净 dict 或 None（丢弃）。"""
    if not isinstance(raw, dict):
        stats["dropped"] += 1
        stats["drop_reasons"].append(f"#{idx}: 非字典记录(类型 {type(raw).__name__})")
        return None
    # 错误契约透传：含 error 键的记录原样保留
    if "error" in raw:
        return raw
    clean = {}
    for k in _EXPECTED_KEYS:
        v = raw.get(k, "")
        clean[k] = _strip_html(v) if k in _TEXT_FIELDS else ("" if v is None else str(v))
    # 标题或公众号任一非空才算有效记录
    if not clean["title"] and not clean["account"]:
        stats["dropped"] += 1
        stats["drop_reasons"].append(f"#{idx}: 标题与公众号均为空")
        return None
    return clean


def _normalize_results(results):
    """归一化整批结果；返回 (归一化列表, 统计)。保留错误契约与空列表语义。"""
    stats = {"raw": 0, "kept": 0, "dropped": 0, "drop_reasons": []}
    if not isinstance(results, list):
        # 上游返回非列表（字符串 / None / 异常对象）→ 原始 0 条，交由调用方判漂移
        return [], stats
    stats["raw"] = len(results)
    # 错误契约：首条为 {"error": ...} 直接透传，不归一化
    if results and isinstance(results[0], dict) and "error" in results[0]:
        return results, stats
    out = []
    for i, r in enumerate(results):
        nr = _normalize_record(r, i, stats)
        if nr is not None:
            out.append(nr)
            stats["kept"] += 1
    return out, stats


def _report_stats(q, stats):
    dropped = stats.get("dropped", 0)
    if dropped > 0:
        reasons = "; ".join(stats.get("drop_reasons", [])[:3])
        print(f"[解析] 关键词「{q}」丢弃 {dropped} 条异常记录（保留 {stats['kept']}/{stats['raw']}）：{reasons}")


def _search(q, search_type, page, time_from, time_to):
    """包装上游检索 + 防御性归一化 + 漂移检测。"""
    raw = sogou.search_sogou(q, search_type, page, time_from, time_to)
    norm, stats = _normalize_results(raw)
    # 解析结构漂移：原始有内容但无一有效记录 → 合成错误，避免误判「真无结果」。
    # 注意：若上游主动返回 error 契约（如验证码 / 限流），则属「可恢复错误」而非漂移，
    # 不应被覆盖——否则验证码错误会被误判为「页面结构变化」，导致重试逻辑永不触发。
    has_error_contract = bool(norm) and isinstance(norm[0], dict) and "error" in norm[0]
    if stats["raw"] > 0 and stats["kept"] == 0 and not has_error_contract:
        norm = [{"error": f"解析到 0 条有效记录（原始 {stats['raw']} 条），疑似搜狗页面结构变化"}]
    _report_stats(q, stats)
    return norm


# ---- 验证码 / 限流自动重试 -------------------------------------------------
# 搜狗微信对高频或异常会话会返回验证码页面（"请输入验证码"/antispider），
# sogou_search.search_sogou 将其统一包装为 [{"error": "触发验证码，请稍后重试"}]。
# 这类错误是「可恢复的临时限流」，退避等待后通常可解除；本层在包装层自动重试，
# 避免单关键词因瞬时限流而直接空结果。空结果（[]）视为「真无结果」不重试，
# 非限流类明确错误也不重试，防止误把真实缺失当限流反复轰炸。
RETRYABLE_HINTS = ("触发验证码", "antispider", "请稍后重试", "Error:", "timeout", "Connection", "timed out")


def _is_recoverable_error(results):
    """判断 search_sogou 返回是否为可重试的限流 / 网络错误。"""
    if not results or not isinstance(results[0], dict) or "error" not in results[0]:
        return False
    msg = results[0]["error"]
    return any(h in msg for h in RETRYABLE_HINTS)


def search_with_retry(q, search_type, page, time_from, time_to,
                      max_retries=3, backoff=(5, 10), sleep=time.sleep):
    """带退避重试的公众号检索；返回 (results, retried, status)。

    status:
      'ok'     —— 拿到非错误结果
      'empty'  —— 首轮即为空（视为真无结果，不重试）
      'error'  —— 非限流类的明确错误（单次返回即带 error，不重试）
      'blocked'—— 重试耗尽仍受限于验证码 / 网络错误
    retried: 实际额外重试次数（不含首次尝试）。
    """
    def _classify(results, retried):
        if not results:
            return results, retried, "empty"
        if isinstance(results[0], dict) and "error" in results[0]:
            return results, retried, "error"
        return results, retried, "ok"

    results = _search(q, search_type, page, time_from, time_to)
    if not _is_recoverable_error(results):
        return _classify(results, 0)
    # 限流 / 网络错误 → 指数退避重试
    retried = 0
    while retried < max_retries - 1:
        wait = backoff[retried] if retried < len(backoff) else backoff[-1]
        sleep(wait)
        retried += 1
        results = _search(q, search_type, page, time_from, time_to)
        if not _is_recoverable_error(results):
            return _classify(results, retried)
    return results, retried, "blocked"


def parse_args(argv):
    args = {"keywords_file": None, "days": None, "time_range": None, "output": None,
            "no_retry": False, "slug": None, "parallel": 4}
    i = 0
    while i < len(argv):
        if argv[i] == "--keywords" and i + 1 < len(argv):
            args["keywords_file"] = argv[i + 1]
            i += 2
        elif argv[i] == "--days" and i + 1 < len(argv):
            args["days"] = int(argv[i + 1])
            i += 2
        elif argv[i] == "--time-range" and i + 2 < len(argv):
            args["time_range"] = (argv[i + 1], argv[i + 2])
            i += 3
        elif argv[i] == "--output" and i + 1 < len(argv):
            args["output"] = argv[i + 1]
            i += 2
        elif argv[i] == "--slug" and i + 1 < len(argv):
            args["slug"] = argv[i + 1]
            i += 2
        elif argv[i] == "--parallel" and i + 1 < len(argv):
            args["parallel"] = max(1, int(argv[i + 1]))
            i += 2
        elif argv[i] == "--no-retry":
            args["no_retry"] = True
            i += 1
        else:
            i += 1
    return args


def _fallback_search(q, count):
    """降级模式单关键词检索；返回 (results, error_msg)，异常不抛出。"""
    try:
        return search_fallback(q, count), None
    except Exception as e:
        return None, str(e)

def main():
    args = parse_args(sys.argv[1:])
    if not args["keywords_file"] or not os.path.exists(args["keywords_file"]):
        print("ERROR: 请提供 --keywords <json文件>")
        sys.exit(1)

    with open(args["keywords_file"], "r", encoding="utf-8") as f:
        cfg = json.load(f)
    queries = cfg.get("queries", [])
    count = cfg.get("count", 10)

    now = int(datetime.now(timezone.utc).timestamp())
    if args["time_range"]:
        time_from = int(datetime.strptime(args["time_range"][0], "%Y-%m-%d").replace(
            tzinfo=timezone.utc).timestamp())
        time_to = int(datetime.strptime(args["time_range"][1], "%Y-%m-%d").replace(
            tzinfo=timezone.utc).timestamp())
    elif args["days"]:
        time_from = now - args["days"] * 86400
        time_to = now
    else:
        time_from = now - 365 * 86400
        time_to = now

    print("=" * 60)
    print(f"微信公众号检索 | 时间范围: {datetime.fromtimestamp(time_from)} ~ {datetime.fromtimestamp(time_to)}")
    print(f"关键词数: {len(queries)} | 每词返回: {count}")
    print("=" * 60)

    out_lines = []
    out_lines.append("# 公众号检索素材库")
    out_lines.append("")
    out_lines.append(f"> 时间范围：{datetime.fromtimestamp(time_from).strftime('%Y-%m-%d')} ~ {datetime.fromtimestamp(time_to).strftime('%Y-%m-%d')}")
    out_lines.append(f"> 检索时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    out_lines.append("")

    total_hits = 0

    # 降级模式加速（用户反馈检索慢）：多关键词并行检索，
    # 结果按原顺序输出，落盘格式不变。
    fallback_results = None
    if not SOGOU_AVAILABLE and len(queries) > 1:
        import concurrent.futures as cf
        fallback_results = {}
        with cf.ThreadPoolExecutor(max_workers=args["parallel"]) as ex:
            futs = {ex.submit(_fallback_search, q, count): q for q in queries}
            for f in cf.as_completed(futs):
                fallback_results[futs[f]] = f.result()

    for q in queries:
        print("\n" + "#" * 60)
        print(f"## 关键词: {q}")
        print("#" * 60)
        out_lines.append(f"## 关键词：{q}")
        out_lines.append("")
        if not SOGOU_AVAILABLE:
            # 降级模式：ddgs site:mp.weixin.qq.com（无重试，ddgs 自带后端容错链+简化词重试）
            if fallback_results is not None:
                results, ferr = fallback_results[q]
            else:
                results, ferr = _fallback_search(q, count)
            if ferr:
                print(f"⚠ 关键词受限：{ferr}")
                out_lines.append(f"（关键词受限：{ferr}；建议稍后补跑或改用 Web 通道）")
                out_lines.append("")
                continue
            retried = 0
            status = "ok" if results else "empty"
        elif args["no_retry"]:
            results = _search(q, "article", 1, time_from, time_to)
            if results and isinstance(results[0], dict) and "error" in results[0]:
                status, retried = "blocked", 0
            elif not results:
                status, retried = "empty", 0
            else:
                status, retried = "ok", 0
        else:
            results, retried, status = search_with_retry(
                q, "article", 1, time_from, time_to)

        if status == "blocked":
            msg = results[0]["error"] if (results and isinstance(results[0], dict) and "error" in results[0]) else "检索受限"
            print(f"⚠ 关键词受限：{msg}（已重试 {retried} 次仍受限）")
            out_lines.append(f"（关键词受限：{msg}；已重试 {retried} 次仍受限，建议稍后补跑或改用 Web 通道）")
            out_lines.append("")
            continue
        if not results:
            print("（无结果）")
            out_lines.append("（无结果）")
            out_lines.append("")
            continue
        if isinstance(results[0], dict) and "error" in results[0]:
            print("ERROR:", results[0]["error"])
            out_lines.append(f"（检索出错：{results[0]['error']}）")
            out_lines.append("")
            continue
        if retried:
            print(f"（重试 {retried} 次后恢复）")
        for r in results[:count]:
            title = r.get("title", "")
            account = r.get("account", "")
            ts = r.get("time", "")
            digest = r.get("digest", "")
            link = r.get("sogou_link", "")
            total_hits += 1
            print(f"- [{title}]")
            if account:
                print(f"  公众号: {account}")
            if ts:
                print(f"  时间: {ts}")
            if digest:
                print(f"  摘要: {digest}")
            if link:
                print(f"  链接: {link}")

            out_lines.append(f"- **{title}**")
            if account:
                out_lines.append(f"  - 公众号：{account}")
            if ts:
                out_lines.append(f"  - 时间：{ts}")
            if digest:
                out_lines.append(f"  - 摘要：{digest}")
            if link:
                out_lines.append(f"  - 链接：{link}")
        out_lines.append("")

    if args["output"]:
        outdir = os.path.dirname(args["output"])
        if outdir and not os.path.isdir(outdir):
            os.makedirs(outdir, exist_ok=True)
        with open(args["output"], "w", encoding="utf-8") as f:
            f.write("\n".join(out_lines))
        print(f"\n已写入素材库: {args['output']}")
        # 落盘即自动登记通道 A：写到标准 research/<slug>/gathered_wechat.md 即登记，
        # 无需手动 mark_channel（仍可用 --slug 显式指定；否则从输出路径反推）。
        slug = args["slug"] or cs.derive_slug_from_out(args["output"])
        if slug:
            status = "done" if total_hits else "empty"
            note = f"命中 {total_hits} 条" if total_hits else "通道 A 零命中"
            if cs.mark(slug, "A", status, note=note):
                print(f"[自动登记] 通道 A（公众号）: {status} —— {note}")
            else:
                print(f"[提示] 未找到 research/{slug}/.progress.json，跳过通道 A 自动登记（请先 research_start）")

if __name__ == "__main__":
    main()
