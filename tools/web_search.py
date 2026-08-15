# -*- coding: utf-8 -*-
"""Web 搜索工具（多引擎聚合，zhihu-ask 项目专用）

背景：agent 的 WebSearch 工具不可用（HTTP 402 会员权益验证失败）时，
本工具提供无需 API key 的搜索兜底。

引擎：
  - ddgs       DuckDuckGo 元搜索（网页/新闻，通用首选；反爬时多后端+重试）
  - openalex   OpenAlex 学术论文 API（免费稳定，学术主题质量高）
  - crossref   CrossRef DOI API（免费稳定，学术条目）
  - hn         Hacker News Algolia API（免费稳定，技术社区讨论）
  - auto       默认：依次尝试上述引擎，首个返回非空结果的胜出

加速（用户反馈检索慢后升级）：
  - auto 模式 4 个引擎改为 ThreadPoolExecutor 并行尝试，首个非空结果胜出，
    整体耗时从「串行累加各引擎失败时间」降到「最慢的单引擎时间」；
    仍失败时按查询变体（去引号/截断）重试一轮。
  - 静默 Windows 下 ssl 证书存储加载失败的 warnings（Python 3.12+ 每次
    urllib 请求都会 warn 一次，污染 stderr 并被 PowerShell 误判为错误）。

通用增强：
  1. 多后端容错链（duckduckgo → bing → brave）+ 重试退避（应对瞬时限流/反爬）
  2. 查询变体自动重试：原查询全失败时依次尝试去引号 / 截断超长查询
  3. 低质量域名过滤：过滤图片站/视频站/盗版站/成人站/游戏站等污染源
  4. region 自适应：含中文 → cn-zh，否则 us-en（ddgs 引擎）

用法：
  python tools/web_search.py "关键词" [--max 10] [--news] [--engine auto] [--timelimit year] [--out 文件.md] [--json]
  python tools/web_search.py --queries-file q.json --parallel 4 --out 文件.md   # 多查询并行
    --max          结果条数（默认 10）
    --news         新闻搜索模式（仅 ddgs 支持，默认 text 网页搜索）
    --engine       auto/ddgs/openalex/crossref/hn（默认 auto 聚合）
    --timelimit    day/week/month/year 时间过滤（仅 ddgs，默认不过滤）
    --timeout      单引擎超时秒数（默认 30，仅 auto 并行模式生效）
    --queries-file 多查询 JSON（{"queries": ["q1", ...]} 或纯列表），并行搜索
    --parallel     多查询并行数（默认 4；1=串行），结果按原顺序落盘、通道 B 一次性登记
    --slug         落盘时自动登记通道 B 的 slug（默认从 --out 路径反推）

依赖：pip install ddgs（可选，openalex/crossref/hn 引擎用标准库 urllib 即可）
退出码：0 成功；1 全部查询失败；2 参数错误。
"""
import argparse
import html as htmllib
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import warnings
from datetime import date

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# Windows 下 Python ssl 加载系统证书存储失败时，C 层直接向 stderr 打印
# "failed to load native root certificate ..."（不走 warnings 系统，
# filterwarnings 无法静默）。用 certifi 的 CA bundle 显式
# 指定 SSL_CERT_FILE，使 ssl.create_default_context 走文件证书而非 Windows
# 证书存储——噪音消失且 TLS 验证仍用 Mozilla CA。必须在任何 urlopen 之前设置。
try:
    import certifi as _certifi
    os.environ.setdefault("SSL_CERT_FILE", _certifi.where())
except ImportError:
    pass

# Windows 下 Python 3.12+ 的 ssl.create_default_context() 每次尝试加载
# 系统证书存储，失败即 warnings.warn("failed to load native root certificate...")，
# 污染 stderr 且被 PowerShell 误判为 NativeCommandError。此处静默该特定警告
# （不影响实际 TLS 验证：urllib 仍使用默认 CA 路径）。
warnings.filterwarnings("ignore", message="failed to load native root certificate")

# 敏感配置（TAVILY_API_KEY 等）：优先真实环境变量，其次项目根 .env
# （沙箱下注册表写入被拒，.env 为后备通道；两者都无则 tavily 引擎自动跳过）
try:
    from env_loader import load_dotenv
    load_dotenv()
except ImportError:
    pass

TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "").strip()


BACKENDS = ["duckduckgo", "bing", "brave"]
RETRIES = 1  # ddgs 每后端额外重试次数（总尝试 = RETRIES + 1 轮；由 2 降为 1：
             # 反爬时一轮即可判断成败，多轮只增加空转时间）

