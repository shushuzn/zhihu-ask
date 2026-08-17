"""
J-Space 认知工作空间集成模块（zhihu-ask 项目专用）

将 J-Space 认知管理框架与 zhihu-ask 研究流程集成，提供：
1. 阶段转换时的接缝审计（seam）
2. 研究状态 ledger 管理
3. 交付前检查（ship）
4. 认知过程规范化

用法：
  from tools.jspace_integration import JSpaceManager
  
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
from typing import Optional, Dict, Any, List
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


class JSpaceError(Exception):
    """J-Space操作异常基类"""
    pass


class JSpaceInitializationError(JSpaceError):
    """J-Space初始化异常"""
    pass


class JSpaceCommandError(JSpaceError):
    """J-Space命令执行异常"""
    pass


class JSpaceManager:
    """J-Space 认知工作空间管理器
    
    提供J-Space认知管理框架与zhihu-ask研究流程的集成。
    
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
            
        Raises:
            JSpaceInitializationError: 如果J-Space脚本不存在
        """
        self.slug = slug
        self.research_dir = ROOT / "research" / slug
        self.jspace_dir = self.research_dir / ".jspace"
        self.progress_file = self.research_dir / ".progress.json"
        
        # 检查J-Space脚本是否存在
        if not os.path.exists(JSPACE_SCRIPT):
            raise JSpaceInitializationError(f"J-Space脚本不存在: {JSPACE_SCRIPT}")
        
        logger.debug(f"JSpaceManager初始化完成: slug={slug}, research_dir={self.research_dir}")
    
    def _run_jspace(self, *args, check: bool = True) -> subprocess.CompletedProcess:
        """运行 j-space 控制器命令
        
        Args:
            *args: 传递给jspace.py的命令行参数
            check: 是否检查返回码（默认True）
            
        Returns:
            subprocess.CompletedProcess对象
            
        Raises:
            JSpaceCommandError: 如果命令执行失败且check=True
        """
        cmd = [sys.executable, JSPACE_SCRIPT] + list(args)
        logger.info(f"执行J-Space命令: {' '.join(args)}")
        
        try:
            r = subprocess.run(
                cmd, 
                cwd=str(self.research_dir), 
                capture_output=True, 
                text=True,
                encoding='utf-8',
                errors='replace'
            )
            
            if r.stdout:
                logger.debug(f"J-Space stdout: {r.stdout[:200]}...")
            if r.stderr:
                logger.warning(f"J-Space stderr: {r.stderr[:200]}...")
            
            if check and r.returncode != 0:
                error_msg = f"J-Space命令返回非零退出码: {r.returncode}"
                logger.error(error_msg)
                raise JSpaceCommandError(error_msg)
            
            return r
            
        except subprocess.TimeoutExpired:
            error_msg = "J-Space命令执行超时"
            logger.error(error_msg)
            if check:
                raise JSpaceCommandError(error_msg)
            return subprocess.CompletedProcess(cmd, returncode=-1, stdout="", stderr=error_msg)
        except Exception as e:
            error_msg = f"J-Space命令执行异常: {e}"
            logger.error(error_msg)
            if check:
                raise JSpaceCommandError(error_msg)
            return subprocess.CompletedProcess(cmd, returncode=-1, stdout="", stderr=error_msg)
    
    def initialize(self, goal: str, next_action: str = "执行阶段 1 六通道检索") -> None:
        """初始化研究 ledger
        
        Args:
            goal: 研究目标描述
            next_action: 下一步行动描述
            
        Raises:
            JSpaceInitializationError: 如果初始化失败
        """
        try:
            # 确保目录存在
            os.makedirs(self.jspace_dir, exist_ok=True)
            
            # 初始化 ledger
            self._run_jspace("note", f"--goal={goal}", f"--next={next_action}")
            logger.info(f"J-Space研究ledger已初始化: {self.slug}")
            
        except Exception as e:
            error_msg = f"J-Space初始化失败: {e}"
            logger.error(error_msg)
            raise JSpaceInitializationError(error_msg)
    
    def seam(self, checkpoint: str = "") -> None:
        """接缝审计：记录阶段完成状态
        
        Args:
            checkpoint: 检查点描述（可选）
            
        Note:
            如果ledger不存在，会自动初始化
        """
        # 先检查 ledger 是否存在，不存在则初始化
        if not self.check_ledger_exists():
            logger.info("J-Space Ledger不存在，先初始化...")
            self.initialize(f"研究任务：{self.slug}")
        
        self._run_jspace("seam")
        if checkpoint:
            self._run_jspace("note", f"--next={checkpoint}")
    
    def note(self, **kwargs) -> None:
        """记录检查点
        
        Args:
            **kwargs: 键值对参数，如 goal="...", next="...", verified="..." 等
        """
        args = []
        for key, value in kwargs.items():
            if value is not None:
                args.append(f"--{key}={value}")
        
        if args:
            self._run_jspace("note", *args)
        else:
            logger.warning("note命令没有提供任何参数")
    
    def ship(self, file_path: str) -> None:
        """交付前检查
        
        Args:
            file_path: 要检查的文件路径
            
        Raises:
            JSpaceCommandError: 如果检查失败
        """
        if not os.path.exists(file_path):
            logger.warning(f"要检查的文件不存在: {file_path}")
        
        self._run_jspace("ship", file_path)
    
    def resume(self) -> None:
        """恢复上下文（长间隔后）
        
        用于会话中断后恢复之前的上下文状态。
        """
        self._run_jspace("resume")
    
    def check_ledger_exists(self) -> bool:
        """检查 ledger 是否存在
        
        Returns:
            bool: ledger文件是否存在
        """
        ledger_path = self.jspace_dir / "WORKSPACE.md"
        return ledger_path.exists()
    
    def auto_seam(self, context: str = "") -> None:
        """自动接缝审计：在每个工具调用前后执行
        
        Args:
            context: 上下文描述（可选）
            
        Note:
            如果ledger不存在，会跳过执行
        """
        if not self.check_ledger_exists():
            logger.debug("J-Space Ledger不存在，跳过auto_seam")
            return
        
        try:
            # 执行seam审计
            self._run_jspace("seam", check=False)
            
            # 如果有上下文，记录到ledger
            if context:
                self._run_jspace("note", f"--next={context}", check=False)
                
        except Exception as e:
            logger.warning(f"auto_seam执行异常: {e}")
    
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
                self._run_jspace("note", f"--goal={goal}", check=False)
            
            # 更新Verified字段（已完成通道）
            verified_channels = [ch for ch, info in channels.items() 
                               if info.get('status') == 'done']
            if verified_channels:
                verified_text = f"已完成通道：{', '.join(verified_channels)}"
                self._run_jspace("note", f"--verified={verified_text}", check=False)
            
            # 更新Next字段（当前阶段）
            stage_map = {
                'phase1_done': '执行阶段2多视角收集',
                'phase2_done': '执行阶段3交叉验证',
                'phase3_done': '执行阶段4报告生成',
                'phase4_done': '报告验收'
            }
            next_action = stage_map.get(stage, '继续当前阶段')
            self._run_jspace("note", f"--next={next_action}", check=False)
            
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
            self._run_jspace("seam", check=False)
            
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
    
    def update_ledger_field(self, field: str, value: str) -> bool:
        """更新ledger的特定字段
        
        Args:
            field: 字段名（goal/core/verified/open/next）
            value: 新值
            
        Returns:
            bool: 更新是否成功
        """
        try:
            self._run_jspace("note", f"--{field}={value}", check=False)
            logger.info(f"已更新ledger字段 {field}")
            return True
        except Exception as e:
            logger.error(f"更新ledger字段失败: {e}")
            return False


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


def get_jspace_manager(slug: str) -> Optional[JSpaceManager]:
    """获取JSpaceManager实例（工厂方法）
    
    Args:
        slug: 研究主题的slug标识
        
    Returns:
        Optional[JSpaceManager]: JSpaceManager实例，如果创建失败则返回None
    """
    try:
        return JSpaceManager(slug)
    except JSpaceInitializationError as e:
        logger.error(f"创建JSpaceManager失败: {e}")
        return None
    except Exception as e:
        logger.error(f"创建JSpaceManager时发生未知错误: {e}")
        return None


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
    
    try:
        js = JSpaceManager(slug)
    except JSpaceInitializationError as e:
        print(f"初始化失败: {e}")
        sys.exit(1)
    
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