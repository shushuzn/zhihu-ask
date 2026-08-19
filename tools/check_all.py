
"""
全库一键体检工具：批量对所有成品报告跑结构校验 + 质量检查 + 轮次校验 + 落报告纪律
+ 结论长度 + docx 存在性（提示级，不判失败），输出汇总表，供交付前快速确认全库健康状态。

用法：
    python tools/check_all.py                 # 检查 research/*/report.md
    python tools/check_all.py --quiet         # 仅输出不达标报告
    python tools/check_all.py --offline       # 违规引用检查使用离线模式
    python tools/check_all.py --jobs 8        # 并行体检并发数（默认最多 4）
    python tools/check_all.py --quick         # 跳过工具自测/项目自检，快速体检

覆盖项：结构(struct) / 质量(qual) / 轮次(round) / 结论(conc) / 落报告(report_channels) / 去AI腔(aivoice) / 国标(gbt) / 违规引用(citv) / docx；项目自检（模板/脚本矛盾）在体检前执行。
其中「落报告」校验「已执行通道的素材是否落进 report.md 正文」（落报告纪律）；
「去AI腔」校验固定禁用表达（check_ai_voice.py 硬伤与提示级均判失败）；
「国标」校验参考文献 GB/T 7714-2015 著录合规（check_gbt_refs.py 硬伤与提示级均判失败）；
「违规引用」校验编造作者/题名不符/URL 伪造（check_citation_validity.py 联网核验，硬伤与提示级均判失败）。

额外在逐篇体检前先跑工具回归测试套件（tests/run_all.py）：覆盖 quality_check 全部规则、
report_channels 双向门禁、channel_state 登记、wechat 消费端防御与自动登记、arxiv 自动登记。
任一规则静默回退会连累每一篇报告或污染通道 ledger，故自测未过则中止逐篇体检。
修改任意被测工具后，先跑 `python tests/run_all.py` 确认无回归。
"""

import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

try:
    from tools.console_encoding import setup as _ce
    _ce()
except Exception:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESEARCH = os.path.join(ROOT, "research")

# 质量检查的「提示级」命中：需人工过目但不判硬失败（不影响质量列 OK）。
SOFT_HIT_KEYWORDS = ("无来源数字", "立场词", "长段落建议分点")

def find_reports(slugs=None):
    """找含 report.md 的研究目录。

    红线：默认【不扫描】research/ 旧报告——读取旧报告
    内容须用户显式授权。slugs=None 时返回空列表（不读取任何旧报告）；
    仅当调用方显式传 slugs（--slug）或开启 --all 时才扫描读取。
    """
    reports = []
    if not os.path.isdir(RESEARCH):
        return reports
    if slugs is None:
        return reports  # 未显式指定：不读取任何旧报告
    for slug in slugs:
        p = os.path.join(RESEARCH, slug, "report.md")
        if os.path.isfile(p):
            reports.append((slug, p))
    return reports

def classify_quality_hits(out):
    """从 quality_check 输出提取「硬性」命中行（提示级命中不算硬失败）。

    提示级命中（无来源数字/立场词）需人工过目、不判质量不达标；
    其余命中项（评价词/感叹号/框架词等）才计入硬失败。
    返回硬性命中行列表。
    """
    hits = re.findall(r"^\[[^\]]+\]\s*\d+\s*处", out, re.M)
    return [h for h in hits if not any(k in h for k in SOFT_HIT_KEYWORDS)]

def extract_conclusion(body):
    """从报告正文提取结论段落文本（标题行之后、首个标题行之前）。

    返回段落原文（可能为空串）；无标题行返回 None。
    注意两点：
    - 用 \\Z（绝对文末）而非 $——$ 在 MULTILINE 下匹配行尾，会把结论截断为仅首行，
      导致长度/bullet 检查只作用于第一行（潜藏漏检）。
    - 截止符用 ^#{2,6}\\s（任意标题行）而非 ^##\\s——报告正文为「H1→结论段→### 小节→## 参考文献」，
      ^##\\s 匹配不到 ### 小节，会把整篇正文吞进结论。
    """
    m = re.search(r"^# [^\n]*\n\n(.*?)(?=^#{2,6}\s|\Z)", body, re.S | re.M)
    return m.group(1) if m else None

