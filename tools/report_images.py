
"""
研究报告配图工具（zhihu-ask 项目专用，，弃用 matplotlib 改 PIL）

把纯文本报告升级为「图文并茂」：为报告生成两类图片并插入 report.md。
1. AI 概念图（Agnes Image 2.1 Flash API，文生图）：封面主视觉/场景示意，
   由 prompt 驱动；当前定价 $0/张。
2. 数据图表（PIL 静态 PNG）：价格对比/指数对比/成本对比等，
   数据图表要求数字准确，不用 AI 生图（AI 生图不擅长精确数据）。

用法：
    python tools/report_images.py --slug <slug> [--api-key <key>] [--skip-ai] [--skip-charts]
    python tools/report_images.py --slug <slug> --chart-defs charts.json   # 自定义图表定义

环境：
- Agnes API key：--api-key 参数或环境变量 AGNES_API_KEY（推荐后者，凭证不入库）。
- 数据图表用 PIL（Pillow），无需 matplotlib（用户要求弃用 matplotlib）；
  PIL 是纯本地轻依赖，避免 venv/字体缓存等额外环境负担。
- 中文字体：自动探测 Windows 微软雅黑/SimHei、macOS PingFang、Linux Noto CJK。

输出：
- 图片落盘 research/<slug>/ 与 report.md 同级（AI 图 ai_*.png，图表 chart_*.png）。
- **AI 概念图仅作封面 ai_cover.png，独立存放不插入正文**；
  正文插图只用数据图表 chart_*.png，按内容锚点插入对应小节（插到小节标题后、内容前）。
- 知乎发布时图片上传后可保留相对引用或替换为图床 URL。

**AI 概念图硬性禁元素**：封面/题图必须为纯抽象视觉，
严禁任何语言文字、徽章与国徽、政府/司法/宗教建筑、货币与票据、真实人脸肖像、
国家/政治符号。`call_agnes` 末尾自动追加 `_AI_IMAGE_NEGATIVE_GUARD` 通用禁词句
确保所有 prompt 默认遵守；生成后必须肉眼复检（重点扫门楣/中央/边缘的圆形徽标
与飘字票据），发现违规立刻删除原图重生成——不要为了凑数保留违规图。完整检查
清单见 `docs/CHECKLIST.md` AI 概念图合规复检项。

图表定义（--chart-defs JSON，可选；缺省用内置默认模板）：
    {
      "charts": [
        {
          "title": "Muse Contributor vs V4 Flash 单价对比（美元/百万 token）",
          "kind": "bar_group",
          "filename": "chart_price.png",
          "groups": ["输入", "缓存输入", "输出"],
          "series": [
            {"label": "Muse Contributor", "values": [0.10, 0.002, 0.20]},
            {"label": "V4 Flash 官方", "values": [0.14, 0.0028, 0.28]}
          ],
          "unit": "$/M",
          "note": "数据：Meta 官方定价 / DeepSeek 价格页"
        }
      ]
    }
"""

import argparse
import json
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGNES_ENDPOINT = "https://apihub.agnes-ai.com/v1/images/generations"
AGNES_MODEL = "agnes-image-2.1-flash"

# AI 概念图严禁出现文字/数字/国徽/徽章/政府建筑/钞票/票据/
# 真实人脸/国旗/政治符号——实测 lof-exit-mechanism 封面曾出现中国国徽+飘字票据。
# 自动追加到每个 prompt 末尾，确保所有 AI 概念图（封面/题图/自定义 --ai-prompts）
# 默认遵守硬约束；具体 prompt 不必重复写 negative，工具会自动附加。
# 检查清单见 docs/CHECKLIST.md 「AI 概念图合规复检」项。
_AI_IMAGE_NEGATIVE_GUARD = (
    "\n\nNegative prompt (must obey): no text, no characters, no letters, no "
    "numbers, no digits, no Chinese characters, no Cyrillic, no Arabic script, "
    "no Japanese kana, no Korean hangul, no logogram, no logo, no watermark, "
    "no sign, no badge, no emblem, no national emblem, no flag, no coat of "
    "arms, no shield with symbols, no medal, no decoration, no coin, no "
    "banknote, no currency, no paper receipt, no ticket, no invoice, no price "
    "tag, no bond certificate, no government building, no courthouse, no "
    "parliament, no palace, no landmark building, no temple, no church, no "
    "mosque, no monument, no statue, no real human face, no portrait, no "
    "recognizable person, no political symbol, no party insignia, no slogan. "
    "Purely abstract visual elements only: geometric shapes, glowing curves, "
    "light particles, color gradients. Composition must be full and balanced: "
    "visual elements evenly fill the whole canvas, no large empty areas, no "
    "blank corners, no white space reserved for text overlay."
)

