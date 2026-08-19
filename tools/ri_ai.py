"""报告配图：Agnes Image 2.1 Flash 文生图调用（从 report_images.py 拆分）。"""
import json
import os
import urllib.request


AGNES_ENDPOINT = "https://apihub.agnes-ai.com/v1/images/generations"
AGNES_MODEL = "agnes-image-2.1-flash"
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

