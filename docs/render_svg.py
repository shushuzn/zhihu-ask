import os
from playwright.sync_api import sync_playwright

html_path = r"D:\OpenClaw\zhihu-ask\docs\architecture_render.html"
png_path = r"D:\OpenClaw\zhihu-ask\docs\architecture.png"
abs_path = os.path.abspath(html_path).replace("\\", "/")
url = f"file:///{abs_path}"

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 2400, "height": 2100}, device_scale_factor=2)
    page.goto(url)
    page.wait_for_timeout(2000)
    svg = page.query_selector("svg")
    svg.screenshot(path=png_path)
    browser.close()

print(f"OK -> {png_path} ({os.path.getsize(png_path)} bytes)")
