#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""引用核验网络层：CrossRef/arXiv/URL 可达性（urllib + curl 兜底）。
符号经 facade `from cv_net import *` 注入 facade.__dict__，使
mock.patch.object(ccv, 'http_get_json'/'check_url_reachable') 生效。"""
import json
import os
import sys
import urllib.parse
import urllib.request

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""违规引用检查：作者真实性 + 题名一致性 + URL 伪造

背景：此前报告参考文献 [2] 出现两类违规——编造作者
（"Li Y, et al." 系虚构，经 CrossRef 核实真实作者为 Miao Yuchun 等）与张冠李戴
（正文描述"策略覆盖视角"挂到 InfoRM 名下，与该文实际内容不符）。
check_gbt_refs 只查著录格式（编号/类型/日期），无法发现"引用本身不真实"。

学术纪律：
- 核验失败 ≠ 核验通过：联网核验失败默认升级为硬伤阻断（不得静默放行）；
  显式 --offline 才允许跳过，且输出中声明"离线模式"。
- 佚名必须真佚名：注册库有作者却著录"佚名"= 作者误用（GB/T：无作者才写佚名）。
- 引用日期须晚于/等于发布日期（引用日期早于发布 = 硬伤）。
- 引用 URL 须可溯源：普通 URL 死链（404/5xx）= 硬伤。
- arXiv 条目同样核验作者与发布日期（不只题名）。

硬性（命中即退出码 1，阻断）：
1. URL 伪造/占位符：URL 含 example.com、<...>、TBD、占位符；或含 #related/#anchor/#note 等
   伪锚点（真实文献 URL 不带这类锚点，如 arxiv.org/abs/xxxx 后拼 #related 属伪造）
2. 作者真实性核验（联网，--offline 跳过）：条目 URL 为 doi.org/10.xxxx 时调 CrossRef
   works API 核验：著录作者序列与注册作者序列前 3 位不匹配 → 疑似编造作者
3. 题名一致性核验（联网，--offline 跳过）：条目含 doi.org URL 时，著录题名与 CrossRef
   注册题名经规范化后不一致 → 张冠李戴；arxiv.org/abs 链接调 arxiv API 核验题名
4. arxiv URL 伪造：arxiv.org/abs/<id> 中 id 非法（须 YYMM.NNNNN 或 vN 后缀格式），或
   条目标题与 arxiv API 返回题名不一致 → 硬伤
5. 作者误用（佚名）：著录"佚名"但 CrossRef/arXiv 注册库有作者 → 硬伤（学术纪律）
6. 引用日期早于发布日期：著录引用日期 < 注册库发布日期 → 硬伤（学术纪律）
7. 普通 URL 死链：非 DOI/arxiv 的 URL 返回 404/5xx → 硬伤（学术纪律）
8. 联网核验失败：含 DOI/arxiv 条目但 CrossRef/arXiv 核验网络失败 → 硬伤（默认模式）

提示级（默认 RC=1，严格阻断为默认）：
9. 作者格式疑似异常：英文作者未按"姓全大写 名首字母"（如 "LI Y"），或作者字段过短
10. 正文引注处与文献题名关键词不匹配（启发式，仅报告模式正文含 [n] 时）：
    正文首次出现 [n] 的前后 100 字与文献题名共享的候选词 < 1 个 → 疑似张冠李戴
    （候选词含去尾字前缀，覆盖「遍历论/遍历理论」类词面差异；0 命中才报）
11. URL 可达性未验证：普通 URL 可达性检查因网络失败无法判定

用法：
  python tools/check_citation_validity.py --file path/to/file.md
  python tools/check_citation_validity.py --slug <slug>
  python tools/check_citation_validity.py --file x.md --offline   # 声明放弃联网核验（输出注明）
  python tools/check_citation_validity.py --file x.md   # 默认严格阻断，提示级命中同样失败
  python tools/check_citation_validity.py --file x.md --verbose   # 显示命中明细
"""


UA = {"User-Agent": "Mozilla/5.0 (zhihu-ask citation validator)"}


def http_get_json(url, timeout=10):
    """GET 并解析 JSON。urllib 失败时 curl 兜底（与 web_search 一致——
    urllib SSL/代理栈本机偶发失败而系统 curl 独立栈可用）。"""
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception:
        data = http_get_curl(url, timeout)
        if data is None:
            raise
        return data


def http_get_curl(url, timeout=10):
    """curl 兜底 GET：返回解析后的 JSON 或 None。"""
    try:
        import shutil
        import subprocess
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


def fetch_text(url, timeout=10):
    """GET 返回文本；urllib 失败时 curl 兜底。全部失败返回 None。"""
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", "replace")
    except Exception:
        pass
    try:
        import shutil
        import subprocess
        if shutil.which("curl") is None:
            return None
        r = subprocess.run(
            ["curl", "-sL", "--max-time", str(timeout), "-A", UA.get("User-Agent", "Mozilla/5.0"), url],
            capture_output=True, timeout=timeout + 10)
        return r.stdout.decode("utf-8", "replace") if r.stdout else None
    except Exception:
        return None


def check_url_reachable(url, timeout=10):
    """URL 可达性：返回 (是否可达, 状态说明)。重定向视为可达；404/5xx 不可达；网络失败返回 None。

    403（反爬拒绝）与 000（网络层无响应）不直接判死链：降级 WebFetch 复核，
    复核成功说明页面存在、仅直连被拦截，按可达处理（死链判定的核心是「内容不存在」，
    而非「本机直连被拒」）。
    """
    try:
        import shutil
        import subprocess
        if shutil.which("curl") is None:
            return None, "无 curl"
        r = subprocess.run(
            ["curl", "-sL", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", str(timeout),
             "-A", UA.get("User-Agent", "Mozilla/5.0"), url],
            capture_output=True, timeout=timeout + 10)
        code = (r.stdout or b"").decode("utf-8", "replace").strip()
        if not code:
            return None, "空响应"
        # 429（限流）视为"暂不可达但非死链"——网页存在但被限流，
        # 与 404 死链本质不同；返回 True 交由提示级处理（URL 可达性未验证）。
        if code.startswith(("2", "3")):
            return True, f"HTTP {code}"
        if code.startswith("429"):
            return None, f"HTTP 429（限流，非死链）"
        # 403/000：直连被拒 ≠ 内容不存在，WebFetch 复核后判定
        if code.startswith(("403", "000")):
            from check_citation_validity import _probe_via_webfetch
            ok, detail = _probe_via_webfetch(url)
            if ok:
                return True, f"HTTP {code}（直连被拒，{detail}）"
            return False, f"HTTP {code}（{detail}）"
        return False, f"HTTP {code}"
    except Exception as e:
        return None, str(e)[:40]