def conclusion_ok(text):
    """结论段落校验：存在、≤300 字、不以 bullet 行开头。"""
    if text is None:
        return False
    if len(text.strip()) > 300:
        return False
    if re.search(r"^\s*[-*]\s+", text, re.M):
        return False
    return True

def run(cmd):
    """运行工具并返回 (exit_code, stdout)。"""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=120)
        return r.returncode, r.stdout
    except Exception as e:
        return -1, str(e)

def run_self_tests():
    """运行工具回归测试套件（tests/run_all.py）。

    放在逐篇体检之前，确保质检规则、通道门禁、登记逻辑本身未被改坏——
    规则静默回退会连累每一篇报告或污染通道 ledger。返回 True 表示全部通过。
    """
    runner = os.path.join(ROOT, "tests", "run_all.py")
    if not os.path.isfile(runner):
        print("[跳过] 未找到 tests/run_all.py，跳过工具自测。")
        return True
    code, out = run([sys.executable, runner])
    # run_all.py 结尾固定打印 TOTAL: PASS=... FAIL=...
    m = re.search(r"TOTAL.*FAIL=(\d+)", out)
    if (m and int(m.group(1)) == 0) or code == 0:
        print("[自测通过] 工具回归测试套件（详见上方各模块行）")
        return True
    print("[自测失败] 工具回归测试未全过，请先修复后再体检：")
    print(out[-1500:])
    return False

def run_project_check():
    """项目模板与脚本矛盾自检（check_consistency.py 查项目自身文件）。

    放在逐篇体检之前：项目文件（模板/脚本/文档）间的矛盾（工具引用缺失、
    旧通道表述、占位符未实现）会误导后续每篇报告的执行，须先清障。
    """
    code, out = run([sys.executable, os.path.join(ROOT, "tools", "check_consistency.py")])
    if code == 0:
        print("[项目自检通过] 模板与脚本无矛盾与废话")
        return True
    print("[项目自检失败] 模板/脚本存在矛盾或废话：")
    print(out[-1500:])
    return False

def check_one_report(slug, path, offline):
    """对单篇报告执行全部体检，返回汇总行所需字段。"""
    issues = []

    code, out = run([sys.executable, os.path.join(ROOT, "tools", "check_report_structure.py"), "--file", path])
    struct_ok = code == 0
    if not struct_ok:
        issues.append("结构")

    code, out = run([sys.executable, os.path.join(ROOT, "tools", "quality_check.py"), "--file", path])
    hard_hits = classify_quality_hits(out)
    qual_ok = code == 0 or not hard_hits
    if not qual_ok:
        issues.append("质量")

    code, out = run([sys.executable, os.path.join(ROOT, "tools", "check_progress.py"), "--slug", slug, "--require_round", "auto"])
    round_ok = code == 0
    if not round_ok:
        issues.append("轮次")

    code, out = run([sys.executable, os.path.join(ROOT, "tools", "check_progress.py"), "--slug", slug, "--require", "report_channels"])
    report_ok = code == 0
    if not report_ok:
        issues.append("落报告")

    code, out = run([sys.executable, os.path.join(ROOT, "tools", "check_ai_voice.py"), "--file", path])
    aivoice_ok = code == 0
    if not aivoice_ok:
        issues.append("AI腔")

    code, out = run([sys.executable, os.path.join(ROOT, "tools", "check_gbt_refs.py"), "--file", path])
    gbt_ok = code == 0
    if not gbt_ok:
        issues.append("国标")

    citv_cmd = [sys.executable, os.path.join(ROOT, "tools", "check_citation_validity.py"), "--file", path]
    if offline:
        citv_cmd.append("--offline")
    code, out = run(citv_cmd)
    citv_ok = code == 0
    if not citv_ok:
        issues.append("违规引用")

    body = open(path, encoding="utf-8").read()
    conc_text = extract_conclusion(body)
    conc_ok = conclusion_ok(conc_text)
    if not conc_ok:
        issues.append("结论")

    docx_path = os.path.join(RESEARCH, slug, "report.docx")
    docx_note = ""
    if not os.path.isfile(docx_path):
        docx_note = "（docx 未生成）"

    return {
        "slug": slug,
        "struct_ok": struct_ok,
        "qual_ok": qual_ok,
        "round_ok": round_ok,
        "report_ok": report_ok,
        "aivoice_ok": aivoice_ok,
        "gbt_ok": gbt_ok,
        "citv_ok": citv_ok,
        "conc_ok": conc_ok,
        "issues": issues,
        "docx_note": docx_note,
    }


