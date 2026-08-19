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
清单与合规复检要求见 `templates/research_report_TEMPLATE.md` 配图条。

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

from ri_font import (load_font, draw_text_center, hex_to_rgb, draw_text_width, download_image)
from ri_ai import call_agnes
from ri_chart import (draw_bar_group, draw_bar_single, draw_scatter, CHART_DRAWERS, COLORS)
from ri_inject import (ensure_images_dir, insert_block_into_content, inject_images_by_anchor)
from ri_export import (export_url_report, embed_images_base64)


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


if __name__ == "__main__":
    main()
