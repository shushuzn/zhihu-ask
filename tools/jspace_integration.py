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


@contextmanager
def jspace_context(slug: str):
    """J-Space上下文管理器
    
    自动处理研究目录切换和异常恢复。
    
    Args:
        slug: 研究主题的slug标识
        
    Yields:
        Path: 研究目录路径
    """
    research_dir = jspace_get_research_dir(slug)
    os.makedirs(research_dir, exist_ok=True)
    
    original_dir = os.getcwd()
    os.chdir(research_dir)
    
    try:
        yield research_dir
    finally:
        os.chdir(original_dir)


def jspace_call(*args: str, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    """原生J-Space调用
    
    直接调用jspace.py脚本，最小封装，保持原生体验。
    
    Args:
        *args: 传递给jspace.py的命令行参数
        check: 是否检查返回码（默认True）
        capture: 是否捕获输出（默认False，直接打印）
        
    Returns:
        subprocess.CompletedProcess对象
        
    Raises:
        subprocess.CalledProcessError: 如果命令执行失败且check=True
    """
    if not os.path.exists(JSPACE_SCRIPT):
        raise FileNotFoundError(f"J-Space脚本不存在: {JSPACE_SCRIPT}")
    
    cmd = [sys.executable, JSPACE_SCRIPT] + list(args)
    logger.debug(f"J-Space调用: {' '.join(args)}")
    
    if capture:
        return subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            encoding='utf-8',
            errors='replace'
        )
    else:
        return subprocess.run(cmd)


def jspace_seam(context: str = "", check: bool = True) -> subprocess.CompletedProcess:
    """原生J-Space接缝审计
    
    执行seam命令，记录当前状态。
    
    Args:
        context: 上下文描述（可选）
        check: 是否检查返回码
        
    Returns:
        subprocess.CompletedProcess对象
    """
    result = jspace_call("seam", check=check)
    
    if context and result.returncode == 0:
        # 如果有上下文，记录到ledger
        jspace_call("note", f"--next={context}", check=False)
    
    return result


def jspace_ship(file_path: str, check: bool = True) -> subprocess.CompletedProcess:
    """原生J-Space交付前检查
    
    执行ship命令，检查文件是否符合认知管理标准。
    
    Args:
        file_path: 要检查的文件路径
        check: 是否检查返回码
        
    Returns:
        subprocess.CompletedProcess对象
    """
    return jspace_call("ship", file_path, check=check)


def jspace_resume(check: bool = True) -> subprocess.CompletedProcess:
    """原生J-Space恢复上下文
    
    执行resume命令，恢复之前的上下文状态。
    
    Args:
        check: 是否检查返回码
        
    Returns:
        subprocess.CompletedProcess对象
    """
    return jspace_call("resume", check=check)


def jspace_note(**kwargs) -> subprocess.CompletedProcess:
    """原生J-Space记录检查点
    
    执行note命令，记录检查点到ledger。
    
    Args:
        **kwargs: 键值对参数，如 goal="...", next="...", verified="..." 等
        
    Returns:
        subprocess.CompletedProcess对象
    """
    args = []
    for key, value in kwargs.items():
        if value is not None:
            args.append(f"--{key}={value}")
    
    if args:
        return jspace_call("note", *args)
    else:
        logger.warning("note命令没有提供任何参数")
        return subprocess.CompletedProcess([], returncode=0)


def jspace_module(module_name: str, read_only: bool = True) -> Optional[str]:
    """读取J-Space模块内容
    
    Args:
        module_name: 模块名（如 introspection, capacity 等）
        read_only: 是否只读取（默认True）
        
    Returns:
        Optional[str]: 模块内容，如果不存在则返回None
    """
    if module_name not in MODULE_FILES:
        logger.error(f"未知模块: {module_name}")
        return None
    
    module_path = JSPACE_MODULES_DIR / MODULE_FILES[module_name]
    if not module_path.exists():
        logger.error(f"模块文件不存在: {module_path}")
        return None
    
    try:
        with open(module_path, encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logger.error(f"读取模块文件失败: {e}")
        return None


def jspace_list_modules() -> list:
    """列出所有可用的J-Space模块
    
    Returns:
        list: 可用模块名列表
    """
    return list(MODULE_FILES.keys())


def jspace_validate() -> bool:
    """验证J-Space脚本是否存在且可执行
    
    Returns:
        bool: 脚本是否有效
    """
    if not os.path.exists(JSPACE_SCRIPT):
        logger.error(f"J-Space脚本不存在: {JSPACE_SCRIPT}")
        return False
    
    # 检查是否可读
    if not os.access(JSPACE_SCRIPT, os.R_OK):
        logger.error(f"J-Space脚本不可读: {JSPACE_SCRIPT}")
        return False
    
    return True


def jspace_get_research_dir(slug: str) -> Path:
    """获取研究目录路径
    
    Args:
        slug: 研究主题的slug标识
        
    Returns:
        Path: 研究目录路径
    """
    return ROOT / "research" / slug


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


if __name__ == "__main__":
    # 测试用法
    if len(sys.argv) < 2:
        print("用法: python jspace_integration.py <command> [args]")
        print("命令: validate | seam <slug> [context] | ship <slug> <file> | resume <slug> | status <slug> | module <name> | modules")
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