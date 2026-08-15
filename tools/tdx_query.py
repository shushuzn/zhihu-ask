# -*- coding: utf-8 -*-
"""通达信 TQ 查询工具（tdx-tq-local HTTP JSON-RPC 模式，zhihu-ask 项目专用）

背景：本机通达信金融终端（TdxW.exe）内置 HTTP 服务
http://127.0.0.1:17709/，按 JSON-RPC 协议即可取行情/财务/板块/分红等数据，
无需生成 Python 策略文件、无需 numpy/pandas 依赖（tdx-tq-local SKILL 方案）。

用法：
  python tools/tdx_query.py lookup  --name 贵州茅台                    # 证券代码查询
  python tools/tdx_query.py snapshot --code 600519.SH                  # 实时行情快照
  python tools/tdx_query.py kline   --code 600519.SH --period 1d --count 10
  python tools/tdx_query.py info    --code 600519.SH                   # 基础信息+财务
  python tools/tdx_query.py more    --code 600519.SH                   # 扩展信息（估值/资金）
  python tools/tdx_query.py relation --code 600519.SH                  # 所属板块
  python tools/tdx_query.py divid   --code 600519.SH --start 20250101 --end 20261231
  python tools/tdx_query.py all     --code 600519.SH                   # 快照+财务+扩展+板块

通用选项：
  --json            输出原始 JSON（便于脚本化），不格式化
  --code 股票代码   标准格式如 600519.SH / 000001.SZ / 00700.HK / AAPL.US
  --fields "A,B,C"  限定返回字段（info/more 有效）

依赖：通达信客户端（TdxW.exe）运行中且已登录，HTTP 服务 127.0.0.1:17709 可达。
K 线历史条数取决于客户端本地已下载的数据（盘后数据下载补齐）。

退出码：0 成功；1 连接失败或接口业务错误；2 参数错误。
"""
import argparse
import json
import sys
import urllib.request
import urllib.error

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

TQ_URL = "http://127.0.0.1:17709/"
TIMEOUT = 15

# get_stock_info 的 field_list 不能为空（接口规定），默认常用财务字段
INFO_DEFAULT_FIELDS = ["Name", "J_yysy", "J_jly", "J_mgsy", "J_jzc", "J_zgb",
                       "J_zzc", "J_ldfz", "J_jyxjl", "J_start"]
# get_more_info 的常用展示字段（接口忽略 field_list 返回全部，此处仅作过滤）
MORE_DEFAULT_FIELDS = ["Name", "Now", "ZAF", "Zsz", "Ltsz", "StaticPE_TTM",
                       "DynaPE", "PB_MRQ", "DYRatio", "fHSL", "Zjl_HB",
                       "HisHigh", "HisLow", "HqDate", "ZTPrice", "DTPrice"]


