# -*- coding: utf-8 -*-
"""本地敏感配置加载（.env）。

背景：沙箱下 `[Environment]::SetEnvironmentVariable` / `setx` 写用户级注册表
被拒（registry access not allowed），改用项目根 `.env` 文件承载 API key 等
敏感配置（.gitignore 已忽略，不入库）。web_search.py 等工具启动时调用
load_dotenv() 读取，优先级：真实环境变量 > .env 文件（不覆盖已存在的环境变量）。

用法：
  from env_loader import load_dotenv
  load_dotenv()            # 读取项目根 .env 到 os.environ（不覆盖已有）
  key = os.environ.get("TAVILY_API_KEY")

约定：
  - .env 格式：KEY=VALUE 每行一条，# 开头为注释；值不含引号包裹（或剥掉）
  - 只读加载，绝不写回；敏感值只在内存，不打印
"""
import os
import re

_ENV_LINE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$")


def _find_env_file():
    """项目根 .env 路径（tools/ 上一级）。"""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, ".env")


def load_dotenv(env_path=None):
    """把 .env 中未在真实环境变量里出现的键写入 os.environ。

    优先级：已存在的环境变量优先（.env 不覆盖）；重复键以首个出现为准。
    返回加载的键数；文件不存在/空返回 0；不抛异常。
    """
    path = env_path or _find_env_file()
    if not os.path.isfile(path):
        return 0
    loaded = 0
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                m = _ENV_LINE.match(line)
                if not m:
                    continue
                key, val = m.group(1), m.group(2)
                val = val.strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = val
                    loaded += 1
    except OSError:
        return 0
    return loaded


if __name__ == "__main__":
    n = load_dotenv()
    print(f"loaded {n} keys")
    print("TAVILY_API_KEY present:", bool(os.environ.get("TAVILY_API_KEY")))
