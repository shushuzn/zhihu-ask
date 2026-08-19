"""报告配图：PIL 静态数据图表绘制（从 report_images.py 拆分）。"""
from ri_font import (load_font, hex_to_rgb, draw_text_center, draw_text_width)


COLORS = ["#E64A3C", "#3B6FB5", "#2E8B57", "#C9A227", "#8E5FA8"]
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