FONT_PATH_CANDIDATES = [
    r"C:/Windows/Fonts/msyh.ttc",
    r"C:/Windows/Fonts/msyhbd.ttc",
    r"C:/Windows/Fonts/simhei.ttf",
    r"C:/Windows/Fonts/simsun.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
]

def load_font(size):
    """加载中文字体（PIL），失败回退默认字体。返回 (font, usable)。"""
    from PIL import ImageFont
    for path in FONT_PATH_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size), True
            except Exception:
                continue
    return ImageFont.load_default(), False

def draw_text_center(draw, cx, y, text, font, fill):
    """PIL 无 textlength 的兼容写法（Pillow>=10 用 draw.textlength）。"""
    try:
        w = draw.textlength(text, font=font)
    except AttributeError:
        w = font.getbbox(text)[2] - font.getbbox(text)[0]
    draw.text((cx - w / 2, y), text, font=font, fill=fill)

def call_agnes(prompt, size="2K", ratio="16:9", api_key=None, timeout=300, retries=3):
    """调用 Agnes Image 2.1 Flash 文生图，返回图片 URL。网络波动时自动重试。

    AI 概念图严禁出现文字/数字/国徽/徽章/政府建筑/钞票/票据/
    真实人脸/国旗/政治符号——实测 lof-exit-mechanism 封面曾出现中国国徽+飘字票据。
    通用禁词句 `_AI_IMAGE_NEGATIVE_GUARD` 自动追加到所有 prompt 末尾，确保任何
    自定义 --ai-prompts 都默认遵守；具体 prompt 不必重复写 negative。生成后仍需
    肉眼复检（门楣/中央/边缘的圆形徽标与飘字票据），发现违规删图重生成。
    """
    key = api_key or os.environ.get("AGNES_API_KEY")
    if not key:
        raise RuntimeError("缺少 Agnes API key（--api-key 或环境变量 AGNES_API_KEY）")
    full_prompt = prompt + _AI_IMAGE_NEGATIVE_GUARD
    payload = {
        "model": AGNES_MODEL,
        "prompt": full_prompt,
        "size": size,
        "ratio": ratio,
        "extra_body": {"response_format": "url"},
    }
    import time
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                AGNES_ENDPOINT,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Authorization": f"Bearer {key}",
                         "Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            img_url = data.get("data", [{}])[0].get("url")
            if not img_url:
                raise RuntimeError(f"Agnes 响应无图片 URL: {data}")
            return img_url
        except Exception as e:
            last_err = e
            if attempt < retries - 1:
                print(f"  [重试] 第 {attempt + 1} 次失败: {e}")
                time.sleep(5)
    raise RuntimeError(f"Agnes 调用 {retries} 次均失败: {last_err}")

def download_image(url, out_path):
    """下载图片到本地。"""
    with urllib.request.urlopen(url, timeout=60) as resp:
        content = resp.read()
    with open(out_path, "wb") as f:
        f.write(content)
    return out_path

COLORS = ["#E64A3C", "#3B6FB5", "#2E8B57", "#C9A227", "#8E5FA8"]

def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