# 低质量/无关来源域名（子串匹配主域）：图片/视频/盗版/成人/游戏/小说站等
LOW_QUALITY_DOMAINS = (
    "pinterest.com", "tiktok.com", "youtube.com", "youtu.be", "bilibili.com",
    "oceanofpdf.com", "z-lib.bz", "z-lib.org", "annas-archive", "thepiratebay.org",
    "wowebook.org", "novelfull.in", "lunoxscans.com", "sephiria.net",
    "growagardenscript.dev", "epicwar.com", "buildingguide.app", "xpicvid.org",
    "xxsp39.wiki", "mojira.dev", "minecraft", "mojang.com", "steamcommunity.com",
    "nexusmods.com", "gemini.google.com", "douyin.com", "xx.xxx", "porn", "xvideos",
    "decathlon", "bekafun", "fireandice.com", "rollerenligne", "proskatersplace",
    "jigsawplanet.com", "dreamstime.com", "gettyimages.com", "tr.pinterest",
    "castle.xyz", "hyacinthbloom.com",
    # Gemini/Claude 中文镜像/入口站（Bing 引擎实测污染源，SEO 内容无信息量）
    "gemini-cnblog.com", "gemini-cn.cn", "claudezh.com", "gemini-docs.com",
    "openai-hub.net", "openai-hub.com", "ai-master.cc",
)

CJK_RE = re.compile(r"[\u4e00-\u9fff]")
UA = {"User-Agent": "Mozilla/5.0 (zhihu-ask research agent)"}


# ---------- 通用辅助 ----------

def domain_of(href):
    """提取 URL 主域（去 www. 前缀，小写）。"""
    m = re.search(r"https?://([^/]+)", href or "")
    return (m.group(1).lower() if m else "").replace("www.", "")


def filter_results(items):
    """过滤低质量/无关域名结果。"""
    return [r for r in items
            if not any(d in domain_of(r.get("href", "")) for d in LOW_QUALITY_DOMAINS)]


def pick_region(query):
    """查询含中文 → cn-zh，否则 us-en。"""
    return "cn-zh" if CJK_RE.search(query or "") else "us-en"


def query_variants(query):
    """生成查询变体：原查询 → 去引号 → 截断超长查询（去重保序）。"""
    q = (query or "").strip()
    variants = [q]
    if '"' in q:
        variants.append(q.replace('"', "").strip())
    if len(q) > 80:
        variants.append(q[:80].strip())
    seen, out = set(), []
    for v in variants:
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out


def http_get_json(url, timeout=12):
    """GET 并解析 JSON，失败抛异常。urllib 失败时自动 curl 兜底。

    urllib SSL/代理栈在本机偶发失败（报"无外网出口"），系统 curl 独立栈常可用。
    兜底失败仍抛异常，由调用方容错。"""
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception:
        data = http_get_curl(url, timeout)
        if data is None:
            raise
        return data


def http_get_curl(url, timeout=12):
    """curl 兜底 GET：返回解析后的 JSON 或 None。"""
    try:
        import shutil
        if shutil.which("curl") is None:
            return None
        r = subprocess.run(
            ["curl", "-sL", "--max-time", str(timeout), "-A", UA.get("User-Agent", "Mozilla/5.0"), url],
            capture_output=True, timeout=timeout + 10)
    except Exception:
        return None
    if not r.stdout:
        return None
    try:
        return json.loads(r.stdout.decode("utf-8", "replace"))
    except Exception:
        return None


# ---------- 引擎：ddgs ----------

def search_ddgs(query, max_results=10, news=False, timelimit=None):
    """ddgs 引擎：多后端容错链 + 重试退避。失败/空返回 []。"""
    try:
        from ddgs import DDGS
    except ImportError:
        return []
    regions = [pick_region(query)]
    # 踩坑：ddgs news 模式下 region=cn-zh 常全部无结果
    # （duckduckgo/bing/brave 三后端均 "No results found"），而 us-en 后端
    # bing/brave 正常返回。中文查询 news 模式 cn-zh 失败时回退 us-en 重试一轮。
    if news and regions[0] == "cn-zh":
        regions.append("us-en")
    for attempt in range(RETRIES + 1):
        for region in regions:
            for backend in BACKENDS:
                try:
                    with DDGS() as ddgs:
                        kwargs = {"max_results": max_results, "backend": backend,
                                  "region": region, "safesearch": "moderate"}
                        if timelimit:
                            kwargs["timelimit"] = timelimit
                        if news:
                            raw = list(ddgs.news(query, **kwargs))
                            items = [{"title": r.get("title", ""), "href": r.get("url", ""),
                                      "body": r.get("body", "")} for r in raw]
                        else:
                            raw = list(ddgs.text(query, **kwargs))
                            items = [{"title": r.get("title", ""), "href": r.get("href", ""),
                                      "body": r.get("body", "")} for r in raw]
                    items = filter_results(items)
                    if items:
                        return items
                except Exception:
                    continue
        if attempt < RETRIES:
            time.sleep(2 * (attempt + 1))
    return []


