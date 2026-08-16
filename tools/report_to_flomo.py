
"""
研究报告 → flomo 格式存档工具（zhihu-ask 项目专用；报告禁止上传 flomo，本工具仅做本地存档转换）

参考 mynews 项目的 flomo 集成模式（外部项目，思路一致：完整内容一字不改、只转格式）：
把研究报告【完整内容】转换为 flomo 兼容格式，一字不改、只转格式；仅用于本地存档 flomo_full.md，
上传动作改由 tools/note_upload.py 执行（上传对象为模块化笔记，报告/索引禁止上传）。
flomo 仅支持加粗/高亮/下划线/有序/无序列表，不支持标题/引用/代码块/链接/表格，
故做以下机械转换（不增删任何文字）：
  - 标题（#/##/###）→ 加粗 **标题**
  - 引用（>）→ 正文（去掉 >）
  - 表格行（| a | b |）→ 列表 - a / b；表头分隔行（|---|）跳过
  - 链接 [标题](url) → 标题（url）
  - 图片 ![alt](url) → alt（url）（保留图片 URL 供可追溯；flomo 平台本身支持图片，
    见下方「flomo 图片能力说明」）
  - 反引号（`）→ 去掉
其余内容原样保留。

flomo 图片能力说明（官方文档研究结论，纠正此前"flomo 不支持图片"的错误认知）：
  - flomo 平台支持图片：URL Scheme `flomo://create?image_urls=[...]`（最多 9 个公网图片
    URL，需 PRO 会员 + flomo 客户端）；存储空间免费 500M（压缩）/ PRO 20G（原图）。
  - 当前接入的 flomo 官方 MCP 的 memo_create/memo_update 无图片参数（仅 content/format），
    故本工具输出的文本版不含图片，图片引用转为 alt（url）保留。
  - 未来接入带图：走官方 webhook API（https://flomoapp.com/iwh/{token}，需 PRO）或
    URL Scheme 手动带图——图片 URL 已部署公网（CloudStudio），可直接引用。

用法：
    python tools/report_to_flomo.py --slug <slug>                    # 打印完整转换结果
    python tools/report_to_flomo.py --slug <slug> --out flomo_full.md # 写文件（research/<slug>/）

存档说明：flomo_full.md 仅作为报告本地存档（不上传）；素材库（gathered_*）、plan.md 仍仅存本地。
"""

import sys
import os
import re
from datetime import date

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DOMAIN_TAGS = {
    "能源": ("能源", "油气煤炭"),
    "营销": ("营销", "消费心理"),
    "消费心理": ("营销", "消费心理"),
    "人工智能": ("AI", "科技社会"),
    "ai": ("AI", "科技社会"),
    "编程语言": ("编程语言", "开源社区"),
    "科技": ("科技战略", "地缘产业"),
    "财政": ("财政", "宏观经济"),
    "经济史": ("经济", "历史"),
    "宏观": ("财政", "宏观经济"),
    "金融": ("金融", "投资理财"),
    "量化": ("金融", "投资理财"),
    "因子": ("金融", "投资理财"),
    "股票": ("金融", "投资理财"),
    "基金": ("金融", "投资理财"),
    "期货": ("金融", "投资理财"),
    "指数": ("金融", "投资理财"),
    "贵金属": ("金融", "贵金属"),
    "数码": ("数码", "消费电子"),
    "产品": ("产品", "职业成长"),
    "法律": ("法律", "合规"),
    "教育": ("教育", "学业规划"),
    "产业经济": ("产业经济", "区域经济"),
    "数学": ("数学", "基础科学"),
    "物理": ("物理", "基础科学"),
    "凝聚态": ("物理", "基础科学"),
    "量子": ("物理", "基础科学"),
    "路径积分": ("物理", "基础科学"),
    "场论": ("物理", "基础科学"),
}