def draw_bar_group(chart, out_path):
    """分组柱状图：groups 为横轴分类，series 为多系列对比（PIL 绘制）。"""
    from PIL import Image, ImageDraw
    groups = chart["groups"]
    series = chart["series"]
    unit = chart.get("unit", "")
    title = chart.get("title", "")
    note = chart.get("note", "")

    W, H = 1440, 840
    margin_l, margin_r, margin_t, margin_b = 120, 60, 110, 140
    plot_w = W - margin_l - margin_r
    plot_h = H - margin_t - margin_b

    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    font_title = load_font(30)[0]
    font_axis = load_font(22)[0]
    font_val = load_font(19)[0]
    font_legend = load_font(21)[0]
    font_note = load_font(17)[0]

    all_vals = [v for s in series for v in s["values"] if v is not None]
    vmax = max(all_vals) * 1.15 if all_vals else 1
    if vmax <= 0:
        vmax = 1

    n = len(series)
    width = plot_w / (len(groups) * (n + 0.6))

    d.text((margin_l, 30), title, font=font_title, fill=(30, 30, 30))

    for gi, g in enumerate(groups):
        x0 = margin_l + gi * (plot_w / len(groups))
        for si, s in enumerate(series):
            v = s["values"][gi]
            if v is None:
                continue
            bw = width * 0.85
            bx = x0 + si * width + (plot_w / len(groups) - n * width) / 2
            bh = plot_h * (v / vmax)
            by = margin_t + plot_h - bh
            d.rectangle([bx, by, bx + bw, by + bh],
                        fill=hex_to_rgb(COLORS[si % len(COLORS)]))

            d.text((bx + bw / 2, by - 26), f"{v:g}",
                   font=font_val, fill=(60, 60, 60), anchor="mm")

        draw_text_center(d, x0 + plot_w / len(groups) / 2, margin_t + plot_h + 12,
                         g, font_axis, (60, 60, 60))

    d.text((margin_l - 12, margin_t + plot_h), "0", font=font_val,
           fill=(60, 60, 60), anchor="rm")
    d.text((margin_l - 12, margin_t), f"{vmax:.2g}", font=font_val,
           fill=(60, 60, 60), anchor="rm")

    d.line([margin_l, margin_t + plot_h, W - margin_r, margin_t + plot_h],
           fill=(150, 150, 150), width=2)
    d.line([margin_l, margin_t, margin_l, margin_t + plot_h],
           fill=(150, 150, 150), width=2)

    if unit:
        d.text((margin_l - 10, margin_t - 40), unit, font=font_axis,
               fill=(90, 90, 90), anchor="rm")

    lx = margin_l
    for si, s in enumerate(series):
        d.rectangle([lx, H - 105, lx + 26, H - 79],
                    fill=hex_to_rgb(COLORS[si % len(COLORS)]))
        d.text((lx + 34, H - 98), s["label"], font=font_legend, fill=(40, 40, 40))
        lx += 34 + draw_text_width(d, s["label"], font_legend) + 40

    if note:
        d.text((W - margin_r, H - 40), note, font=font_note,
               fill=(140, 140, 140), anchor="rm")
    img.save(out_path)

def draw_text_width(d, text, font):
    try:
        return d.textlength(text, font=font)
    except AttributeError:
        bb = d.textbbox((0, 0), text, font=font)
        return bb[2] - bb[0]

def draw_bar_single(chart, out_path):
    """单系列横向条形图（适合排序对比，PIL 绘制）。"""
    from PIL import Image, ImageDraw
    labels = chart["labels"]
    values = chart["values"]
    title = chart.get("title", "")
    unit = chart.get("unit", "")
    note = chart.get("note", "")

    n_items = len(labels)
    row_h = 56
    W = 1440
    H = 160 + n_items * row_h + 40
    margin_l, margin_r = 320, 80
    margin_t, margin_b = 110, 80
    plot_w = W - margin_l - margin_r
    plot_h = H - margin_t - margin_b

    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    font_title = load_font(30)[0]
    font_label = load_font(21)[0]
    font_val = load_font(19)[0]
    font_note = load_font(17)[0]

    vmax = max(values) * 1.15 if values else 1
    if vmax <= 0:
        vmax = 1
    d.text((margin_l, 30), title, font=font_title, fill=(30, 30, 30))
    for i, (label, v) in enumerate(zip(labels, values)):
        y = margin_t + i * row_h
        d.text((margin_l - 14, y + row_h / 2), label, font=font_label,
               fill=(50, 50, 50), anchor="rm")
        bw = plot_w * (v / vmax)
        d.rectangle([margin_l, y + 8, margin_l + bw, y + row_h - 8],
                    fill=hex_to_rgb(COLORS[0]))
        d.text((margin_l + bw + 8, y + row_h / 2), f"{v:g}{unit}",
               font=font_val, fill=(60, 60, 60), anchor="lm")
    d.line([margin_l, margin_t, margin_l, margin_t + plot_h],
           fill=(150, 150, 150), width=2)
    d.line([margin_l, margin_t + plot_h, W - margin_r, margin_t + plot_h],
           fill=(150, 150, 150), width=2)
    if note:
        d.text((W - margin_r, H - 36), note, font=font_note,
               fill=(140, 140, 140), anchor="rm")
    img.save(out_path)