# ---------- 引擎：OpenAlex（学术） ----------

def parse_openalex(data):
    """解析 OpenAlex works 响应为 [{title, href, body}]。"""
    out = []
    for w in data.get("results", []):
        title = (w.get("title") or "").strip()
        if not title:
            continue
        wid = w.get("id", "")
        doi = (w.get("doi") or "").strip()
        href = None
        if doi:
            href = doi if doi.startswith("http") else f"https://doi.org/{doi}"
        elif wid:
            href = f"https://openalex.org/{wid.rsplit('/', 1)[-1]}"
        if not href:
            continue
        src = ""
        loc = (w.get("primary_location") or {})
        if loc and loc.get("source"):
            src = loc["source"].get("display_name", "")
        year = (w.get("publication_date") or "")[:4]
        body = " ".join(x for x in [src, year] if x) or "学术文献"
        out.append({"title": title, "href": href, "body": body})
    return out


def search_openalex(query, max_results=10):
    """OpenAlex 学术搜索。失败/空返回 []。"""
    try:
        url = ("https://api.openalex.org/works?search="
               + urllib.parse.quote(query) + f"&per-page={max_results}&mailto=research@example.com")
        data = http_get_json(url)
        return filter_results(parse_openalex(data))
    except Exception:
        return []


# ---------- 引擎：CrossRef（学术 DOI） ----------

def parse_crossref(data):
    """解析 CrossRef works 响应为 [{title, href, body}]。"""
    out = []
    for it in data.get("message", {}).get("items", []):
        title = (it.get("title") or [""])[0].strip()
        if not title:
            continue
        doi = it.get("DOI", "")
        if not doi:
            continue
        href = f"https://doi.org/{doi}"
        journal = (it.get("container-title") or [""])[0]
        year = ""
        if it.get("published-print"):
            year = it["published-print"]["date-parts"][0][0]
        elif it.get("published-online"):
            year = it["published-online"]["date-parts"][0][0]
        body = " ".join(x for x in [str(journal), str(year)] if x) or "学术文献"
        out.append({"title": title, "href": href, "body": body})
    return out


def search_crossref(query, max_results=10):
    """CrossRef 学术搜索。失败/空返回 []。"""
    try:
        url = ("https://api.crossref.org/works?query="
               + urllib.parse.quote(query) + f"&rows={max_results}")
        data = http_get_json(url)
        return filter_results(parse_crossref(data))
    except Exception:
        return []


# ---------- 引擎：Hacker News Algolia（技术社区） ----------

def parse_hn(data):
    """解析 HN Algolia 响应为 [{title, href, body}]。"""
    out = []
    for h in data.get("hits", []):
        title = (h.get("title") or "").strip()
        if not title:
            continue
        href = h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID', '')}"
        points = h.get("points") or 0
        comments = h.get("num_comments") or 0
        body = f"Hacker News 讨论：{points} 分 / {comments} 评论"
        out.append({"title": title, "href": href, "body": body})
    return out


def search_hn(query, max_results=10):
    """HN Algolia 技术讨论搜索。失败/空返回 []。"""
    try:
        url = ("https://hn.algolia.com/api/v1/search?query="
               + urllib.parse.quote(query) + f"&hitsPerPage={max_results}")
        data = http_get_json(url)
        return filter_results(parse_hn(data))
    except Exception:
        return []


# ---------- 引擎：Bing HTML（免费无 key） ----------

BING_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"}