def get_meta(slug):
    """从报告头部读取领域与标题（仅元信息，不读正文）。

报告头部已删除「日期：... | 领域：...」行（用户规范），领域改从
    plan.md 读取（init_research 落盘）；plan.md 缺失时回退为从 slug 推断。
    """
    path = os.path.join(ROOT, "research", slug, "report.md")
    domain, title = "", ""
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f.readlines()[:8]:
                m = re.match(r"^#\s+(.+)$", line.strip())
                if m and not title:
                    title = m.group(1).strip()
    except OSError as e:
        print(f"[错误] 无法读取报告头部: {e}", file=sys.stderr)

    plan_path = os.path.join(ROOT, "research", slug, "plan.md")
    try:
        with open(plan_path, "r", encoding="utf-8") as f:
            for line in f.readlines()[:20]:
                m = re.search(r"领域[：:]\s*([^|]+)", line.strip())
                if m:
                    domain = m.group(1).strip()
                    break
    except OSError:
        pass

    # 占位符防御：模板未实填时（{{...}}）视同缺失，避免静默产出 #{{...}} 之类脏标签
    if "{{" in domain:
        print(f"[警告] plan.md 领域仍是模板占位符「{domain}」，请实填后重跑（{plan_path}）", file=sys.stderr)
        domain = ""
    if not domain:
        print(f"[警告] plan.md 未提供领域（{plan_path}），标签将兜底", file=sys.stderr)
    return title, domain

def pick_tags(domain):
    """领域 → (一级, 二级) 标签。返回 (tags, matched)；未命中时兜底并警告提示补映射。

匹配改为「最长键优先」——按 key 长度降序遍历，先匹配更长更具体的键，
    根治子串误匹配（如"科技 / 人工智能"此前被"科技"抢先命中而非"人工智能"；
    "经济史 / 宏观经济"被"宏观"抢先命中）。此前靠字典顺序打补丁不彻底。
    """
    d = (domain or "").strip()
    dl = d.lower()
    best, best_key = None, ""
    for key, tags in DOMAIN_TAGS.items():
        kl = key.lower()
        if kl in dl and len(kl) > len(best_key):
            best, best_key = tags, kl
    if best:
        return best, True
    first = re.split(r"[/、,，\s]+", d)[0] if d else "研究"
    tags = (first[:8] or "研究", "综合")
    print(f"[警告] 领域「{d or '未记录'}」未在 DOMAIN_TAGS 中，兜底为 #{tags[0]} #{tags[1]}，请到 tools/report_to_flomo.py 补充映射", file=sys.stderr)
    return tags, False

LOCAL_IMG_LINE = re.compile(r"^\s*!\[[^\]]*\]\((?!https?:|//)[^)]+\)\s*$")


def _img_repl(m):
    """行内图片转换：仅公网 URL 保留地址，本地相对路径只留 alt 文字。

    报告内的图表是本地相对路径（如 chart_benchmark.png），转成
    「图注（chart_benchmark.png）」后在 flomo 里既不可点也无法显示，
    只是噪声；公网 URL 则保留以便追溯（见文件头 flomo 图片能力说明）。
    """
    alt, url = m.group(1).strip(), m.group(2).strip()
    if re.match(r"^(https?:)?//", url):
        return f"{alt}（{url}）"
    return alt