def draw_scatter(chart, out_path):
    """散点图（斩杀线散点图示意：横轴成本、纵轴智能指数，PIL 绘制）。"""
    from PIL import Image, ImageDraw
    points = chart["points"]
    title = chart.get("title", "")
    xlabel = chart.get("xlabel", "单任务成本（美元）")
    ylabel = chart.get("ylabel", "智能指数")
    note = chart.get("note", "")
    kill_x = chart.get("kill_x")

    W, H = 1440, 960
    margin_l, margin_r, margin_t, margin_b = 140, 70, 120, 150
    plot_w = W - margin_l - margin_r
    plot_h = H - margin_t - margin_b

    xs = [p["x"] for p in points]
    ys = [p["y"] for p in points]
    xmax = max(xs) * 1.2 if xs else 1
    ymax = max(ys) * 1.15 if ys else 1
    if kill_x is not None:
        xmax = max(xmax, kill_x * 1.15)

    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    font_title = load_font(30)[0]
    font_label = load_font(19)[0]
    font_axis = load_font(21)[0]
    font_note = load_font(17)[0]

    def sx(v):
        return margin_l + plot_w * (v / xmax)

    def sy(v):
        return margin_t + plot_h - plot_h * (v / ymax)

    d.text((margin_l, 30), title, font=font_title, fill=(30, 30, 30))

    for i in range(5):
        gy = margin_t + plot_h * i / 4
        d.line([margin_l, gy, W - margin_r, gy], fill=(235, 235, 235), width=1)

    if kill_x is not None:
        kx = sx(kill_x)
        d.line([kx, margin_t, kx, margin_t + plot_h],
               fill=hex_to_rgb("#E64A3C"), width=3)
        d.text((kx + 6, margin_t + 8), "斩杀线", font=font_label,
               fill=hex_to_rgb("#E64A3C"))

    for p in points:
        px, py = sx(p["x"]), sy(p["y"])
        color = hex_to_rgb(p.get("color", "#3B6FB5"))
        r = 11
        d.ellipse([px - r, py - r, px + r, py + r], fill=color)
        d.text((px + 14, py - 10), p["label"], font=font_label,
               fill=(40, 40, 40))

    d.line([margin_l, margin_t + plot_h, W - margin_r, margin_t + plot_h],
           fill=(150, 150, 150), width=2)
    d.line([margin_l, margin_t, margin_l, margin_t + plot_h],
           fill=(150, 150, 150), width=2)

    d.text((margin_l + plot_w / 2, H - 60), xlabel, font=font_axis,
           fill=(60, 60, 60), anchor="mm")

    for i, ch in enumerate(ylabel):
        d.text((26, margin_t + plot_h / 2 - len(ylabel) * 14 / 2 + i * 14),
               ch, font=font_axis, fill=(60, 60, 60))
    if note:
        d.text((W - margin_r, H - 36), note, font=font_note,
               fill=(140, 140, 140), anchor="rm")
    img.save(out_path)

CHART_DRAWERS = {
    "bar_group": draw_bar_group,
    "bar_single": draw_bar_single,
    "scatter": draw_scatter,
}

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

DEFAULT_AI_PROMPTS = [
    {
        "name": "ai_cover",
        "alt": "研究报告封面：大模型『斩杀线』主视觉",
        "ratio": "16:9",
        "anchor": "__cover__",
        "prompt": (
            "科技感研究封面主视觉，宽幅 16:9：画面中央一道醒目的红色光刃斜劈而过"
            "（代表『斩杀线』），上方数枚发光 AI 芯片阵列代表高性价比模型胜出者，"
            "下方灰暗破碎的电路代表被淘汰者；背景深蓝黑色渐变星空与数据光流，"
            "画面整体构图饱满、平衡，无大面积空白区域，视觉元素均匀铺满整个画布，"
            "边角不留白；电影级打光，宏大构图，精密"
            "工业质感，高视觉密度，无文字水印"
        ),
    },
    {
        "name": "ai_killline",
        "alt": "AI 大模型『斩杀线』概念图",
        "ratio": "16:9",
        "anchor": "斩杀线的定义",
        "prompt": (
            "高信息密度科技概念图：大模型价格战『斩杀线』主题。画面中央一条发光的"
            "红色水平能量线横贯全图，线上方排列数枚明亮发光的 AI 芯片模型（代表高"
            "性价比胜出者），线下方模型呈灰色暗淡（代表被淘汰者）；右侧远处数据"
            "瀑布与价格标签若隐若现，深蓝黑背景，电影级打光，广角构图，精密工业"
            "质感，高视觉密度，无文字水印"
        ),
    },
    {
        "name": "ai_dualtier",
        "alt": "AI 模型双档定价对比概念图",
        "ratio": "16:9",
        "anchor": "Muse Spark 1.2",
        "prompt": (
            "高信息密度科技概念图：AI 模型双档定价对比主题。左侧一叠金色发光代币"
            "堆成高塔（标准档），右侧同款代币散落低塔（Contributor 折扣档），中"
            "间一道由细密数据流组成的隔断；深色科技背景，赛博感但克制，电影级"
            "打光，广角构图，高视觉密度，无文字水印"
        ),
    },
]