def parse_bing_html(html_text):
    """解析 Bing HTML 搜索结果页（b_algo 块）为 [{title, href, body}]。

    实测（本机 cn.bing.com/www.bing.com 经代理可用）：HTML 端点
    （search?q=...&count=N）结果质量与新鲜度优于 RSS 端点（format=rss 返回
    镜像站污染）；中文查询用 cn.bing.com + qft 时间过滤效果最佳。
    """
    out = []
    for b in re.findall(r'<li class="b_algo".*?</li>', html_text, re.S):
        tm = re.search(r'<h2[^>]*><a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', b, re.S)
        if not tm:
            continue
        sm = re.search(r'<p[^>]*>(.*?)</p>', b, re.S)
        title = htmllib.unescape(re.sub(r"<[^>]+>", "", tm.group(2))).strip()
        body = (htmllib.unescape(re.sub(r"<[^>]+>", "", sm.group(1))).strip()
                if sm else "")
        out.append({"title": title, "href": tm.group(1), "body": body[:300]})
    return out


def search_bing(query, max_results=10, news=False, timelimit=None):
    """Bing HTML 搜索（免费无 key）。失败/空返回 []。

    - 含中文 → cn.bing.com（国内可达、中文结果质量高）；否则 www.bing.com
    - news 模式：cn.bing.com 用 qft=+filterui:age-ltN 时间过滤 + news 标签
    - timelimit（day/week/month/year）→ age-lt 分钟数（24h/168h/720h/8760h）
    """
    host = "cn.bing.com" if CJK_RE.search(query or "") else "www.bing.com"
    params = {"q": query, "count": max_results}
    if timelimit:
        hours = {"day": 24, "week": 168, "month": 720, "year": 8760}[timelimit]
        if host == "cn.bing.com":
            params["qft"] = f"+filterui:age-lt{hours * 60}"
        else:
            params["freshness"] = {"day": "Day", "week": "Week",
                                   "month": "Month", "year": "Year"}[timelimit]
    url = "https://%s/search?%s" % (host, urllib.parse.urlencode(params))
    req = urllib.request.Request(url, headers=BING_UA)
    with urllib.request.urlopen(req, timeout=15) as r:
        html_text = r.read().decode("utf-8", "ignore")
    items = parse_bing_html(html_text)
    return filter_results(items[:max_results])


# ---------- 引擎：Tavily（AI 搜索 API，免费层 1000 次/月） ----------

