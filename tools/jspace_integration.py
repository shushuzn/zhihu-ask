"""
J-Space 原生集成模块（zhihu-ask 项目专用）

提供J-Space认知管理框架与zhihu-ask研究流程的轻量级集成。
设计理念：最小封装，最大化原生J-Space体验。

用法：
  from tools.jspace_integration import jspace_call, jspace_seam, jspace_ship
  
  # 原生调用
  jspace_call("initialize", "--goal=研究问题：xxx")
  jspace_seam("阶段1完成")
  jspace_ship("report.md")
  
  # 或使用管理器（轻量封装）
  js = JSpaceManager(slug="my-research-topic")
  js.initialize("研究问题：xxx")
  js.seam("阶段1完成")
  js.ship("report.md")
"""

import os
import subprocess
import sys
import json
import logging
from typing import Optional, Dict, Any
from pathlib import Path

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


class JSpaceManager:
    """J-Space 轻量级管理器
    
    提供路径管理和便捷方法，但保持原生J-Space调用方式。
    不隐藏底层实现，不添加不必要的抽象层。
    
    属性：
        slug (str): 研究主题的slug标识
        research_dir (Path): 研究目录路径
        jspace_dir (Path): J-Space工作空间目录
        progress_file (Path): .progress.json文件路径
    """
    
    def __init__(self, slug: str):
        """初始化JSpaceManager
        
        Args:
            slug: 研究主题的slug标识
        """
        self.slug = slug
        self.research_dir = ROOT / "research" / slug
        self.jspace_dir = self.research_dir / ".jspace"
        self.progress_file = self.research_dir / ".progress.json"
        
        # 确保研究目录存在
        os.makedirs(self.research_dir, exist_ok=True)
        
        logger.debug(f"JSpaceManager初始化: slug={slug}")
    
    def initialize(self, goal: str, next_action: str = "执行阶段 1 六通道检索") -> subprocess.CompletedProcess:
        """初始化研究ledger
        
        Args:
            goal: 研究目标描述
            next_action: 下一步行动描述
            
        Returns:
            subprocess.CompletedProcess对象
        """
        # 确保.jspace目录存在
        os.makedirs(self.jspace_dir, exist_ok=True)
        
        # 使用原生调用初始化ledger
        return jspace_call("note", f"--goal={goal}", f"--next={next_action}")
    
    def seam(self, context: str = "") -> subprocess.CompletedProcess:
        """接缝审计
        
        Args:
            context: 上下文描述（可选）
            
        Returns:
            subprocess.CompletedProcess对象
        """
        # 检查ledger是否存在
        if not self.check_ledger_exists():
            logger.info("J-Space Ledger不存在，先初始化...")
            self.initialize(f"研究任务：{self.slug}")
        
        return jspace_seam(context)
    
    def note(self, **kwargs) -> subprocess.CompletedProcess:
        """记录检查点
        
        Args:
            **kwargs: 键值对参数
            
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
    
    def ship(self, file_path: str) -> subprocess.CompletedProcess:
        """交付前检查
        
        Args:
            file_path: 要检查的文件路径
            
        Returns:
            subprocess.CompletedProcess对象
        """
        return jspace_ship(file_path)
    
    def resume(self) -> subprocess.CompletedProcess:
        """恢复上下文
        
        Returns:
            subprocess.CompletedProcess对象
        """
        return jspace_resume()
    
    def check_ledger_exists(self) -> bool:
        """检查ledger是否存在
        
        Returns:
            bool: ledger文件是否存在
        """
        ledger_path = self.jspace_dir / "WORKSPACE.md"
        return ledger_path.exists()
    
    def sync_progress(self) -> bool:
        """将.progress.json状态与J-space ledger同步
        
        Returns:
            bool: 同步是否成功
        """
        if not self.progress_file.exists():
            logger.debug(f".progress.json不存在: {self.progress_file}")
            return False
        
        try:
            with open(self.progress_file, encoding='utf-8') as f:
                progress = json.load(f)
            
            # 从.progress.json提取关键信息
            stage = progress.get('stage', '')
            question = progress.get('data', {}).get('question', '')[:100]
            channels = progress.get('data', {}).get('channels_done', {})
            
            # 更新ledger的Goal字段
            if question:
                goal = f"研究问题：{question}"
                jspace_call("note", f"--goal={goal}", check=False)
            
            # 更新Verified字段（已完成通道）
            verified_channels = [ch for ch, info in channels.items() 
                               if info.get('status') == 'done']
            if verified_channels:
                verified_text = f"已完成通道：{', '.join(verified_channels)}"
                jspace_call("note", f"--verified={verified_text}", check=False)
            
            # 更新Next字段（当前阶段）
            stage_map = {
                'phase1_done': '执行阶段2多视角收集',
                'phase2_done': '执行阶段3交叉验证',
                'phase3_done': '执行阶段4报告生成',
                'phase4_done': '报告验收'
            }
            next_action = stage_map.get(stage, '继续当前阶段')
            jspace_call("note", f"--next={next_action}", check=False)
            
            logger.info("已同步.progress.json状态到J-space ledger")
            return True
            
        except Exception as e:
            logger.error(f"同步.progress.json失败: {e}")
            return False
    
    def status(self) -> Dict[str, Any]:
        """显示当前研究状态
        
        Returns:
            Dict[str, Any]: 包含状态信息的字典
        """
        status_info = {
            'slug': self.slug,
            'ledger_exists': self.check_ledger_exists(),
            'progress_exists': self.progress_file.exists(),
            'stage': 'unknown',
            'done_channels': []
        }
        
        if not status_info['ledger_exists']:
            logger.info("J-Space Ledger不存在")
            return status_info
        
        try:
            # 显示J-Space状态
            print("\n=== J-Space 研究状态 ===")
            jspace_call("seam", check=False)
            
            # 显示.progress.json状态（如果存在）
            if status_info['progress_exists']:
                with open(self.progress_file, encoding='utf-8') as f:
                    progress = json.load(f)
                
                status_info['stage'] = progress.get('stage', '未知')
                channels = progress.get('data', {}).get('channels_done', {})
                status_info['done_channels'] = [ch for ch, info in channels.items() 
                                               if info.get('status') == 'done']
                
                print(f"阶段：{status_info['stage']}")
                print(f"已完成通道：{', '.join(status_info['done_channels']) if status_info['done_channels'] else '无'}")
            
            print("========================\n")
            
        except Exception as e:
            logger.error(f"获取状态信息失败: {e}")
        
        return status_info
    
    def get_ledger_content(self) -> Optional[str]:
        """获取ledger文件内容
        
        Returns:
            Optional[str]: ledger内容，如果不存在则返回None
        """
        ledger_path = self.jspace_dir / "WORKSPACE.md"
        if not ledger_path.exists():
            return None
        
        try:
            with open(ledger_path, encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"读取ledger文件失败: {e}")
            return None


def validate_jspace_script() -> bool:
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


if __name__ == "__main__":
    # 测试用法
    if len(sys.argv) < 3:
        print("用法: python jspace_integration.py <slug> <command> [args]")
        print("命令: initialize <goal> | seam [checkpoint] | ship <file> | resume | status | sync | validate")
        sys.exit(1)
    
    slug = sys.argv[1]
    command = sys.argv[2]
    
    # 验证J-Space脚本
    if command == "validate":
        if validate_jspace_script():
            print(f"J-Space脚本有效: {JSPACE_SCRIPT}")
            sys.exit(0)
        else:
            print(f"J-Space脚本无效: {JSPACE_SCRIPT}")
            sys.exit(1)
    
    js = JSpaceManager(slug)
    
    if command == "initialize":
        goal = sys.argv[3] if len(sys.argv) > 3 else "研究问题"
        js.initialize(goal)
    elif command == "seam":
        checkpoint = sys.argv[3] if len(sys.argv) > 3 else ""
        js.seam(checkpoint)
    elif command == "ship":
        if len(sys.argv) < 4:
            print("ship 命令需要文件路径参数")
            sys.exit(1)
        js.ship(sys.argv[3])
    elif command == "resume":
        js.resume()
    elif command == "status":
        js.status()
    elif command == "sync":
        js.sync_progress()
    elif command == "validate":
        # 已经在前面处理了
        pass
    else:
        print(f"未知命令: {command}")
        sys.exit(1)