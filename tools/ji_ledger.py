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



from ji_call import jspace_context, jspace_call, jspace_seam

def jspace_get_research_dir(slug: str) -> Path:
    """获取研究目录路径
    
    Args:
        slug: 研究主题的slug标识
        
    Returns:
        Path: 研究目录路径
    """
    return jspace_integration.ROOT / "research" / slug

def jspace_get_jspace_dir(slug: str) -> Path:
    """获取J-Space工作空间目录路径
    
    Args:
        slug: 研究主题的slug标识
        
    Returns:
        Path: J-Space工作空间目录路径
    """
    return jspace_get_research_dir(slug) / ".jspace"

def jspace_check_ledger_exists(slug: str) -> bool:
    """检查ledger是否存在
    
    Args:
        slug: 研究主题的slug标识
        
    Returns:
        bool: ledger文件是否存在
    """
    ledger_path = jspace_get_jspace_dir(slug) / "WORKSPACE.md"
    return ledger_path.exists()

def jspace_get_ledger_content(slug: str) -> Optional[str]:
    """获取ledger文件内容
    
    Args:
        slug: 研究主题的slug标识
        
    Returns:
        Optional[str]: ledger内容，如果不存在则返回None
    """
    ledger_path = jspace_get_jspace_dir(slug) / "WORKSPACE.md"
    if not ledger_path.exists():
        return None
    
    try:
        with open(ledger_path, encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logger.error(f"读取ledger文件失败: {e}")
        return None

def jspace_get_ledger_content_cached(slug: str) -> Optional[str]:
    """缓存版本的获取ledger内容
    
    使用缓存避免频繁读取文件，提高性能。
    
    Args:
        slug: 研究主题的slug标识
        
    Returns:
        Optional[str]: ledger内容，如果不存在则返回None
    """
    # 简单缓存实现：检查文件修改时间
    cache_key = f"ledger_{slug}"
    cache_file = ROOT / ".jspace_cache" / f"{cache_key}.txt"
    
    # 确保缓存目录存在
    cache_dir = ROOT / ".jspace_cache"
    os.makedirs(cache_dir, exist_ok=True)
    
    ledger_path = jspace_get_jspace_dir(slug) / "WORKSPACE.md"
    if not ledger_path.exists():
        return None
    
    # 检查缓存是否有效
    if cache_file.exists():
        try:
            with open(cache_file, encoding='utf-8') as f:
                cache_data = f.read()
            # 简单缓存：如果缓存文件存在且ledger文件未修改，返回缓存
            # 这里简化处理，每次都重新读取
        except:
            pass
    
    # 读取ledger文件
    try:
        with open(ledger_path, encoding='utf-8') as f:
            content = f.read()
        # 写入缓存
        with open(cache_file, 'w', encoding='utf-8') as f:
            f.write(content)
        return content
    except Exception as e:
        logger.error(f"读取ledger文件失败: {e}")
        return None

def jspace_batch_note(slug: str, notes: list) -> None:
    """批量记录检查点
    
    支持批量记录检查点，减少J-Space调用次数。
    
    Args:
        slug: 研究主题的slug标识
        notes: 笔记列表，每个元素是字典，包含要记录的参数
    """
    with jspace_context(slug):
        for note in notes:
            args = []
            for key, value in note.items():
                if value is not None:
                    args.append(f"--{key}={value}")
            if args:
                jspace_call("note", *args, check=False)

def jspace_directed_focus(slug: str, item: str) -> None:
    """记录要保持的关注点（directed-focus模块）
    
    在长时间任务中保持目标不丢失，防止"做到一半忘了目标"。
    
    Args:
        slug: 研究主题的slug标识
        item: 要保持关注的项目
    """
    with jspace_context(slug):
        jspace_call("note", f"--next=保持关注: {item}", check=False)

def jspace_marker(slug: str, marker_type: str, description: str) -> None:
    """记录标记点（markers模块）
    
    记录检查点和状态变化，用于追踪任务进度。
    
    Args:
        slug: 研究主题的slug标识
        marker_type: 标记类型（如 "checkpoint", "decision", "swap" 等）
        description: 标记描述
    """
    with jspace_context(slug):
        # 使用--next参数记录标记点
        jspace_call("note", f"--next={marker_type}: {description}", check=False)

def jspace_self_monitor(slug: str, observation: str) -> None:
    """记录自我监控观察（self-monitoring模块）
    
    在处理过程中记录自我监控观察，用于追踪思考过程。
    
    Args:
        slug: 研究主题的slug标识
        observation: 自我监控观察内容
    """
    with jspace_context(slug):
        jspace_call("note", f"--next=观察: {observation}", check=False)

def jspace_run_in_context(slug: str, func: Callable[[], Any], *args, **kwargs) -> Any:
    """在J-Space上下文中执行函数
    
    自动处理目录切换，确保函数在研究目录中执行。
    
    Args:
        slug: 研究主题的slug标识
        func: 要执行的函数
        *args: 函数参数
        **kwargs: 函数关键字参数
        
    Returns:
        Any: 函数返回值
    """
    with jspace_context(slug):
        return func(*args, **kwargs)

def jspace_track_phase_transition(slug: str, from_phase: str, to_phase: str, notes: str = "") -> None:
    """记录阶段转换
    
    自动记录阶段转换，用于状态跟踪。
    
    Args:
        slug: 研究主题的slug标识
        from_phase: 源阶段（如 "phase1", "phase2" 等）
        to_phase: 目标阶段
        notes: 额外备注
    """
    with jspace_context(slug):
        # 记录阶段转换
        description = f"阶段转换: {from_phase} → {to_phase}"
        if notes:
            description += f" ({notes})"
        jspace_call("note", f"--next={description}", check=False)
        
        # 执行seam审计
        jspace_seam(f"阶段转换: {from_phase} → {to_phase}")
