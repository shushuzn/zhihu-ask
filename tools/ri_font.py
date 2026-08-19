"""报告配图基础工具：中文字体加载 / 文本测量 / 颜色解析 / 图片下载（从 report_images.py 拆分）。"""
import os
import urllib.request


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
def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
def draw_text_width(d, text, font):
    try:
        return d.textlength(text, font=font)
    except AttributeError:
        bb = d.textbbox((0, 0), text, font=font)
        return bb[2] - bb[0]
def download_image(url, out_path):
    """下载图片到本地。"""
    with urllib.request.urlopen(url, timeout=60) as resp:
        content = resp.read()
    with open(out_path, "wb") as f:
        f.write(content)
    return out_path

