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
        self.progress_file = os.path.join(self.research_dir, ".progress.json")
        
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
    
    def auto_seam(self, context: str = ""):
        """自动接缝审计：在每个工具调用前后执行"""
        if not self.check_ledger_exists():
            return  # 如果ledger不存在，跳过
        
        # 执行seam审计
        self._run_jspace("seam", check=False)
        
        # 如果有上下文，记录到ledger
        if context:
            self._run_jspace("note", f"--next={context}", check=False)
    
    def sync_progress(self):
        """将.progress.json状态与J-space ledger同步"""
        if not os.path.exists(self.progress_file):
            return
        
        try:
            import json
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
            
            print(f"[J-Space] 已同步.progress.json状态到ledger")
        except Exception as e:
            print(f"[J-Space] 同步失败：{e}")
    
    def status(self):
        """显示当前研究状态"""
        if not self.check_ledger_exists():
            print("[J-Space] Ledger不存在")
            return
        
        print("\n=== J-Space 研究状态 ===")
        self._run_jspace("seam", check=False)
        
        # 显示.progress.json状态（如果存在）
        if os.path.exists(self.progress_file):
            try:
                import json
                with open(self.progress_file, encoding='utf-8') as f:
                    progress = json.load(f)
                
                stage = progress.get('stage', '未知')
                channels = progress.get('data', {}).get('channels_done', {})
                done_channels = [ch for ch, info in channels.items() 
                               if info.get('status') == 'done']
                
                print(f"阶段：{stage}")
                print(f"已完成通道：{', '.join(done_channels) if done_channels else '无'}")
            except:
                pass
        
        print("========================\n")


def integrate_with_pipeline():
    """将 J-Space 集成到 run_pipeline.py 的示例函数"""
    # 这个函数展示了如何在 run_pipeline.py 中调用 J-Space
    # 实际集成需要修改 run_pipeline.py 的具体阶段转换点
    pass


if __name__ == "__main__":
    # 测试用法
    if len(sys.argv) < 3:
        print("用法: python jspace_integration.py <slug> <command> [args]")
        print("命令: initialize <goal> | seam [checkpoint] | ship <file> | resume | status | sync")
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
    elif command == "status":
        js.status()
    elif command == "sync":
        js.sync_progress()
    else:
        print(f"未知命令: {command}")
        sys.exit(1)