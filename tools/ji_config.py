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
import signal
import time
from typing import Optional, Callable, Any, Dict
from pathlib import Path
from contextlib import contextmanager

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 项目根目录由门面 jspace_integration 持有，子模块运行时引用 jspace_integration.ROOT
# 以兼容测试对 jspace_integration.ROOT 的 monkeypatch（文件系统隔离）
import jspace_integration

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



# 默认配置
DEFAULT_CONFIG = {
    "default_timeout": 30,
    "max_retries": 3,
    "retry_delay": 1.0,
    "log_level": "INFO",
    "auto_seam": True,
    "auto_ship": True,
}



def jspace_load_config() -> Dict[str, Any]:
    """加载J-Space配置
    
    优先从配置文件加载，否则使用默认配置。
    
    Returns:
        Dict[str, Any]: 配置字典
    """
    config_file = jspace_integration.ROOT / "jspace_config.json"
    if config_file.exists():
        try:
            import json
            with open(config_file, encoding='utf-8') as f:
                config = json.load(f)
                # 合并默认配置
                merged = DEFAULT_CONFIG.copy()
                merged.update(config)
                return merged
        except Exception as e:
            logger.warning(f"加载配置文件失败，使用默认配置: {e}")
    
    return DEFAULT_CONFIG.copy()

def jspace_save_config(config: Dict[str, Any]) -> bool:
    """保存J-Space配置
    
    Args:
        config: 配置字典
        
    Returns:
        bool: 是否保存成功
    """
    config_file = jspace_integration.ROOT / "jspace_config.json"
    try:
        import json
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"保存配置文件失败: {e}")
        return False

def jspace_log_operation(operation: str, slug: str = "", details: str = "") -> None:
    """记录J-Space操作日志
    
    将操作记录到日志文件，便于追踪和调试。
    
    Args:
        operation: 操作类型（如 "seam", "ship", "initialize" 等）
        slug: 研究主题的slug标识（可选）
        details: 操作详情（可选）
    """
    log_file = jspace_integration.ROOT / "jspace_operations.log"
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {operation}"
    if slug:
        log_entry += f" (slug: {slug})"
    if details:
        log_entry += f" - {details}"
    log_entry += "\n"
    
    try:
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(log_entry)
    except Exception as e:
        logger.warning(f"记录操作日志失败: {e}")

def jspace_get_operation_log(limit: int = 10) -> list:
    """获取最近的操作日志
    
    Args:
        limit: 返回的最大条目数（默认10）
        
    Returns:
        list: 日志条目列表
    """
    log_file = jspace_integration.ROOT / "jspace_operations.log"
    if not log_file.exists():
        return []
    
    try:
        with open(log_file, encoding='utf-8') as f:
            lines = f.readlines()
        # 返回最后N条
        return lines[-limit:] if len(lines) > limit else lines
    except Exception as e:
        logger.error(f"读取操作日志失败: {e}")
        return []
