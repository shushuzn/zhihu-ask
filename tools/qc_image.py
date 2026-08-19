"""quality_check 子模块（从 quality_check.py 拆分）：qc_image 相关检查。"""
import re

def check_caption_sequence(body):
    """图注编号连贯性：正文「图 N｜」必须从 1 开始且连续递增，
    图片数（![...] 行）与图注数必须相等——封面图不插入正文、不参与编号，
    编号不得跳号（如封面占号导致首图从图 2 开始）。"""
    issues = []
    img_count = len(re.findall(r"!\[[^\]]*\]\([^)]+\)", body))
    caps = []
    for m in re.finditer(r"^图\s*(\d+)\s*｜", body, re.M):
        caps.append(int(m.group(1)))
    if not caps and img_count == 0:
        return issues
    if img_count != len(caps):
        issues.append((0, "图注数量不符",
                       f"图片 {img_count} 处但图注 {len(caps)} 条，应一一对应",
                       "图注规范"))
        return issues
    expected = list(range(1, len(caps) + 1))
    if caps != expected:
        issues.append((0, "图注编号不连续",
                       f"图注编号 {caps}，应从 1 连续递增到 {len(caps)}",
                       "图注规范"))
    return issues

def check_cover_ban(body):
    """AI 概念图禁止进正文：ai_*.png 只作独立封面文件
    ai_cover.png 供发布使用，report.md 正文不得出现对它们的图片引用（硬性拦截，
    不再允许"进正文+图注标概念图"的旧做法）。"""
    issues = []
    for m in re.finditer(r"!\[[^\]]*\]\(([^)]*ai[^)]*\.png)\)", body, re.M):
        line_no = body[:m.start()].count("\n") + 1
        issues.append((line_no, "概念图进正文",
                       "AI 概念图（ai_*.png）禁止插入 report.md 正文，封面仅作独立文件 ai_cover.png",
                       m.group(1)))
    return issues

def check_image_continuity(body):
    """图片连续性：正文任意两张图片之间必须有文字内容（非空行、非图注行），
    禁止两张图片连续——连续图片之间无过渡文字，破坏阅读节奏且无内容需求依据。
    图片数量应随内容需求而定，同小节通常只配一张图。"""
    issues = []
    lines = body.split("\n")
    img_positions = [i for i, l in enumerate(lines) if l.strip().startswith("![")]
    for j in range(len(img_positions) - 1):
        a, b = img_positions[j], img_positions[j + 1]
        between = lines[a + 1:b]
        text = [l for l in between
                if l.strip() and not re.match(r"^图\s*\d+\s*｜", l.strip())]
        if not text:
            issues.append((a + 2, "图片连续",
                           "两张图片之间无文字内容（禁止连续图片）",
                           f"图@{a + 1} 与 图@{b + 1}"))
    return issues

