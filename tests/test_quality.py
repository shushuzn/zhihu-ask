"""quality_check.py 回归测试：每条规则的正向（必命中）/负向（必不命中）用例。

运行：python tests/test_quality.py
设计：每个 check_* 函数独立调用，互不污染（避免跨规则误报干扰断言）。
目标：锁定当前启发式行为，任何后续改动若改变判定即在此暴露。
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import quality_check as qc

PASS = 0
FAIL = 0

def expect(label, got, must_have):
    global PASS, FAIL
    ok = (len(got) > 0) == must_have
    if ok:
        PASS += 1
        # print(f"  ok  {label}")
    else:
        FAIL += 1
        print(f"  FAIL {label}: got {len(got)} issues, expected {'>0' if must_have else '==0'}")
        if got:
            for g in got[:3]:
                print(f"        {g}")

def has(issues, label):
    return [i for i in issues if i[1] == label]

# ---- 立场词 / 框架词 / 评价词 ----
expect("stance+ 我认为", has(qc.check_words("我认为这个判断很硬", qc.STANCE_WORDS, "立场词"), "立场词"), True)
expect("stance- 中性表述", has(qc.check_words("工信部于 2026 年发布通知", qc.STANCE_WORDS, "立场词"), "立场词"), False)
expect("stance- 论文证明这豁免", has(qc.check_words("论文证明这两类对象都能计算", qc.STANCE_WORDS, "立场词"), "立场词"), False)
expect("stance+ 这证明命中", has(qc.check_words("这证明该结论成立", qc.STANCE_WORDS, "立场词"), "立场词"), True)
expect("framework+ 综上所述", has(qc.check_words("综上所述，结论是", qc.FRAMEWORK_WORDS, "框架词"), "框架词"), True)
expect("eval+ 太离谱", has(qc.check_words("这太离谱了", qc.EVALUATIVE_WORDS, "评价词"), "评价词"), True)

# ---- 感叹号 / 反问句 ----
expect("excl+ 感叹号", qc.check_exclamation("这是真的！"), True)
expect("excl- 图片行感叹号跳过", qc.check_exclamation("![alt](url)!"), False)
expect("excl+ 反问句", qc.check_exclamation("难道这不是降价吗？"), True)
expect("excl- 普通问句", qc.check_exclamation("这是真的吗？"), False)
expect("excl- 行内公式阶乘", qc.check_exclamation("公式 $k!$ 与 $\\sqrt{k!}$ 混排"), False)
expect("excl- 块级公式阶乘", qc.check_exclamation("块级 $$\\sum_{k=0}^{n}(-1)^k k!\\,g^{-k-1}B_{n-i,k}$$ 公式"), False)

# ---- 无来源数字 ----
expect("num+ 约X元无来源", qc.check_unsourced_numbers("约 3000 亿元规模", "无来源区"), True)
expect("num- 带来源词", qc.check_unsourced_numbers("据披露约 3000 亿元", "无参考文献区"), False)
expect("num- 表格行跳过", qc.check_unsourced_numbers("| 约 3000 | 单位 |", "无参考文献区"), False)
expect("num- 有参考文献区则免检", qc.check_unsourced_numbers("约 3000 亿元", "正文\n## 参考文献\n[标题](url)"), False)

# ---- 模板占位符 ----
expect("ph+ {{}}", qc.check_placeholders("值={{name}}"), True)
expect("ph- 正常", qc.check_placeholders("正常文本"), False)

# ---- 过程性字样 ----
expect("proc+ 本轮", qc.check_process_words("本轮调研发现"), True)
expect("proc+ 通道A", qc.check_process_words("通道A 检索结果"), True)
expect("proc+ 第N轮", qc.check_process_words("第 3 轮完成"), True)
expect("proc- 电离通道", qc.check_process_words("电离通道传输稳定"), False)
expect("proc- 算力迭代", qc.check_process_words("算力迭代更新"), False)

# ---- AI 转折句式 ----
expect("turn+ 不是…而是", qc.check_turn_pattern("这不是涨价，而是存量清理"), True)
expect("turn- 独立否定", qc.check_turn_pattern("不是所有领域都有阈值"), False)

# ---- AI 腔句式 ----
expect("ai+ 随着发展", qc.check_ai_phrases("随着技术的发展，行业变革"), True)
expect("ai- 中性", qc.check_ai_phrases("技术持续进步明显"), False)

# ---- 段落过长 ----
expect("para+ 6行叙述", qc.check_paragraph_len("a\nb\nc\nd\ne\nf"), True)
expect("para- 5行叙述", qc.check_paragraph_len("a\nb\nc\nd\ne"), False)
expect("para- 有序列表7项", qc.check_paragraph_len("1. 积分定理：$\\int f\\,dt$\n2. 平移定理\n3. 逆变换\n4. Parseval\n5. Plancherel\n6. 微分\n7. 卷积"), False)

# ---- 标题括号 ----
expect("title+ 括号", qc.check_title_paren("# 标题（说明）"), True)
expect("title- 无括号", qc.check_title_paren("# 标题"), False)

# ---- 标题长度（≤30 字符） ----
expect("titlelen+ 31字", qc.check_title_len("# " + "甲" * 31), True)
expect("titlelen- 30字", qc.check_title_len("# " + "甲" * 30), False)
expect("titlelen- 短", qc.check_title_len("# 短标题"), False)
expect("titlelen+ 无H1", qc.check_title_len("### 小节标题\n正文"), False)

# ---- 提示性套话 ----
expect("hint+ 判断权留给读者", qc.check_judgment_hints("判断权留给读者"), True)
expect("hint- 自行判断", qc.check_judgment_hints("请自行判断"), False)

# ---- 元话语自称 ----
expect("meta+ 本报告", qc.check_meta_discourse("本报告认为"), True)
expect("meta- 该报告", qc.check_meta_discourse("该报告记载了"), False)

# ---- 内部标识 ----
expect("int+ gathered_", qc.check_internal_refs("见 gathered_wechat 素材"), True)
expect("int- 公开来源", qc.check_internal_refs("公开来源显示"), False)
expect("int+ 智慧芽", qc.check_internal_refs("智慧芽论文检索无直接相关"), True)
expect("int+ 产业无对应", qc.check_internal_refs("产业侧无对应物（企查查与通达信无适用主体）"), True)
expect("int+ 无适用主体", qc.check_internal_refs("通达信与企查查无适用主体"), True)
expect("int+ verify 脚本名", qc.check_internal_refs("结果见验证脚本 verify_check.py"), True)
expect("int- verify 正常语境", qc.check_internal_refs("数值结果如下"), False)

# ---- 分级词括注 ----
expect("grade+ 一手括注", qc.check_grade_paren("（一手数据）"), True)
expect("grade- 日本二手设备", qc.check_grade_paren("日本二手设备"), False)

# ---- 证据分级词 ----
expect("ev+ 证据较强", qc.check_evidence_grade("证据较强"), True)
expect("ev- 反方证据", qc.check_evidence_grade("反方证据明确"), False)

# ---- A 股行情信息 ----
expect("stock+ 代码", qc.check_stock_info("股票 603986 涨幅"), True)
expect("stock+ 现价", qc.check_stock_info("现价 12.5 元"), True)
expect("stock+ 总市值", qc.check_stock_info("总市值 300 亿"), True)
expect("stock- 年份", qc.check_stock_info("2026 年发布"), False)
expect("stock- 兑现价值", qc.check_stock_info("兑现价值 300 亿"), False)
expect("stock- 普通大数", qc.check_stock_info("普通大数 2828 亿"), False)

# ---- Unicode 手写公式（机检） ----
expect("math+ 积分符号", qc.check_math_formula("∫Ψ_x dx=π/2"), True)
expect("math+ 范数", qc.check_math_formula("∥T_even∥≤0.64"), True)
expect("math+ 平方上标", qc.check_math_formula("x²+y²=1"), True)
expect("math+ 希腊字母", qc.check_math_formula("β(φ)=−dφ/d ln z"), True)
expect("math- LaTeX 包裹", qc.check_math_formula("$\\int\\Psi_x\\,dx=\\pi/2$ 与 $e^{-s|x-y|}$"), False)
expect("math- 中文叙述 ≤", qc.check_math_formula("小节 ≤5 个、不带编号"), False)
expect("math- 图片引用行", qc.check_math_formula("![图1](images/a.png)"), False)
expect("math+ 表格内LaTeX公式", qc.check_math_formula("| 积分 | $\\int f\\,dt$ | $a$ |"), True)
expect("math+ 表格内Unicode公式", qc.check_math_formula("| 积分 | ∫f dt=√(2π) f̂(0) | a |"), True)
expect("math- 表格行无公式", qc.check_math_formula("| 维度 | 说明 |\n| 数学 | 偏好酉约定 |"), False)
expect("math- 无公式", qc.check_math_formula("纯文本叙述"), False)

# ---- 转述体/汇报腔（机检） ----
expect("trans+ 解读博客", qc.check_translation_voice("以下解读 John D. Cook 的博客文章。"), True)
expect("trans+ 文章价值", qc.check_translation_voice("Cook 文章的价值在于对照表。"), True)
expect("trans+ 论文讲了", qc.check_translation_voice("这篇论文讲了反例。"), True)
expect("trans+ 姊妹篇处理", qc.check_translation_voice("Cook 的姊妹篇处理相反问题。"), True)
expect("trans- 概念主体", qc.check_translation_voice("傅里叶变换有 8 种定义约定，三参数组合而成。"), False)
expect("trans- 数据转述", qc.check_translation_voice("媒体转述数字已回溯一手来源。"), False)
expect("trans- 无公式", qc.check_translation_voice("纯文本叙述。"), False)

# ---- 无主语开头（句首裸指代） ----
expect("subj+ 这篇裸指代", qc.check_subjectless_openers("这篇通过反例说明。"), True)
expect("subj+ 该篇裸指代", qc.check_subjectless_openers("该篇给出构造。"), True)
expect("subj+ 本篇裸指代", qc.check_subjectless_openers("本篇证明了结论。"), True)
expect("subj+ 此篇裸指代", qc.check_subjectless_openers("此篇介绍方法。"), True)
expect("subj+ 句号后裸指代", qc.check_subjectless_openers("前文已述。这篇补充细节。"), True)
expect("subj- 这篇论文有主语", qc.check_subjectless_openers("这篇论文通过反例说明。"), False)
expect("subj- 这篇文章有主语", qc.check_subjectless_openers("这篇文章给出构造。"), False)
expect("subj- 句中指代不拦", qc.check_subjectless_openers("正文中这篇论文被引用。"), False)
expect("subj- 带笔记名词", qc.check_subjectless_openers("这篇笔记记录踩坑。"), False)

# ---- 来源标注缺失（编号定理/定义须可追溯） ----
expect("src+ 无出处 Theorem", qc.check_source_attribution("Theorem 1.1 断言唯一性。"), True)
expect("src+ 无出处 Definition", qc.check_source_attribution("Definition 3.14 定义 bar code。"), True)
expect("src+ 无出处 中文定理", qc.check_source_attribution("定理 2.1 给出判据。"), True)
expect("src- 正文有 arXiv", qc.check_source_attribution("arXiv:2608.13526 中 Theorem 1.1 断言唯一性。"), False)
expect("src- 正文有书名号", qc.check_source_attribution("《某论文》的 Definition 3.14 定义 bar code。"), False)
expect("src- 无编号不拦", qc.check_source_attribution("定理与定义见参考文献。"), False)

# ---- 参考文献标注 ----
expect("ref+ 链接后带一手", qc.check_references("## 参考文献\n[标题](http://x) — 一手"), True)
expect("ref- 链接无标注", qc.check_references("## 参考文献\n[标题](http://x)"), False)
expect("ref- 无参考文献区", qc.check_references("无参考文献区"), False)

# ---- 参考文献区禁止 LaTeX ----
def ref_latex_hit(text, note_mode=False):
    return qc.check_ref_latex_ban(text, note_mode=note_mode)
expect("reflat+ 参考文献含LaTeX拦截",
       ref_latex_hit("## 参考文献\n[1] 佚名. 题名[EB/OL]. (2026-01-01)[2026-08-14]. https://x.org/a. 含 $\\lambda$."), True)
expect("reflat- 参考文献Unicode通过",
       ref_latex_hit("## 参考文献\n[1] 佚名. 题名[EB/OL]. (2026-01-01)[2026-08-14]. https://x.org/a. 含 λ₁ 值."), False)
expect("reflat- 无参考文献区",
       ref_latex_hit("正文含 $\\lambda$ 公式（正文允许 LaTeX）"), False)
expect("reflat+ 笔记来源段同样拦截",
       ref_latex_hit("来源:\n[1] 佚名. 题名[EB/OL]. (2026-01-01)[2026-08-14]. https://x.org/a. 含 $\\lambda$.", note_mode=True), True)

# ---- 结论长度（上限 300 字符） ----
expect("conclen+ 超300", qc.check_conclusion_len("# 结论\n\n" + "x" * 301), True)
expect("conclen- 300内", qc.check_conclusion_len("# 结论\n\n" + "x" * 300), False)
expect("conclen- 短", qc.check_conclusion_len("# 结论\n\n简短结论。"), False)

# ---- 结论风格 ----
expect("constyle+ 分点", qc.check_conclusion_style("# 结论\n\n- 点1\n- 点2"), True)
expect("constyle+ 分层", qc.check_conclusion_style("# 结论\n\n监管层面，加强监管。"), True)
expect("constyle- 一段式", qc.check_conclusion_style("# 结论\n\n事实是 A；事实是 B。"), False)

# ---- 交叉引用 ----
expect("xref+ 错号", qc.check_cross_ref("### 2.5 小节\n见 3.7 节补充"), True)
expect("xref- 对号", qc.check_cross_ref("### 2.5 小节\n见 2.5 节"), False)
expect("xref- 版本号", qc.check_cross_ref("Industry 5.0 应用"), False)

# ---- 事实小节预算（须含 H1：真实报告以 # 结论 开头）----
body_6sec = "# 结论\n\n简述。\n## 参考文献\n" + "".join(f"### 2.{i} 节\n正文。\n- 单行点\n" for i in range(1, 7))
expect("budget+ 6节+bullet", qc.check_fact_section_budget(body_6sec), True)
body_6sec_nobullet = "# 结论\n\n简述。\n## 参考文献\n" + "".join(f"### 2.{i} 节\n正文叙述。\n" for i in range(1, 7))
expect("budget- 6节无bullet", qc.check_fact_section_budget(body_6sec_nobullet), False)
body_2sec = "# 结论\n\n简述。\n## 参考文献\n### 2.1 节\n正文叙述段。\n### 2.2 节\n正文。\n"
expect("budget- 2节叙述", qc.check_fact_section_budget(body_2sec), False)

# ---- 结构完整性 ----
expect("struct+ 无参考文献", qc.check_structure("正文", "正文无参考文献"), True)
expect("struct+ 空参考文献", qc.check_structure("正文", "## 参考文献\n\n(空)"), True)
expect("struct- 有链接", qc.check_structure("正文", "## 参考文献\n[标题](http://x)\n"), False)
expect("struct+ TODO残留", qc.check_structure("此处待补充", "此处待补充\n## 参考文献\n[标题](http://x)"), True)

# ---- 图注序列 ----
expect("cap+ 数量不符",
       qc.check_caption_sequence("![图1](a.png)\n![图2](b.png)\n图 2｜说明"), True)
expect("cap- 一一对应", qc.check_caption_sequence("![图1](a.png)\n图 1｜说明"), False)
expect("cap- 无图无注", qc.check_caption_sequence("纯文本"), False)

# ---- 概念图禁令（AI 概念图禁止进正文） ----
expect("cover+ ai_cover.png 进正文",
       has(qc.check_cover_ban("![封面](ai_cover.png)\n图 1｜概念图：示意"), "概念图进正文"), True)
expect("cover+ ai_x.png 进正文",
       has(qc.check_cover_ban("![图1](ai_x.png)\n图 1｜概念图：示意"), "概念图进正文"), True)
expect("cover- 数据图不误报", qc.check_cover_ban("![图1](images/price.png)\n图 1｜说明"), False)
expect("cover- 无图", qc.check_cover_ban("纯文本"), False)

# ---- 图片连续性 ----
expect("imgcont+ 连续", qc.check_image_continuity("![a](x.png)\n![b](y.png)"), True)
expect("imgcont- 有文字", qc.check_image_continuity("![a](x.png)\n中间文字\n![b](y.png)"), False)

# ---- scan_body 截断：来源区之后不入正文 ----
import testutil
_tmp = testutil.mktestfile(suffix=".md")
with open(_tmp, "w", encoding="utf-8") as _f:
    _f.write("# 结论\n正文\n## 参考文献\n我认为这是来源区\n")
b, f = qc.scan_body(_tmp)
expect("scan- 来源区后不入正文", has(qc.check_words(b, qc.STANCE_WORDS, "立场词"), "立场词"), False)
os.unlink(_tmp)

# ---- 长段落建议分点（能用1234分点就用）----
long_para = ("# 结论\n\n概述。\n\n" +
             "规格一：上下文与输出参数说明，输入上限一百零四万八千五百七十六个 token，输出六万五千五百三十六。"
             "规格二：能力矩阵清单，缓存、代码执行、文件搜索、函数调用、接地、结构化输出、URL 上下文、推理档位均支持。"
             "规格三：推理档位说明，低档面向延迟敏感任务，中档为默认，高档最大化思考与工具使用。"
             "规格四：迭代节奏描述，距离上一代仅三周发布，官方称源于开发者反馈与算法创新。"
             "规格五：部署入口列举，包括 API、企业平台、智能体平台与订阅者个人智能体四个入口。"
             "规格六：迁移要点汇总，移除弃用采样参数，预算参数替换为档位枚举，多轮对话改用服务端标识。"
             "这一段超过三百字符用于触发建议分点的提示检查，应当被提示人工复核是否改为分点组织。")
expect("para+ 长段落提示", has(qc.check_para_points_eligible(long_para), "长段落建议分点"), True)
short_para = "# 结论\n\n概述。\n\n一段简短叙述。"
expect("para- 短段落不提示", has(qc.check_para_points_eligible(short_para), "长段落建议分点"), False)
listed_para = "# 结论\n\n1. 条目一。\n2. 条目二。\n3. 条目三。\n4. 条目四。"
expect("para- 已分点不提示", has(qc.check_para_points_eligible(listed_para), "长段落建议分点"), False)
table_para = "# 结论\n\n| 列1 | 列2 |\n|---|---|\n| a | b |"
expect("para- 表格段不提示", has(qc.check_para_points_eligible(table_para), "长段落建议分点"), False)

# ---- 标题禁止用 * 标记（flomo 笔记上传质检，笔记模式 check_title_asterisk）----
aster_body = ("# 技术 #AI #主题/x\n\n"
             "## 正常标题\n\n"
             "### 正常小标题\n\n"
             "正文里有 *斜体强调* 不应误报。\n\n"
             "- * 列表项不应误报\n\n"
             "| 列1 | 列2 |\n|---|---|\n")
expect("aster- 正常标题不命中", has(qc.check_title_asterisk(aster_body), "标题用*标记"), False)
aster_bad = ("# 技术 #AI #主题/x\n\n"
             "**## 用星号包裹的标题**\n\n"
             "*小标题用星号*\n\n"
             "### 标题含 *强调* 也命中\n")
expect("aster+ **## 标题** 命中", has(qc.check_title_asterisk(aster_bad), "标题用*标记"), True)
expect("aster+ *小标题* 命中", has(qc.check_title_asterisk("*小标题用星号*\n"), "标题用*标记"), True)
expect("aster+ ### 含* 命中", has(qc.check_title_asterisk("### 标题含 *强调* 也命中\n"), "标题用*标记"), True)

# ---- 标题禁止用 # 标记（flomo 笔记上传质检，笔记模式 check_title_hash）----
hash_body = ("#技术 #AI #主题/x\n\n"          # 首行 tag 行，# 后无空白，不命中
             "笔记标题纯文本\n\n"
             "正文段落不加 # 标题。\n\n"
             "- * 列表项不应误报\n\n"
             "| 列1 | 列2 |\n|---|---|\n")
expect("hash- tag行与纯文本标题不命中", has(qc.check_title_hash(hash_body), "标题用#标记"), False)
expect("hash- 正文斜体 *x* 不误报", has(qc.check_title_hash("正文里有 *斜体* 不误报\n"), "标题用#标记"), False)
hash_bad = ("#技术 #AI #主题/x\n\n"
            "## 大标题用#违规\n\n"
            "### 小标题用#违规\n\n"
            "# 单#也违规\n")
expect("hash+ ## 大标题命中", has(qc.check_title_hash(hash_bad), "标题用#标记"), True)
expect("hash+ ### 小标题命中", has(qc.check_title_hash("### 小标题也违规\n"), "标题用#标记"), True)
expect("hash+ # 单级命中", has(qc.check_title_hash("# 单级也违规\n"), "标题用#标记"), True)

# ---- 参考文献与正文引注一一对应（笔记模式 check_citation_correspondence）----
_cite_ok = ("#技术 #AI\n\n笔记标题\n\n某观点[1]。\n\n参考文献:\n"
            "[1] A. Title[EB/OL]. (2025-01-01)[2026-01-01]. https://x.com.\n")
_cite_missing = ("#技术 #AI\n\n笔记标题\n\n某观点[1]。\n\n参考文献:\n"
                 "[1] A. Title[EB/OL]. (2025-01-01)[2026-01-01]. https://x.com.\n"
                 "[2] B. Title[EB/OL]. (2025-01-01)[2026-01-01]. https://y.com.\n")
_cite_orphan = ("#技术 #AI\n\n笔记标题\n\n某观点[1][2]。\n\n参考文献:\n"
                "[1] A. Title[EB/OL]. (2025-01-01)[2026-01-01]. https://x.com.\n")
_cite_noref = "#技术 #AI\n\n笔记标题\n\n正文无参考文献。\n"
_rep_ok = ("报告标题\n\n某观点[1]。\n\n## 参考文献\n[1] A. Title[M]. 2025.\n")
expect("cite- note 一一对应通过",
       has(qc.check_citation_correspondence(_cite_ok, note_mode=True), "文献未被引用")
       or has(qc.check_citation_correspondence(_cite_ok, note_mode=True), "引用无对应文献"), False)
expect("cite+ note 文献未被引用(缺[2])",
       has(qc.check_citation_correspondence(_cite_missing, note_mode=True), "文献未被引用"), True)
expect("cite+ note 引用无对应文献(多[2])",
       has(qc.check_citation_correspondence(_cite_orphan, note_mode=True), "引用无对应文献"), True)
expect("cite- note 无参考文献段不触发",
       qc.check_citation_correspondence(_cite_noref, note_mode=True), False)
expect("cite- report 一一对应通过",
       has(qc.check_citation_correspondence(_rep_ok, note_mode=False), "文献未被引用")
       or has(qc.check_citation_correspondence(_rep_ok, note_mode=False), "引用无对应文献"), False)

print(f"\n==== quality_check 回归测试：PASS={PASS} FAIL={FAIL} ====")
sys.exit(1 if FAIL else 0)
