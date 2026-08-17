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
from typing import Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSPACE_SCRIPT = r"C:\Users\35234\.workbuddy\skills\J-Space-Cognition-Suite\scripts\jspace.py"


class JSpaceManager:
    """J-Space 认知工作空间管理器"""
    
    def __init__(self, slug: str):
        self.slug = slug
        self.research_dir = os.path.join(ROOT, "research", slug)
        self.jspace_dir = os.path.join(self.research_dir, ".jspace")
        
    def _run_jspace(self, *args, check: bool = True) -> subprocess.CompletedProcess:
        """运行 j-space 控制器命令"""
        cmd = [sys.executable, JSPACE_SCRIPT] + list(args)
        print(f"\n─── J-Space: {' '.join(args)} ───")
        r = subprocess.run(cmd, cwd=self.research_dir, capture_output=True, text=True)
        if r.stdout:
            print(r.stdout)
        if r.stderr:
            print(f"stderr: {r.stderr}", file=sys.stderr)
        if check and r.returncode != 0:
            print(f"[警告] J-Space 命令返回非零退出码: {r.returncode}")
        return r
    
    def initialize(self, goal: str, next_action: str = "执行阶段 1 六通道检索"):
        """初始化研究 ledger"""
        # 确保目录存在
        os.makedirs(self.jspace_dir, exist_ok=True)
        
        # 初始化 ledger
        self._run_jspace("note", f"--goal={goal}", f"--next={next_action}")
        print(f"[J-Space] 研究 ledger 已初始化: {self.slug}")
        
    def seam(self, checkpoint: str = ""):
        """接缝审计：记录阶段完成状态"""
        # 先检查 ledger 是否存在，不存在则初始化
        if not self.check_ledger_exists():
            print("[J-Space] Ledger 不存在，先初始化...")
            self.initialize(f"研究任务：{self.slug}")
        
        self._run_jspace("seam")
        if checkpoint:
            self._run_jspace("note", f"--next={checkpoint}")
            
    def note(self, **kwargs):
        """记录检查点"""
        args = []
        for key, value in kwargs.items():
            if value is not None:
                args.append(f"--{key}={value}")
        self._run_jspace("note", *args)
        
    def ship(self, file_path: str):
        """交付前检查"""
        self._run_jspace("ship", file_path)
        
    def resume(self):
        """恢复上下文（长间隔后）"""
        self._run_jspace("resume")
        
    def check_ledger_exists(self) -> bool:
        """检查 ledger 是否存在"""
        return os.path.exists(os.path.join(self.jspace_dir, "WORKSPACE.md"))


def integrate_with_pipeline():
    """将 J-Space 集成到 run_pipeline.py 的示例函数"""
    # 这个函数展示了如何在 run_pipeline.py 中调用 J-Space
    # 实际集成需要修改 run_pipeline.py 的具体阶段转换点
    pass


if __name__ == "__main__":
    # 测试用法
    if len(sys.argv) < 3:
        print("用法: python jspace_integration.py <slug> <command> [args]")
        print("命令: initialize <goal> | seam [checkpoint] | ship <file> | resume")
        sys.exit(1)
    
    slug = sys.argv[1]
    command = sys.argv[2]
    
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
    else:
        print(f"未知命令: {command}")
        sys.exit(1)