def rpc(method, params, rid=1):
    """向通达信本地 HTTP 服务发送 JSON-RPC 请求，返回 result 字典。"""
    payload = {"id": rid, "method": method, "params": params}
    req = urllib.request.Request(
        TQ_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
        print(f"[失败] 通达信 HTTP 服务不可达（{TQ_URL}）：{e}")
        print("      请确认 TdxW.exe 已启动并登录、进入主界面后再试。")
        sys.exit(1)
    result = data.get("result") or {}
    if isinstance(result, dict) and result.get("ErrorId") not in ("0", None):
        print(f"[失败] {method} 业务错误 ErrorId={result.get('ErrorId')}")
        sys.exit(1)
    return result


# ─── 各接口封装 ───────────────────────────────────────────────────────────

def lookup(name):
    """按名称/拼音/代码模糊查证券。"""
    res = rpc("get_match_stkinfo", {"key_word": name})
    value = res.get("Value")
    return value if isinstance(value, list) else []


def snapshot(code):
    """实时行情快照。"""
    res = rpc("get_market_snapshot", {"stock_code": code})
    return res


def kline(code, period="1d", count=10, fields=None, dividend_type="none"):
    """历史 K 线（条数受客户端本地数据限制）。"""
    field_list = fields or ["Date", "Open", "High", "Low", "Close", "Volume"]
    res = rpc("get_market_data", {
        "field_list": field_list,
        "stock_list": [code],
        "period": period,
        "count": count,
        "dividend_type": dividend_type,
    })
    value = (res.get("Value") or {}).get(code, {})
    return value


def info(code, fields=None):
    """基础信息 + 财务（field_list 必填非空）。"""
    field_list = fields or INFO_DEFAULT_FIELDS
    return rpc("get_stock_info", {"stock_code": code, "field_list": field_list})


def more(code, fields=None):
    """扩展信息（接口返回全部字段，本地过滤展示）。"""
    res = rpc("get_more_info", {"stock_code": code})
    value = res.get("Value") or {}
    if fields:
        return {k: v for k, v in value.items() if k in fields}
    return value


def relation(code):
    """所属板块列表。"""
    res = rpc("get_relation", {"stock_code": code})
    value = res.get("Value")
    return value if isinstance(value, list) else []


def divid(code, start, end):
    """分红配送记录。"""
    return rpc("get_divid_factors", {
        "stock_code": code, "start_time": start, "end_time": end})


# ─── 格式化输出 ──────────────────────────────────────────────────────────

def fmt_snapshot(code, res):
    buy1 = (res.get("Buyp") or [""])[0]
    buy1v = (res.get("Buyv") or [""])[0]
    print(f"[{code}] 现价 {res.get('Now')} | 开 {res.get('Open')} | "
          f"高 {res.get('Max')} | 低 {res.get('Min')} | 昨收 {res.get('LastClose')}")
    print(f"  量 {res.get('Volume')} 手 | 额 {res.get('Amount')} 万 | "
          f"内盘 {res.get('Inside')} | 外盘 {res.get('Outside')}")
    print(f"  五档买1 {buy1} ({buy1v}手) | 涨速 {res.get('Zangsu')} | 3日涨幅 {res.get('ZAFPre3')}%")


def fmt_kline(code, value):
    dates = value.get("Date", [])
    if not dates:
        print(f"[{code}] 无 K 线数据（客户端未下载该周期数据，请先盘后数据下载）")
        return
    print(f"[{code}] {len(dates)} 条 K 线：")
    print("  日期        开      高      低      收      量(手)")
    for i in range(len(dates)):
        row = [dates[i], value.get("Open", [""])[i], value.get("High", [""])[i],
               value.get("Low", [""])[i], value.get("Close", [""])[i],
               value.get("Volume", [""])[i]]
        print("  " + "  ".join(str(x) for x in row))


def fmt_info(res):
    name = res.get("Name", "?")
    print(f"[{name}] 财务（万元，通达信 F10 口径）")
    print(f"  营业收入 {res.get('J_yysy')} | 净利润 {res.get('J_jly')} | "
          f"经营现金流 {res.get('J_jyxjl')}")
    print(f"  每股收益 {res.get('J_mgsy')} | 净资产 {res.get('J_jzc')} | "
          f"总股本 {res.get('J_zgb')} 万 | 总资产 {res.get('J_zzc')} | "
          f"流动负债 {res.get('J_ldfz')}")
    print(f"  上市日期 {res.get('J_start')}")


def fmt_more(code, res):
    snap = snapshot(code)
    name = (info(code, ["Name"]).get("Name")) or snap.get("Name") or res.get("Name") or code
    now = res.get("Now") or snap.get("Now")
    print(f"[{name}] 扩展信息（{res.get('HqDate')}）")
    print(f"  现价 {now} | 涨幅 {res.get('ZAF')}% | "
          f"总市值 {res.get('Zsz')} 亿 | 流通市值 {res.get('Ltsz')} 亿")
    print(f"  PE(TTM) {res.get('StaticPE_TTM')} | 动态PE {res.get('DynaPE')} | "
          f"PB {res.get('PB_MRQ')} | 股息率 {res.get('DYRatio')}% | "
          f"换手 {res.get('fHSL')}%")
    print(f"  主力净流入 {res.get('Zjl_HB')} 万 | 52周高 {res.get('HisHigh')} | "
          f"52周低 {res.get('HisLow')} | 涨停价 {res.get('ZTPrice')} | "
          f"跌停价 {res.get('DTPrice')}")


def fmt_relation(code, blocks):
    if not blocks:
        print(f"[{code}] 无板块信息")
        return
    print(f"[{code}] 所属板块 {len(blocks)} 个：")
    for b in blocks:
        print(f"  - {b.get('BlockName')}（{b.get('BlockType')}）")


def fmt_divid(res, start, end):
    dates = res.get("Date", [])
    print(f"分红记录 {len(dates)} 条（{start}~{end}）")
    print("  前 10 条:", ", ".join(str(d) for d in dates[:10]),
          "..." if len(dates) > 10 else "")


# ─── CLI ────────────────────────────────────────────────────────────────

def build_parser():
    ap = argparse.ArgumentParser(description="通达信 TQ 查询工具（HTTP JSON-RPC 模式）")
    ap.add_argument("command", choices=["lookup", "snapshot", "kline", "info",
                                        "more", "relation", "divid", "all"])
    ap.add_argument("--code", help="证券代码，如 600519.SH")
    ap.add_argument("--name", help="证券名称/关键字（lookup）")
    ap.add_argument("--period", default="1d", help="K线周期（1m/5m/15m/30m/1h/1d/1w/1mon/1q/1y/tick）")
    ap.add_argument("--count", type=int, default=10, help="K线条数（默认 10）")
    ap.add_argument("--fields", help="限定返回字段，逗号分隔（info/more）")
    ap.add_argument("--start", default="20250101", help="开始日期 YYYYMMDD（divid）")
    ap.add_argument("--end", default="20261231", help="结束日期 YYYYMMDD（divid）")
    ap.add_argument("--json", action="store_true", help="输出原始 JSON")
    return ap


def main():
    ap = build_parser()
    args = ap.parse_args()
    fields = [f.strip() for f in args.fields.split(",")] if args.fields else None

    if args.command in ("snapshot", "kline", "info", "more", "relation", "divid", "all") and not args.code:
        ap.error("--code 必填")

    if args.command == "lookup":
        if not args.name:
            ap.error("--name 必填")
        items = lookup(args.name)
        if args.json:
            print(json.dumps(items, ensure_ascii=False))
        elif items:
            print(f"匹配 {len(items)} 条：")
            for it in items:
                print(f"  {it.get('Code')}  {it.get('Name')}")
        else:
            print("无匹配，可尝试换关键词或先调用通达信接口 get_stock_list")
        return

    if args.command == "snapshot":
        res = snapshot(args.code)
        if args.json:
            print(json.dumps(res, ensure_ascii=False))
        else:
            fmt_snapshot(args.code, res)
        return

    if args.command == "kline":
        value = kline(args.code, args.period, args.count, fields)
        if args.json:
            print(json.dumps(value, ensure_ascii=False))
        else:
            fmt_kline(args.code, value)
        return

    if args.command == "info":
        res = info(args.code, fields)
        if args.json:
            print(json.dumps(res, ensure_ascii=False))
        else:
            fmt_info(res)
        return

    if args.command == "more":
        res = more(args.code, fields)
        if args.json:
            print(json.dumps(res, ensure_ascii=False))
        else:
            fmt_more(args.code, res)
        return

    if args.command == "relation":
        blocks = relation(args.code)
        if args.json:
            print(json.dumps(blocks, ensure_ascii=False))
        else:
            fmt_relation(args.code, blocks)
        return

    if args.command == "divid":
        res = divid(args.code, args.start, args.end)
        if args.json:
            print(json.dumps(res, ensure_ascii=False))
        else:
            fmt_divid(res, args.start, args.end)
        return

    # all：综合
    if args.json:
        out = {"snapshot": snapshot(args.code), "info": info(args.code),
               "more": more(args.code), "relation": relation(args.code)}
        print(json.dumps(out, ensure_ascii=False))
        return
    print("=" * 50)
    fmt_snapshot(args.code, snapshot(args.code))
    print("=" * 50)
    fmt_info(info(args.code))
    print("=" * 50)
    fmt_more(args.code, more(args.code))
    print("=" * 50)
    fmt_relation(args.code, relation(args.code))


if __name__ == "__main__":
    main()
