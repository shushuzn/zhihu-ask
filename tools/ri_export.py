"""报告配图：report.md 图片引用转换为公网 URL / base64 内嵌（从 report_images.py 拆分）。"""
import os
import re

from report_images import ROOT


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

