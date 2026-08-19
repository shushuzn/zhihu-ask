"""报告配图：图片按内容锚点插入 report.md（从 report_images.py 拆分）。"""
import os
import re

from report_images import ROOT


def ensure_images_dir(slug):
    """图片目录 = 报告同级目录（用户要求图片不放进子文件夹，与 report.md 同级）。"""
    d = os.path.join(ROOT, "research", slug)
    os.makedirs(d, exist_ok=True)
    return d
def insert_block_into_content(content, anchor, block_lines, ai_only=False):
    """纯函数：把图片块插入锚点小节第一段正文之后（不紧跟标题行）。

    block_lines: 已编号的图片块行（如 ["![alt](rel)", "", "图 1｜说明"]）。
    返回 (new_content, status)：status ∈ inserted / fallback / missing_ai / missing。
    - inserted：锚点小节命中，插到第一段正文后
    - fallback：锚点缺失，插到首个 ### 小节前（旧式锚点结构已取消的回退）
    - missing_ai：锚点缺失且为 AI 概念图（仅作封面，不插入正文）
    - missing：锚点缺失且无 ### 小节可回退
    """
    block = "\n".join(block_lines) + "\n\n"
    pattern = re.compile(
        r"(^(?:#{1,6}\s*[^\n]*|\*\*[^\n]*)" + re.escape(anchor) + r"[^\n]*\n(?:.*?\n)*?)"
        r"(?=^#{1,6}\s|$)",
        re.M | re.S,
    )
    m = pattern.search(content)
    if m:
        # 插入点：锚点标题行后的第一段正文之后（图片不紧跟标题下一行）
        insert_at = m.end(1)
        tail = content[insert_at:]
        seg = re.match(r"\n*\s*([^\n]+(?:\n[^\n]+)*?)(?=\n\n|\n(?!#)|$)", tail, re.S)
        if seg:
            insert_at += seg.end()
        # 段落末尾补换行后再插图片块（block 自带末尾 \n\n）
        new_content = content[:insert_at] + "\n\n" + block + content[insert_at:].lstrip("\n")
        return new_content, "inserted"
    # 回退：锚点小节不存在（如旧式锚点结构已取消）时，插到第一个 ### 小节前。
    # AI 概念图（ai_*.png）仅作封面、不插入正文（规范），锚点未命中直接跳过。
    if ai_only:
        return content, "missing_ai"
    m2 = re.search(r"^###\s+[^\n]*\n", content, re.M)
    if m2:
        new_content = content[:m2.start()] + block + content[m2.start():]
        return new_content, "fallback"
    return content, "missing"
def inject_images_by_anchor(slug, images):
    """按内容锚点把图片插入 report.md 对应小节末尾（图片放正文合适位置，
    不再集中堆在「配图」节）。

    images: [(rel_path, alt, anchor)]，anchor 为匹配小节标题的关键词（如
    "斩杀线的定义" 匹配 `### 斩杀线的定义与出处`）。**规范**：每个锚点只允许
    一张图（多图会连续或贴标题，违反"图片不连续/不在标题下一行"规则）；
    图片插入锚点小节第一段正文之后（不紧跟标题行）。
    """
    report_path = os.path.join(ROOT, "research", slug, "report.md")
    with open(report_path, encoding="utf-8") as f:
        content = f.read()

    content = re.sub(r"^##\s*配图\s*\n(?:!\[[^\]]*\]\([^)]*\)\n*)+", "", content, flags=re.M)

    existing_max = max((int(n) for n in re.findall(r"图\s*(\d+)｜", content)), default=0)
    caption_n = existing_max

    from collections import OrderedDict
    groups = OrderedDict()
    for rel, alt, anchor, caption in images:
        groups.setdefault(anchor, []).append((rel, alt, caption))

    for anchor, items in groups.items():

        pending = []
        for rel, alt, caption in items:
            if f"]({rel})" in content:
                print(f"  [跳过] {rel} 已存在于 report.md")
            else:
                pending.append((rel, alt, caption))
        if not pending:
            continue

        if anchor == "__cover__":
            for rel, alt, caption in pending:
                print(f"  [跳过插入] {rel} 封面独立存放，不插入 report.md")
            continue

        if len(pending) > 1:
            raise SystemExit(f"[错误] 锚点「{anchor}」配了 {len(pending)} 张图——同一锚点只允许一张图"
                             f"（两张图必然连续或贴标题，违反规范）；请错开 anchor 使每个锚点唯一")
        lines = []
        for rel, alt, caption in pending:
            caption_n += 1
            lines.append(f"![{alt}]({rel})")
            lines.append("")
            lines.append(f"图 {caption_n}｜{caption}")

        ai_only = any(rel.startswith("ai_") for rel, _, _ in pending)
        new_content, status = insert_block_into_content(content, anchor, lines, ai_only=ai_only)
        if status == "inserted":
            content = new_content
            print(f"  图片插入小节「{anchor}」正文后 → report.md")
        elif status == "fallback":
            content = new_content
            print(f"  [回退] 未找到锚点「{anchor}」，图片插入首个小节前 → report.md")
        elif status == "missing_ai":
            for rel, _, _ in pending:
                print(f"  [跳过插入] {rel} AI 概念图仅作封面，未命中锚点不插入正文")
        else:
            print(f"  [警告] 未找到锚点小节「{anchor}」，跳过插入")

    content = re.sub(r"\n{3,}", "\n\n", content)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"已按锚点插入 {len(images)} 张图 → report.md")