DEFAULT_CHARTS = [
    # 清空：历史遗留（muse 主题）图表定义已废弃，曾导致无 --chart-defs
    # 时自动把旧主题图表插进新报告（与 DEFAULT_AI_PROMPTS"斩杀线"同类隐患）。
    # 数据图表必须用 --chart-defs 显式定义（锚点对应当前报告小节），无默认图表。
]

def main():
    ap = argparse.ArgumentParser(description="研究报告配图工具（AI 概念图 + 数据图表，PIL 绘制）")
    ap.add_argument("--slug", required=True, help="研究报告 slug")
    ap.add_argument("--api-key", help="Agnes API key（推荐用环境变量 AGNES_API_KEY）")
    ap.add_argument("--skip-ai", action="store_true", help="跳过 AI 概念图（仅数据图表）")
    ap.add_argument("--skip-charts", action="store_true", help="跳过数据图表（仅 AI 概念图）")
    ap.add_argument("--chart-defs", help="自定义图表定义 JSON 文件")
    ap.add_argument("--ai-prompts", help="自定义 AI 提示词 JSON 文件")
    ap.add_argument("--embed-base64", action="store_true",
                    help="生成图片内嵌单文件 report_embedded.md（图片转 base64 data URI，"
                         "任何应用导入均能显示；解决相对路径图片在其他应用导入失败）")
    ap.add_argument("--url-base", metavar="BASE_URL",
                    help="图片公网 base URL，就地转换 report.md 为 URL 引用版（"
                         "不再产出 report_url.md 副本，报告目录只保留一个 report.md；"
                         "适合知乎/在线笔记发布——文件小、加载快；需先自行把图片部署到"
                         "公网静态托管，如 CloudStudio）")
    args = ap.parse_args()

    if args.url_base or args.embed_base64:
        args.skip_ai = True
        args.skip_charts = True

    slug = args.slug
    images_dir = ensure_images_dir(slug)
    inserted = []

    if not args.skip_ai:
        # 凭证加固：缺 key 时清晰提示，避免「静默失败让人误以为成功」
        if not (args.api_key or os.environ.get("AGNES_API_KEY")):
            print("[提示] 未检测到 AGNES_API_KEY，AI 概念图将失败。"
                  "配置 key 后重跑，或加 --skip-ai 仅生成数据图表。")
        ai_prompts = DEFAULT_AI_PROMPTS
        if args.ai_prompts:
            with open(args.ai_prompts, encoding="utf-8") as f:
                ai_prompts = json.load(f).get("prompts", ai_prompts)
        for item in ai_prompts:
            name = item["name"]
            alt = item.get("alt", name)
            prompt = item["prompt"]
            ratio = item.get("ratio", "16:9")
            anchor = item.get("anchor", "研究问题")
            caption = item.get("caption", alt)
            if anchor != "__cover__" and not caption.startswith("概念图"):
                caption = "概念图：" + caption  # AI 概念图图注必须标明"概念图"（硬性）
            out_path = os.path.join(images_dir, f"{name}.png")
            if os.path.exists(out_path):
                print(f"[跳过] {name}.png 已存在")
                inserted.append((f"{name}.png", alt, anchor, caption))
                continue
            print(f"[生成] AI 概念图 {name}（ratio={ratio}）…")
            try:
                url = call_agnes(prompt, size="2K", ratio=ratio, api_key=args.api_key)
                download_image(url, out_path)
                print(f"  已保存 {out_path}")
                inserted.append((f"{name}.png", alt, anchor, caption))
            except Exception as e:
                print(f"  [失败] {e}")

    if not args.skip_charts:
        charts = DEFAULT_CHARTS  # 默认图表为空：数据图表必须 --chart-defs 显式定义
        if args.chart_defs:
            with open(args.chart_defs, encoding="utf-8") as f:
                charts = json.load(f).get("charts", charts)
        elif not charts:
            print("[提示] 未提供 --chart-defs，跳过数据图表（无默认图表，纪律）")
        for chart in charts:
            kind = chart["kind"]
            filename = chart["filename"]
            anchor = chart.get("anchor", "研究问题")
            out_path = os.path.join(images_dir, filename)
            if os.path.exists(out_path):
                print(f"[跳过] {filename} 已存在")
                inserted.append((f"{filename}", chart.get("title", filename), anchor, chart.get("caption", chart.get("title", filename))))
                continue
            drawer = CHART_DRAWERS.get(kind)
            if not drawer:
                print(f"[失败] 未知图表类型: {kind}")
                continue
            try:
                drawer(chart, out_path)
                print(f"[生成] 数据图表 {filename}（{kind}）")
                inserted.append((f"{filename}", chart.get("title", filename), anchor, chart.get("caption", chart.get("title", filename))))
            except Exception as e:
                print(f"  [失败] {e}")

    if inserted:
        inject_images_by_anchor(slug, inserted)
    else:
        print("未生成任何图片。")

    if args.embed_base64:
        embed_images_base64(slug)

    if args.url_base:
        export_url_report(slug, args.url_base)