def convert_text(text):
    """把 markdown 文本转换为 flomo 兼容格式（只转格式，不改内容）。

    纯函数，便于单元测试；convert_full_report 读取文件后委托此函数。
    """
    out = []
    for idx, line in enumerate(text.splitlines()):
        s = line.rstrip()

        if re.match(r"^\s*\|[\s:\-|]+\|\s*$", s):
            continue

        # 剥离锚点独立行（<a id="ref-N"></a>）：flomo 不需要
        if re.match(r"^\s*<a\s+id=\"ref-\d+\"[^>]*>\s*</a>\s*$", s):
            continue

        # 整行的本地图片直接丢弃：报告规范里图片行后紧跟「图 N｜…」图注行，
        # 保留 alt 会与图注文字重复。公网图片不在此列（仍按行内规则保留 URL）。
        if LOCAL_IMG_LINE.match(s):
            continue

        m = re.match(r"^\s*\|(.+)\|\s*$", s)
        if m:
            # 表格内 LaTeX 范数 \\| 不得被误判为列分隔符
            protected = re.sub(r"(\$[^$\n]+\$)", lambda mm: mm.group(1).replace("|", "\x00"), m.group(1))
            cells = [c.strip().replace("\x00", "|") for c in protected.split("|")]
            out.append("- " + " / ".join(cells))
            continue

        m = re.match(r"^(#{1,6})\s+(.+)$", s)
        if m:
            # 标签行：首行含多个被空格分隔的 #tag（如 "#AI大Model #价格策略"）
            # 标题行：### 开头的连续 #（如 "### 2.1 口径说明"）→ 正常转加粗
            # 判断：首行且有 "空格+ #" 模式（多个独立 tag）
            is_tag_line = (idx == 0 and re.match(r"^#\S", s) and re.search(r"\s+#\S", s))
            if is_tag_line:
                out.append(s)
            else:
                out.append(f"**{m.group(2).strip()}**")
            continue

        if s.startswith(">"):
            out.append(s.lstrip("> ").strip())
            continue

        s2 = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", _img_repl, s)

        # 外部链接 [text](url) → text（url）；锚点链接 [text](#...) 保留为 [text]（引注格式）
        s2 = re.sub(r"\[([^\]]+)\]\((#[^)]+)\)", r"[\1]", s2)
        s2 = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1（\2）", s2)

        # 剥离 HTML 标签（flomo 不支持 HTML）
        s2 = re.sub(r"</?sup>", "", s2)
        s2 = re.sub(r"<a[^>]*>[^<]*</a>", "", s2)

        s2 = s2.replace("`", "")
        out.append(s2)
    return "\n".join(out).strip()


def convert_full_report(slug):
    """读取 report.md 全文，转换为 flomo 兼容格式（只转格式，不改内容）。"""
    path = os.path.join(ROOT, "research", slug, "report.md")
    if not os.path.isfile(path):
        print(f"[错误] 未找到报告: {path}", file=sys.stderr)
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()
    return convert_text(raw)

def main():
    args = {"slug": None, "out": None}
    argv = sys.argv[1:]
    i = 0
    while i < len(argv):
        if argv[i] == "--slug" and i + 1 < len(argv):
            args["slug"] = argv[i + 1]
            i += 2
        elif argv[i] == "--out" and i + 1 < len(argv):
            args["out"] = argv[i + 1]
            i += 2
        else:
            i += 1
    slug = args["slug"]
    if not slug:
        print("用法: python tools/report_to_flomo.py --slug <slug> [--out <文件>]", file=sys.stderr)
        sys.exit(1)

    title, domain = get_meta(slug)
    (tag1, tag2), _matched = pick_tags(domain)
    body = convert_full_report(slug)
    content = f"#知识基座 #{tag1} #{tag2}\n\n{body}"

    print("=" * 60, file=sys.stderr)
    print(f"flomo 完整转换 | slug: {slug}", file=sys.stderr)
    print(f"标题: {title}", file=sys.stderr)
    print(f"领域: {domain or '未记录'} | 标签: #{tag1} #{tag2}", file=sys.stderr)
    print(f"内容长度: {len(body)} 字符（完整报告，未截断）", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(file=sys.stderr)
    print(content)

    if args["out"]:
        out_path = args["out"]
        if not os.path.isabs(out_path):
            out_path = os.path.join(ROOT, "research", slug, out_path)
        # 保留已有 flomo id（如果存在）
        existing_id_comment = ""
        if os.path.exists(out_path):
            with open(out_path, encoding="utf-8") as f:
                head = f.read(200)
            m = re.search(r"(<!-- flomo id: \S+ \|[^>]+-->)", head)
            if m:
                existing_id_comment = m.group(1) + "\n"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(existing_id_comment + content + "\n")
        print(f"\n[已写] {out_path}", file=sys.stderr)

    # 查重决策规则提示（输出到 stderr，不污染 stdout/文件）
    print("\n查重决策规则（参考 mynews relevance 判断）：", file=sys.stderr)
    print("  relevance < 0.5  -> 直接新建 memo_create", file=sys.stderr)
    print("  0.5 <= r < 0.9   -> 主题相近，人工判断（已有本主题笔记则跳过，有增量则合并 update）", file=sys.stderr)
    print("  relevance >= 0.9  -> 高相似，已存在则跳过，有新内容则 memo_update", file=sys.stderr)

if __name__ == "__main__":
    main()
