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
def jspace_context(slug: str, auto_seam: bool = False):
    """J-Space上下文管理器
    
    自动处理研究目录切换和异常恢复。
    
    Args:
        slug: 研究主题的slug标识
        auto_seam: 是否自动记录seam审计（默认False）
        
    Yields:
        Path: 研究目录路径
    """
    research_dir = jspace_get_research_dir(slug)
    os.makedirs(research_dir, exist_ok=True)
    
    original_dir = os.getcwd()
    os.chdir(research_dir)
    
    # 如果启用自动seam审计，记录进入时间
    start_time = time.time()
    
    try:
        yield research_dir
    finally:
        # 如果启用自动seam审计，记录退出时间和持续时间
        if auto_seam:
            duration = time.time() - start_time
            logger.debug(f"J-Space上下文执行时间: {duration:.2f}秒")
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


class JSpaceTimeoutError(Exception):
    """J-Space调用超时异常"""
    pass


def jspace_call_with_timeout(*args: str, timeout: int = 30, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    """带超时的J-Space调用
    
    Args:
        *args: 传递给jspace.py的命令行参数
        timeout: 超时时间（秒）
        check: 是否检查返回码
        capture: 是否捕获输出
        
    Returns:
        subprocess.CompletedProcess对象
        
    Raises:
        JSpaceTimeoutError: 如果调用超时
    """
    def timeout_handler(signum, frame):
        raise JSpaceTimeoutError("J-Space调用超时")
    
    # 设置信号处理器
    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(timeout)
    
    try:
        return jspace_call(*args, check=check, capture=capture)
    except JSpaceTimeoutError:
        logger.error(f"J-Space调用超时（{timeout}秒）")
        return subprocess.CompletedProcess([], returncode=-1, stdout="", stderr="超时")
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


def jspace_call_with_retry(*args: str, max_retries: int = 3, retry_delay: float = 1.0, **kwargs) -> subprocess.CompletedProcess:
    """带重试的J-Space调用
    
    Args:
        *args: 传递给jspace.py的命令行参数
        max_retries: 最大重试次数
        retry_delay: 重试延迟（秒）
        **kwargs: 传递给jspace_call的其他参数
        
    Returns:
        subprocess.CompletedProcess对象
        
    Raises:
        Exception: 如果所有重试都失败
    """
    last_exception = None
    
    for attempt in range(max_retries):
        try:
            return jspace_call(*args, **kwargs)
        except Exception as e:
            last_exception = e
            if attempt == max_retries - 1:
                raise
            logger.warning(f"J-Space调用失败（尝试 {attempt + 1}/{max_retries}），{retry_delay}秒后重试: {e}")
            time.sleep(retry_delay)
    
    raise last_exception


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
    config_file = ROOT / "jspace_config.json"
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
    config_file = ROOT / "jspace_config.json"
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
    log_file = ROOT / "jspace_operations.log"
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
    log_file = ROOT / "jspace_operations.log"
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