def search_tavily(query, max_results=10, news=False, timelimit=None):
    """Tavily AI 搜索。失败/空返回 []。

    依赖环境变量 TAVILY_API_KEY（或项目根 .env）；未配置时返回 [] 不报错。
    POST https://api.tavily.com/search，返回 title/url/content + answer。
    免费层：1000 次/月，basic 深度。
    """
    if not TAVILY_API_KEY:
        return []
    try:
        payload = {
            "api_key": TAVILY_API_KEY,
            "query": query,
            "max_results": max_results,
            "search_depth": "basic",
            "include_answer": True,
        }
        if news:
            payload["topic"] = "news"
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            "https://api.tavily.com/search", data=body,
            headers={"Content-Type": "application/json", "User-Agent": "zhihu-ask/1.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
        items = []
        answer = (data.get("answer") or "").strip()
        for res in data.get("results", []):
            title = (res.get("title") or "").strip()
            url = (res.get("url") or "").strip()
            if not title or not url:
                continue
            body_txt = (res.get("content") or "").strip()
            if answer and not body_txt:
                body_txt = answer
            items.append({"title": title, "href": url, "body": body_txt[:300]})
        return filter_results(items[:max_results])
    except Exception:
        return []


# ---------- 聚合入口 ----------

def _run_parallel(candidates, timeout):
    """并行执行引擎候选（auto 模式加速），返回首个非空结果；全部失败/空返回 None。

    每个候选在独立 **daemon 线程**运行：首个非空结果出现即返回，其余线程在后台
    继续跑到自然结束，主进程退出时 daemon 线程被终止——不会被慢引擎（如 ddgs
    反爬空转）阻塞。踩坑：初版用 `with ThreadPoolExecutor`，
    函数返回时 shutdown(wait=True) 会等待全部线程收尾，ddgs 空转一轮 ~30-100 秒，
    把整体耗时从「最快引擎」拖成「最慢引擎」。
    """
    import threading
    box = {}
    gate = threading.Event()

    def run(fn):
        try:
            items = fn()
        except Exception:
            return
        if items and not gate.is_set():
            box["items"] = items
            gate.set()

    threads = [threading.Thread(target=run, args=(fn,), daemon=True)
               for _, fn in candidates]
    for t in threads:
        t.start()
    gate.wait(timeout)
    return box.get("items")


def search(query, max_results=10, news=False, engine="auto", timelimit=None,
           engine_timeout=30):
    """多引擎聚合搜索，返回 [{title, href, body}] 列表。

    engine: auto（并行尝试全部引擎，首个非空胜出）/ ddgs / openalex / crossref / hn。
    news 模式仅 ddgs 支持。timelimit（仅 ddgs）：day/week/month/year 时间过滤。
    engine_timeout（仅 auto）：并行模式下单轮引擎总超时（秒），默认 30。
    全部引擎失败或无结果时抛 RuntimeError。
    """
    errors = []
    for q in query_variants(query):
        candidates = []
        if engine in ("auto", "ddgs"):
            candidates.append(("ddgs", lambda: search_ddgs(q, max_results, news, timelimit)))
        if not news and engine in ("auto", "openalex"):
            candidates.append(("openalex", lambda: search_openalex(q, max_results)))
        if not news and engine in ("auto", "crossref"):
            candidates.append(("crossref", lambda: search_crossref(q, max_results)))
        if not news and engine in ("auto", "hn"):
            candidates.append(("hn", lambda: search_hn(q, max_results)))
        if engine in ("auto", "bing"):
            # Bing HTML 免费引擎：news/timelimit 均支持
            candidates.append(("bing", lambda: search_bing(q, max_results, news, timelimit)))
        if engine in ("auto", "tavily"):
            # Tavily AI 搜索：无 key 时自动跳过
            candidates.append(("tavily", lambda: search_tavily(q, max_results, news, timelimit)))
        if engine == "auto" and len(candidates) > 1:
            # 并行模式：所有引擎同时尝试，首个非空胜出
            items = _run_parallel(candidates, engine_timeout)
            if items:
                return items
            errors.append(f"auto({q[:30]}): 并行尝试全部引擎均无结果/超时")
            continue
        for name, fn in candidates:
            try:
                items = fn()
            except Exception as e:
                errors.append(f"{name}({q[:30]}): {str(e)[:60]}")
                continue
            if items:
                return items
            errors.append(f"{name}({q[:30]}): 无结果")
    if errors:
        raise RuntimeError("；".join(errors[-8:]))
    raise RuntimeError("无可用查询变体")


def auto_register_channel_b(out_path, slug, items, engine):
    """落盘后自动登记通道 B（Web）。返回 (ok, message)。

    写到标准 research/<slug>/gathered_web.md 即登记 done/empty（按命中数），
    slug 可显式传入，否则从输出路径反推（同 A/P 通道惯例）。
    """
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import channel_state as _cs
        slug = slug or _cs.derive_slug_from_out(out_path)
        if not slug:
            return False, "无法从输出路径反推 slug（非 research/<slug>/ 标准布局），跳过通道 B 自动登记"
        status = "done" if items else "empty"
        note = f"命中 {len(items)} 条（引擎 {engine}）" if items else "通道 B 零命中"
        if _cs.mark(slug, "B", status, note=note):
            return True, f"通道 B（Web）: {status} —— {note}"
        return False, f"未找到 research/{slug}/.progress.json，跳过通道 B 自动登记（请先 research_start）"
    except Exception as e:
        return False, f"通道 B 自动登记失败（不影响落盘）: {e}"


def load_queries_file(path):
    """读取多查询 JSON（{"queries": ["q1", ...]} 或纯列表），返回去空字符串列表。"""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        data = data.get("queries") or []
    return [str(q).strip() for q in data if str(q).strip()]


def run_queries(queries, args):
    """并行执行多组查询，返回 [(query, items, error), ...]（保持传入顺序）。

    --parallel 控制并发（1=串行）；单个查询失败记 error，不影响其他查询。
    """
    def _one(q):
        try:
            return (q, search(q, args.max, args.news, args.engine, args.timelimit,
                              engine_timeout=args.timeout), None)
        except Exception as e:
            return (q, [], f"{type(e).__name__}: {e}")

    if len(queries) <= 1 or args.parallel <= 1:
        return [_one(q) for q in queries]
    from concurrent.futures import ThreadPoolExecutor
    results = []
    with ThreadPoolExecutor(max_workers=args.parallel) as ex:
        for r in ex.map(_one, queries):
            results.append(r)
    return results


def main():
    ap = argparse.ArgumentParser(description="Web 搜索工具（多引擎聚合，无需 API key）")
    ap.add_argument("query", nargs="?", help="搜索关键词（中文/英文均可）；与 --queries-file 二选一")
    ap.add_argument("--queries-file", help="多查询 JSON 文件（{\"queries\": [\"q1\", ...]} 或纯列表），并行搜索")
    ap.add_argument("--parallel", type=int, default=4, help="多查询并行数（默认 4；1=串行）")
    ap.add_argument("--max", type=int, default=10, help="结果条数（默认 10）")
    ap.add_argument("--news", action="store_true", help="新闻搜索模式（仅 ddgs）")
    ap.add_argument("--engine", default="auto", choices=["auto", "ddgs", "openalex", "crossref", "hn", "bing", "tavily"],
                    help="引擎（默认 auto 聚合）")
    ap.add_argument("--timelimit", default=None, choices=["day", "week", "month", "year"],
                    help="时间过滤（仅 ddgs）：day/week/month/year")
    ap.add_argument("--timeout", type=int, default=30,
                    help="auto 并行模式单轮引擎总超时秒数（默认 30）")
    ap.add_argument("--out", help="落盘为 Markdown 素材文件（追加式）")
    ap.add_argument("--slug", help="落盘时自动登记通道 B 的 slug（默认从 --out 路径反推）")
    ap.add_argument("--json", action="store_true", help="输出原始 JSON")
    args = ap.parse_args()

    # 查询列表：--queries-file（多查询并行）或单个 positional query
    if args.queries_file:
        try:
            queries = load_queries_file(args.queries_file)
        except Exception as e:
            print(f"ERROR: 无法读取 --queries-file：{e}", file=sys.stderr)
            sys.exit(2)
        if not queries:
            print("ERROR: --queries-file 未包含有效 queries 列表", file=sys.stderr)
            sys.exit(2)
    else:
        if not args.query:
            print("ERROR: 需提供 query 或 --queries-file", file=sys.stderr)
            sys.exit(2)
        queries = [args.query]

    results = run_queries(queries, args)
    total_items = sum(len(items) for _, items, _ in results)
    failed = [q for q, _items, err in results if err]

    if args.json:
        print(json.dumps([{"query": q, "items": items, "error": err}
                          for q, items, err in results], ensure_ascii=False, indent=1))
    else:
        for q, items, err in results:
            if err:
                print(f"[失败] 关键词「{q}」：{err}", file=sys.stderr)
                continue
            print(f"命中 {len(items)} 条（{q}，引擎 {args.engine}，{'新闻' if args.news else '网页'}）：", file=sys.stderr)
            for i, r in enumerate(items, 1):
                print(f"{i}. {r['title']}", file=sys.stderr)
                print(f"   {r['href']}", file=sys.stderr)
                if r.get("body"):
                    print(f"   {r['body'][:120]}", file=sys.stderr)
            print(file=sys.stderr)
        if failed:
            print(f"[汇总] {len(queries)} 组查询中 {len(failed)} 组失败：{', '.join(failed[:3])}", file=sys.stderr)

    if not total_items and not args.out and not args.queries_file:
        print(f"[无结果] 关键词「{args.query}」无命中，可换词重试。", file=sys.stderr)
        sys.exit(0)

    if args.out:
        with open(args.out, "a", encoding="utf-8") as f:
            for q, items, err in results:
                f.write(f"\n## Web 检索：{q}（{date.today()}，引擎 {args.engine}）\n\n")
                for r in items:
                    f.write(f"- **{r['title']}**\n  - 链接：{r['href']}\n")
                    if r.get("body"):
                        f.write(f"  - 摘要：{r['body'][:200]}\n")
                if err:
                    f.write(f"（检索失败：{err}）\n")
                elif not items:
                    f.write("（零命中，换词重试后仍无则登记通道 B 无有效素材）\n")
                f.write("\n")
        print(f"[已落盘] {args.out}", file=sys.stderr)
        # 落盘即自动登记通道 B（Web）：写到标准 research/<slug>/gathered_web.md 即登记，
        # 无需手动 mark_channel（可用 --slug 显式指定；否则从输出路径反推，同 A/P 通道惯例）。
        ok, msg = auto_register_channel_b(args.out, args.slug,
                                          [r for _, items, _ in results for r in items], args.engine)
        print(f"[自动登记] {msg}" if ok else f"[提示] {msg}", file=sys.stderr)

    # 全部查询失败 → 退出码 1；部分失败/零命中 → 0（零命中已有 empty 登记闭环）
    if failed and len(failed) == len(queries):
        sys.exit(1)


if __name__ == "__main__":
    main()