def export_url_report(slug, base_url):
    """把 report.md 相对路径图片替换为公网 URL，就地更新 report.md（用户要求
    文件名就用 report，不再产出 report_url.md 副本——报告目录只保留一个 report.md，
    其图片引用即发布用 https URL）。

    适用：知乎/公众号/在线笔记发布——在线应用不读本地文件，相对路径与 base64
    均不可靠；图片先部署到公网静态托管（如 CloudStudio），再把引用替换为
    https URL。文件仅几十 KB，加载快。
    """
    report_path = os.path.join(ROOT, "research", slug, "report.md")
    with open(report_path, encoding="utf-8") as f:
        content = f.read()
    base_url = base_url.rstrip("/")

    def repl(m):
        alt, path = m.group(1), m.group(2)
        if path.startswith(("http://", "https://", "data:")):
            return m.group(0)
        return f"![{alt}]({base_url}/{path})"

    new_content = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", repl, content)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print(f"已就地转换为 URL 引用版: {report_path}（{os.path.getsize(report_path) // 1024} KB）")

def embed_images_base64(slug):
    """把 report.md 中的相对路径图片替换为 base64 data URI，输出 report_embedded.md。

    适用于把 md 导入 Notion/飞书/语雀/公众号等在线应用（这些应用不读本地
    文件，相对路径图片必然失败）；内嵌后 md 为单文件自包含，任何 Markdown
    渲染器都能显示图片。代价：文件体积增大（图片 base64 约 +33%）。
    """
    import base64
    report_path = os.path.join(ROOT, "research", slug, "report.md")
    with open(report_path, encoding="utf-8") as f:
        content = f.read()

    def repl(m):
        alt, path = m.group(1), m.group(2)
        if path.startswith(("http://", "https://", "data:")):
            return m.group(0)
        img_path = os.path.join(ROOT, "research", slug, path)
        if not os.path.exists(img_path):
            print(f"  [警告] 图片不存在: {img_path}")
            return m.group(0)
        with open(img_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        ext = os.path.splitext(img_path)[1].lstrip(".").lower()
        mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
                "gif": "image/gif", "webp": "image/webp"}.get(ext, "image/png")
        print(f"  内嵌图片: {path}（{len(b64) // 1024} KB base64）")
        return f"![{alt}](data:{mime};base64,{b64})"

    new_content = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", repl, content)
    out_path = os.path.join(ROOT, "research", slug, "report_embedded.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print(f"已生成图片内嵌单文件: {out_path}（{os.path.getsize(out_path) // 1024} KB）")

if __name__ == "__main__":
    main()
