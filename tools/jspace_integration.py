"""
J-Space 原生集成模块（zhihu-ask 项目专用）

提供J-Space认知管理框架与zhihu-ask研究流程的极简集成。
设计理念：最小封装，最大化原生J-Space体验，只提供必要的路径管理和便捷函数。

用法：
  from tools.jspace_integration import jspace_call, jspace_seam, jspace_ship
  
  # 原生调用
  jspace_call("initialize", "--goal=研究问题：xxx")
  jspace_seam("阶段1完成")
  jspace_ship("report.md")
  
  # 模块调用
  from tools.jspace_integration import jspace_module
  
  # 读取introspection模块
  content = jspace_module("introspection")
"""

import os
import subprocess
import sys
import logging

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass
import signal
import time
from typing import Optional, Callable, Any, Dict
from pathlib import Path
from contextlib import contextmanager

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 项目根目录
ROOT = Path(__file__).parent.parent.absolute()

# J-Space脚本路径（优先从环境变量读取，否则使用默认路径）
JSPACE_SCRIPT = os.environ.get(
    "JSPACE_SCRIPT_PATH",
    str(Path.home() / ".workbuddy" / "skills" / "J-Space-Cognition-Suite" / "scripts" / "jspace.py")
)

# J-Space模块目录
JSPACE_MODULES_DIR = Path.home() / ".workbuddy" / "skills" / "J-Space-Cognition-Suite" / "modules"

# 模块映射：模块名 -> 文件名
MODULE_FILES: Dict[str, str] = {
    "capacity": "capacity.md",
    "broadcast": "broadcast.md",
    "deep-reasoning": "deep-reasoning.md",
    "directed-focus": "directed-focus.md",
    "empirics": "empirics.md",
    "introspection": "introspection.md",
    "markers": "markers.md",
    "self-monitoring": "self-monitoring.md",
    "shorthand": "shorthand.md",
}

from ji_call import (
    jspace_context, jspace_call, JSpaceTimeoutError, jspace_call_with_timeout, jspace_call_with_retry, jspace_seam, jspace_ship, jspace_resume, jspace_note, jspace_module, jspace_list_modules, jspace_validate,
)
from ji_ledger import (
    jspace_get_research_dir, jspace_get_jspace_dir, jspace_check_ledger_exists, jspace_get_ledger_content, jspace_get_ledger_content_cached, jspace_batch_note, jspace_directed_focus, jspace_marker, jspace_self_monitor, jspace_run_in_context, jspace_track_phase_transition,
)
from ji_config import (
    jspace_load_config, jspace_save_config, jspace_log_operation, jspace_get_operation_log,
)

if __name__ == "__main__":
    # 测试用法
    if len(sys.argv) < 2:
        print("用法: python jspace_integration.py <command> [args]")
        print("命令: validate | seam <slug> [context] | ship <slug> <file> | resume <slug> | status <slug> | module <name> | modules | log [limit]")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "validate":
        if jspace_validate():
            print(f"J-Space脚本有效: {JSPACE_SCRIPT}")
            sys.exit(0)
        else:
            print(f"J-Space脚本无效: {JSPACE_SCRIPT}")
            sys.exit(1)
    
    if command == "modules":
        modules = jspace_list_modules()
        print("可用模块:")
        for mod in modules:
            print(f"  - {mod}")
        sys.exit(0)
    
    if command == "module":
        if len(sys.argv) < 3:
            print("module 命令需要模块名参数")
            sys.exit(1)
        module_name = sys.argv[2]
        content = jspace_module(module_name)
        if content:
            print(content)
        else:
            print(f"模块 {module_name} 不存在或无法读取")
            sys.exit(1)
        sys.exit(0)
    
    if command == "log":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        logs = jspace_get_operation_log(limit)
        print("最近J-Space操作日志:")
        for line in logs:
            print(line.strip())
        sys.exit(0)
    
    if len(sys.argv) < 3:
        print(f"命令 {command} 需要slug参数")
        sys.exit(1)
    
    slug = sys.argv[2]
    
    # 使用上下文管理器
    with jspace_context(slug):
        if command == "seam":
            context = sys.argv[3] if len(sys.argv) > 3 else ""
            jspace_seam(context)
        elif command == "ship":
            if len(sys.argv) < 4:
                print("ship 命令需要文件路径参数")
                sys.exit(1)
            jspace_ship(sys.argv[3])
        elif command == "resume":
            jspace_resume()
        elif command == "status":
            print("\n=== J-Space 研究状态 ===")
            jspace_call("seam", check=False)
            print("========================\n")
        else:
            print(f"未知命令: {command}")
            sys.exit(1)