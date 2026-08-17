#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""去 AI 腔自动检查（用户「中文写作去 AI 腔」规则固化）。

两级检出：
- [硬伤] 固定禁用表达（空转过渡 / 开头预告 / 「一句话」类 / 对词动手术 /
  标题禁词 / 自问后垫宣告 / 「先说·先给·先看」宣告）——命中即退出码 1。
- [提示] 启发式（装饰词 / 转折词 / 对称排比 / 「不是 X，是 Y」立靶子句式 /
  破折号长插入语与扎堆 / 引号包裹日常词）——默认同样阻断（严格阻断为默认），
  命中需人工确认（如「但」多为真实转折、「关键」可能是合法术语语境）。

与 quality_check.py 互补：该工具已覆盖的立场词/框架词/评价词/AI 因果句式不在此重复。

用法: python tools/check_ai_voice.py (--file <文件> | --slug <slug>) [--verbose] [--skip-source-voice]

--skip-source-voice: 原文应用类报告（访谈转述/文章整理/翻译稿）专用——
  跳过提示级表述检查（装饰词/转折词/对称排比/破折号/引号包裹日常词），
  因这类表述多忠实来自原文，启发式会大量误伤；硬伤检查（固定禁用表达/标题禁词）始终保留。
"""
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)
except Exception:
    pass

# ---- 硬伤：固定禁用表达（命中即阻断） -------------------------------------
HARD_PATTERNS = [
    # 空转过渡
    (r"需要强调的是|需要指出的是|众所周知|说到底|归根结底|划重点|强调一下|强调一句",
     "空转过渡（需要强调的是/众所周知/说到底/归根结底/划重点）"),
    # 开头预告（话说到前头族）
    (r"话说到前头|话说在前头|先说在前头|把话说前头|把话说在前头|话说回来|说在前头",
     "开头预告（话说到前头/话说在前头/说在前头/话说回来）"),
    # 「一句话」类
    (r"一句话|就一句话|核心建议只有一句|一句话讲清|一句话总结",
     "「一句话」类禁用（直接说内容即可）"),
    # 对词动手术
    (r"把[^，。；]{1,20}?(词|概念|说法)[^，。；]{0,8}(拆开|拆解|解构|厘清|界定)",
     "对词动手术（把 X 这个词拆开…，宾语应换回世界里的实事）"),
    (r"(拆解|解构|厘清|界定)[^，。；]{1,15}(概念|这个词|这个说法)",
     "对词动手术（拆解/厘清 X 概念，宾语应换回世界里的实事）"),
    # 自问后垫宣告
    (r"为什么[^。？！]{0,18}[？?]\s*(背后是|原因有三|原因有|有几点|归结为)",
     "自问后垫宣告（为什么…？背后是/原因有三，应直接写一/二/三）"),
    # 「先说/先给/先看」宣告
    (r"先说[^，。；]{0,8}(漂亮|不好|坏处|好处|缺点|优点|结果|答案)",
     "「先说…」宣告（说出的顺序即顺序，不宣告）"),
    (r"先给(结论|答案|数字|结果|建议)", "「先给…」宣告"),
    (r"先看(数据|结果|打新|数字|反面|正面)", "「先看…」宣告"),
    # 「不是 X，而是 Y」AI腔句式
    (r"不是.{1,20}(而是|是)", "「不是 X，而是 Y」AI腔句式（禁止使用，改直说）"),
]

# 标题（# 开头行）禁词：先/必须/清楚/反直觉（用户：标题最招摇，直接写结论或主题）
TITLE_BANNED = [
    (r"必须", "标题含「必须」"),
    (r"反直觉", "标题含「反直觉」"),
    (r"清楚|说清|讲清", "标题含「清楚/说清/讲清」"),
    (r"先(把|给|看|说|弄|搞|理)", "标题含「先…」宣告式开头"),
]

# ---- 提示：启发式（默认同样阻断） ----------------------------
WARN_PATTERNS = [
    (r"非常(?!数|规)|大大|革命性|全方位", "装饰词（非常/大大/革命性/全方位；「非常数/非常规」为术语组合，豁免）"),
    (r"(?:核心|至关重要)(?!关系|原则|组件|组成部分|功能|价值|优势|能力|环节|步骤|问题|矛盾|要点|目标|任务|内容|思想|理念|精神|要义|本质|特征|特点|属性|机制|原理|规律|法则|方法|途径|路径|方向|趋势|前景|潜力|空间|领域|范围|要素|因素|条件|基础|前提|保障|支撑|动力|源泉|来源|依据|证据|理由|原因|目的|意义|作用|影响|效果|结果|后果|效益|效率|质量|水平|程度|状态|情况|形势|局面|格局|态势|动向|变化|发展|进步|提升|提高|增强|加强|巩固|完善|优化|改进|改革|创新|突破|进展|成就|成果|成绩|贡献|地位|角色|职能|职责|任务|使命|责任|担当|作为|表现|行动|举措|措施|办法|手段|方式|形式|模式|类型|种类|类别|层次|级别|档次|标准|规范|规则|制度|体制|体系|系统|网络|平台|载体|工具|途径|渠道|目标|目的|宗旨|原则|方针|政策|战略|策略|战术|计划|方案|规划|设计|布局|安排|部署|推进|实施|执行|落实|完成|实现|达到|取得|获得|赢得|创造|产生|形成|构成|组成|包含|包括|涵盖|涉及|关系|联系|关联|相关|相应|对应|匹配|适应|符合|满足|成功|胜利|重要性|必要性|可行性|合理性|有效性|可靠性|稳定性|安全性|持久性|可持续性|先进性|科学性|系统性|全面性|整体性|协调性|统一性|一致性|连贯性|逻辑性|严密性|精确性|准确性|客观性|公正性|公平性|公开性|透明度|可及性|可得性|可达性|可用性|实用性|适用性|针对性|实效性|时效性|及时性|便捷性|高效性|经济性|节约性|环保性|绿色性|低碳性|循环性|再生性|可回收性|可降解性|可分解性|可处理性|可处置性|可利用性|可开发性|可挖掘性|可拓展性|可扩展性|可延伸性|可延展性|可伸缩性|可调节性|可控制性|可管理性|可操作性|可执行性|可实施性|可推行性|可推广性|可复制性|可借鉴性|可参考性|可学习性|可模仿性|可效仿性|可参照性|可对比性|可比较性|可衡量性|可测量性|可评估性|可评价性|可考核性|可检验性|可验证性|可证实性|可证伪性|可反驳性|可质疑性|可讨论性|可争议性|可辩论性|可商榷性|可斟酌性|可推敲性|可琢磨性|可研究性|可探索性|可发现性|可揭示性|可阐明性|可解释性|可理解性|可接受性|可认可性|可赞同性|可支持性|可拥护性|可赞成性|可肯定性|可否定性|可批判性)", "装饰词（核心/至关重要；合法术语语境豁免）"),
    (r"(?:关键)(?!词|步骤|阶段|环节|要素|因素|条件|基础|前提|保障|支撑|动力|源泉|来源|依据|证据|理由|原因|目的|意义|价值|作用|影响|效果|结果|后果|效益|效率|质量|水平|程度|状态|情况|形势|局面|格局|态势|趋势|动向|变化|发展|进步|提升|提高|增强|加强|巩固|完善|优化|改进|改革|创新|突破|进展|成就|成果|成绩|贡献|地位|角色|职能|职责|任务|使命|责任|担当|作为|表现|行动|举措|措施|办法|手段|方式|形式|模式|类型|种类|类别|层次|级别|档次|标准|规范|规则|制度|体制|体系|系统|网络|平台|载体|工具|途径|渠道|目标|目的|宗旨|原则|方针|政策|战略|策略|战术|计划|方案|规划|设计|布局|安排|部署|推进|实施|执行|落实|完成|实现|达到|取得|获得|赢得|创造|产生|形成|构成|组成|包含|包括|涵盖|涉及|关系|联系|关联|相关|相应|对应|匹配|适应|符合|满足|成功|胜利|重要性|必要性|可行性|合理性|有效性|可靠性|稳定性|安全性|持久性|可持续性|先进性|科学性|系统性|全面性|整体性|协调性|统一性|一致性|连贯性|逻辑性|严密性|精确性|准确性|客观性|公正性|公平性|公开性|透明度|可及性|可得性|可达性|可用性|实用性|适用性|针对性|实效性|时效性|及时性|便捷性|高效性|经济性|节约性|环保性|绿色性|低碳性|循环性|再生性|可回收性|可降解性|可分解性|可处理性|可处置性|可利用性|可开发性|可挖掘性|可拓展性|可扩展性|可延伸性|可延展性|可伸缩性|可调节性|可控制性|可管理性|可操作性|可执行性|可实施性|可推行性|可推广性|可复制性|可借鉴性|可参考性|可学习性|可模仿性|可效仿性|可参照性|可对比性|可比较性|可衡量性|可测量性|可评估性|可评价性|可考核性|可检验性|可验证性|可证实性|可证伪性|可反驳性|可质疑性|可讨论性|可争议性|可辩论性|可商榷性|可斟酌性|可推敲性|可琢磨性|可研究性|可探索性|可发现性|可揭示性|可阐明性|可解释性|可理解性|可接受性|可认可性|可赞同性|可支持性|可拥护性|可赞成性|可肯定性|可否定性|可批判性)", "装饰词（关键；合法术语语境豁免）"),
    (r"其实", "转折词（其实；非真转折应删）"),
    (r"然而|不过", "转折词（然而/不过；非真转折应删）"),
    (r"(?<!不)(?<!凡)(?<!愿)(?<!非)但", "转折词（但；非真转折应删）"),
    (r"既[^，。；]{2,15}又", "对称排比（既…又…，改直说）"),
    (r"不仅[^，。；]{2,20}而且", "对称排比（不仅…而且…，改直说）"),
    (r"一方面[^，。；]{2,20}另一方面", "对称排比（一方面…另一方面…，改直说）"),

    (r"还有一个[^，。；]{0,12}(关键|容易被看漏|值得注意)", "预设「关键/被看漏」（直接说，或只用「还有一点」）"),
    (r"重新定义", "对词动手术（重新定义；确认宾语是实事还是概念）"),
]

# 引号包裹的日常词（短引号 1–8 字；术语/反讽/非字面义引号合规，不在清单）
# 注：不放领域术语（如「回归」在 ML 语境是术语），只放跨领域日常词。
COMMON_QUOTED_WORDS = [
    "消失", "变了", "增长", "风险", "影响", "下降", "提升",
    "成功", "失败", "上涨", "下跌", "泡沫", "退市",
]


def resolve_target(argv, tool_name, extra_usage=""):
    """解析 --file / --slug（互为别名），与 quality_check.py 一致。"""
    filepath = None
    if "--file" in argv:
        idx = argv.index("--file")
        if idx + 1 < len(argv):
            filepath = argv[idx + 1]
    if not filepath and "--slug" in argv:
        idx = argv.index("--slug")
        if idx + 1 < len(argv):
            root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            filepath = os.path.join(root, "research", argv[idx + 1], "report.md")
    if not filepath or not os.path.exists(filepath):
        print(f"用法: python tools/{tool_name} (--file <文件> | --slug <slug>){extra_usage}")
        if filepath:
            print(f"  [错误] 文件不存在: {filepath}")
        sys.exit(1)
    return filepath


def read_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


def scan_lines(text):
    """逐行扫描正文，跳过图片引用行与表格行。

    ## 参考文献 区（模板规定为文件末尾唯一顶层章节）不适用正文行检查：
    著录的题名可含合法标点（如破折号、引号），且不属叙述行，自该标题起截断。
    """
    out = []
    for l in text.splitlines():
        if l.strip().startswith("## 参考文献"):
            break
        if l.strip().startswith("![") or l.strip().startswith("|"):
            continue
        out.append(l)
    return out


def check_hard(body):
    """硬伤：固定禁用表达（逐行，首个命中即记）。返回 (行号, 规则标签, 命中子串, 行预览)。"""
    issues = []
    lines = scan_lines(body)
    for i, line in enumerate(lines, 1):
        for pat, label in HARD_PATTERNS:
            m = re.search(pat, line)
            if m:
                issues.append((i, label, m.group(0)[:40], line.strip()[:70]))
                break
    return issues


def check_title_words(body):
    """硬伤：标题行禁词（先/必须/清楚/反直觉）。返回 (行号, 规则标签, 命中子串, 行预览)。"""
    issues = []
    for i, line in enumerate(body.splitlines(), 1):
        if line.strip().startswith("## 参考文献"):
            break
        if not line.startswith("#") or line.startswith("#!"):
            continue
        for pat, label in TITLE_BANNED:
            m = re.search(pat, line)
            if m:
                issues.append((i, label, m.group(0)[:40], line.strip()[:70]))
                break
    return issues


def check_warn(body):
    """提示：启发式表达（逐行，首个命中即记）。返回 (行号, 规则标签, 命中子串, 行预览)。"""
    issues = []
    lines = scan_lines(body)
    for i, line in enumerate(lines, 1):
        for pat, label in WARN_PATTERNS:
            m = re.search(pat, line)
            if m:
                issues.append((i, label, m.group(0)[:40], line.strip()[:70]))
                break
    return issues


def check_dashes(body):
    """提示：破折号长插入语 / 段内扎堆。返回 (行号, 规则标签, 命中子串, 行预览)。"""
    issues = []
    for i, line in enumerate(scan_lines(body), 1):
        # 长插入语：破折号后第一个完整小句（到句末标点为止）超过 25 字
        for m in re.finditer(r"——+([^——。！？]*。?)", line):
            tail = m.group(1).strip()
            if len(tail) > 25:
                issues.append((i, "破折号长插入语（>25 字，应改冒号或拆句）", m.group(0)[:40], line.strip()[:70]))
    # 同行 ≥2 个破折号即提示扎堆
    for i, line in enumerate(scan_lines(body), 1):
        if line.count("——") >= 2:
            issues.append((i, "破折号扎堆（同行 ≥2 处）", "——", line.strip()[:70]))
    return issues


def check_quotes(body):
    """提示：引号包裹日常词（短引号 1–8 字，且整段引号内容本身就是日常词才报）。

    注意：仅当引号内容整体为清单内日常词时命中（如 `"成功"`/`"消失"`）；
    引号内嵌术语性短语（如 `"在首次成功处停止"`，`成功` 为概率论术语语境）不报，
    避免 `cw in word` 子串匹配误伤合法长引号表述。
    返回 (行号, 规则标签, 命中子串, 行预览)。
    """
    issues = []
    for i, line in enumerate(scan_lines(body), 1):
        for m in re.finditer(r'"([^"\n]{1,8})"', line):
            word = m.group(1)
            if word in COMMON_QUOTED_WORDS:
                issues.append((i, f"引号包裹日常词（{word}；日常词不加引号）", f'"{word}"', line.strip()[:70]))
    return issues


def main():
    argv = sys.argv[1:]
    verbose = "--verbose" in argv
    skip_source_voice = "--skip-source-voice" in argv
    filepath = resolve_target(argv, "check_ai_voice.py",
                              " [--verbose] [--skip-source-voice]")

    body = read_file(filepath)
    if not body.strip():
        print(f"[跳过] {filepath}: 文件为空")
        sys.exit(0)

    hard = check_hard(body) + check_title_words(body)
    if skip_source_voice:
        # 原文应用类报告：表述来自原文，跳过提示级表述检查，仅保留硬伤。
        warn = []
        print("[提示] --skip-source-voice 已启用：跳过装饰词/转折词/破折号/引号表述检查（硬伤检查保留）。")
    else:
        warn = check_warn(body) + check_dashes(body) + check_quotes(body)

    print("=" * 60)
    print(f"去 AI 腔自动检查: {filepath}")
    print("=" * 60)

    if not hard and not warn:
        print("全部通过：未检出硬伤与提示级命中。")
        sys.exit(0)

    if hard:
        print(f"\n[硬伤] {len(hard)} 处（命中即阻断，需修复）")
        for item in hard:
            print(f"  行{item[0]} 命中「{item[2]}」  [{item[1]}]")
            if verbose:
                print(f"    原文: {item[3]}")
    if warn:
        print(f"\n[提示] {len(warn)} 处（启发式，默认同样阻断）")
        for item in warn:
            print(f"  行{item[0]} 命中「{item[2]}」  [{item[1]}]")
            if verbose:
                print(f"    原文: {item[3]}")

    print("\n提示：提示级命中为启发式检出，需人工确认是否真正违规")
    print("（如「但」多为真实转折、「关键」可能是合法术语语境；引号若为非字面义/术语首现属合规）。")
    if hard or warn:
        print("退出码 1。")
        sys.exit(1)
    print("退出码 0（无命中）。")
    sys.exit(0)


if __name__ == "__main__":
    main()