def main():
    quiet = "--quiet" in sys.argv
    offline = "--offline" in sys.argv
    quick = "--quick" in sys.argv
    # 红线：默认不扫描旧报告。读取报告内容须显式授权：
    #   --slug <slug>   仅检查指定 slug（可重复）
    #   --all           显式启用全库扫描（用户自主决定）
    slugs = []
    argv = sys.argv
    i = 1
    all_reports = False
    jobs = None
    while i < len(argv):
        if argv[i] == "--slug" and i + 1 < len(argv):
            slugs.append(argv[i + 1])
            i += 2
        elif argv[i] == "--all":
            all_reports = True
            i += 1
        elif argv[i] == "--jobs" and i + 1 < len(argv):
            try:
                jobs = max(1, int(argv[i + 1]))
            except ValueError:
                jobs = None
            i += 2
        else:
            i += 1

    if quick:
        print("[快速模式] 跳过工具自测与项目自检，直接体检。")
    else:
        self_ok = run_self_tests()
        if not self_ok:
            print("-" * 78)
            print("因工具自测未通过，中止逐篇体检（质检结果不可信）。")
            return 1

        # 项目自检（check_consistency 查项目模板与脚本，非报告正文）
        proj_ok = run_project_check()
        if not proj_ok:
            print("-" * 78)
            print("因项目模板/脚本检查未通过，中止逐篇体检（项目文件存在矛盾）。")
            return 1

    if not slugs and not all_reports:
        print("[提示] 默认不扫描旧报告（读取报告内容须显式授权，纪律）。")
        print("  指定 --slug <slug> 检查单篇，或 --all 显式启用全库扫描。")
        return 0

    if all_reports:
        reports = []
        if os.path.isdir(RESEARCH):
            reports = [(n, os.path.join(RESEARCH, n, "report.md"))
                       for n in sorted(os.listdir(RESEARCH))
                       if os.path.isfile(os.path.join(RESEARCH, n, "report.md"))]
    else:
        reports = find_reports(slugs)
    if not reports:
        print("未找到指定 research/<slug>/report.md")
        return 1

    print("=" * 78)
    print(f"全库体检: {len(reports)} 篇报告")
    print("=" * 78)
    header = f"{'slug':<38}{'结构':<6}{'质量':<6}{'轮次':<6}{'结论':<6}{'落报告':<6}{'AI腔':<6}{'国标':<6}{'违规引':<6}{'问题数'}"
    print(header)
    print("-" * 78)

    bad_total = 0
    # 多篇报告时并行执行各篇的子进程检查；保留输入顺序输出。
    # --jobs 可手动控制并发数，默认最多 4。
    workers = jobs or (min(4, len(reports)) if len(reports) > 1 else 1)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = pool.map(lambda r: check_one_report(r[0], r[1], offline), reports)
        for res in results:
            n = len(res["issues"])
            bad_total += n
            if not quiet or n > 0:
                print(f"{res['slug']:<38}{'OK' if res['struct_ok'] else 'X':<6}"
                      f"{'OK' if res['qual_ok'] else 'X':<6}{'OK' if res['round_ok'] else 'X':<6}"
                      f"{'OK' if res['conc_ok'] else 'X':<6}{'OK' if res['report_ok'] else 'X':<6}"
                      f"{'OK' if res['aivoice_ok'] else 'X':<6}{'OK' if res['gbt_ok'] else 'X':<6}"
                      f"{'OK' if res['citv_ok'] else 'X':<6}{n}{res['docx_note']}")

    print("-" * 78)
    print(f"汇总: {len(reports)} 篇 | 问题项 {bad_total} | {'全库健康' if bad_total == 0 else '存在问题，见上'}")
    return 0 if bad_total == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
