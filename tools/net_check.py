
"""
外网出口检测工具（zhihu-ask 项目专用）

本环境命令行工具（curl 等）通常无外网出口，但 Python urllib 经 HTTPS_PROXY
可正常联网——故 tools/arxiv_search.py（urllib 实现）能直连 ArXiv，而 arxiv-watcher
的 curl 脚本则永远空返回。report_to_docx 的图片下载等 urllib 外网动作同样可联网。
本模块用 urllib 探测出口，供外网脚本在真正无出口时打印清晰提示，避免「静默失败
让人误以为成功」。

用法：
  python tools/net_check.py                 # CLI：打印出口状态
  # 作为模块：
  from net_check import has_egress, require_egress
  if require_egress("报告图片下载"):
      ... 执行外网动作 ...
"""

import urllib.request

_PROBE_URL = "https://export.arxiv.org/api/query?search_query=all:test&max_results=1"


def has_egress(timeout=8):
    """尝试一次轻量 urllib 请求，能拿到非空响应即认为有出口。"""
    try:
        req = urllib.request.Request(
            _PROBE_URL, headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return len(resp.read(256)) > 0
    except Exception:
        return False


def require_egress(purpose="外网抓取"):
    """返回是否有出口；无出口时打印清晰提示。"""
    if has_egress():
        return True
    print(
        "[出口检测] 当前环境 urllib 无外网出口。"
        f"{purpose}将失败或降级。"
    )
    print(
        "  解决：请用 agent 的 WebFetch 工具完成该步骤"
        "（WebFetch 走 WorkBuddy 后端代理，可正常联网），再交由本地工具处理。"
    )
    return False


if __name__ == "__main__":
    if has_egress():
        print("[OK] 检测到外网出口，Bash 可直接联网。")
    else:
        print("[WARN] 未检测到外网出口；Bash 外网动作将失败，请走 WebFetch。")
