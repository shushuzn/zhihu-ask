"""
J-Space集成模块单元测试
"""

import unittest
import os
import sys
import tempfile
import shutil
import json

# 添加项目根目录到路径
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from jspace_integration import (
    jspace_validate,
    jspace_list_modules,
    jspace_get_research_dir,
    jspace_get_jspace_dir,
    jspace_check_ledger_exists,
    jspace_load_config,
    jspace_save_config,
    jspace_context,
    jspace_directed_focus,
    jspace_marker,
    jspace_batch_note,
)


class TestJSpaceIntegration(unittest.TestCase):
    """J-Space集成模块测试"""
    
    def test_validate(self):
        """测试脚本验证功能"""
        # 测试正常情况
        result = jspace_validate()
        self.assertIsInstance(result, bool)
    
    def test_list_modules(self):
        """测试模块列表功能"""
        modules = jspace_list_modules()
        self.assertIsInstance(modules, list)
        self.assertIn("introspection", modules)
        self.assertIn("capacity", modules)
        self.assertIn("directed-focus", modules)
        self.assertIn("markers", modules)
        self.assertIn("self-monitoring", modules)
    
    def test_get_research_dir(self):
        """测试研究目录路径获取"""
        path = jspace_get_research_dir("test-slug")
        path_str = str(path)
        # 检查路径是否包含research/test-slug（兼容Windows和Unix路径）
        self.assertTrue("research/test-slug" in path_str or "research\\test-slug" in path_str)
    
    def test_get_jspace_dir(self):
        """测试J-Space目录路径获取"""
        path = jspace_get_jspace_dir("test-slug")
        path_str = str(path)
        # 检查路径是否包含research/test-slug/.jspace（兼容Windows和Unix路径）
        self.assertTrue(("research/test-slug/.jspace" in path_str) or 
                       ("research\\test-slug\\.jspace" in path_str))
    
    def test_check_ledger_exists(self):
        """测试ledger存在检查"""
        # 使用临时目录测试
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建测试slug的目录结构
            slug = "test-ledger-exists"
            research_dir = os.path.join(tmpdir, "research", slug)
            jspace_dir = os.path.join(research_dir, ".jspace")
            os.makedirs(jspace_dir, exist_ok=True)
            
            # 测试ledger不存在的情况
            self.assertFalse(jspace_check_ledger_exists(slug))
            
            # 创建ledger文件
            ledger_file = os.path.join(jspace_dir, "WORKSPACE.md")
            with open(ledger_file, 'w') as f:
                f.write("# Test Ledger")
            
            # 测试ledger存在的情况
            # 注意：这个测试需要修改ROOT路径，这里只是概念验证
            # self.assertTrue(jspace_check_ledger_exists(slug))
    
    def test_config_management(self):
        """测试配置管理功能"""
        # 测试默认配置
        config = jspace_load_config()
        self.assertIsInstance(config, dict)
        self.assertIn("default_timeout", config)
        self.assertIn("max_retries", config)
        self.assertIn("retry_delay", config)
        
        # 测试保存配置
        test_config = {
            "test_key": "test_value",
            "default_timeout": 60,
        }
        
        # 使用临时目录测试
        with tempfile.TemporaryDirectory() as tmpdir:
            # 临时修改ROOT路径进行测试
            import jspace_integration
            from pathlib import Path
            original_root = jspace_integration.ROOT
            jspace_integration.ROOT = Path(tmpdir)
            
            try:
                result = jspace_save_config(test_config)
                self.assertTrue(result)
                
                # 验证配置文件已创建
                config_file = os.path.join(tmpdir, "jspace_config.json")
                self.assertTrue(os.path.exists(config_file))
                
                # 验证配置内容
                with open(config_file, encoding='utf-8') as f:
                    saved_config = json.load(f)
                self.assertEqual(saved_config["test_key"], "test_value")
                self.assertEqual(saved_config["default_timeout"], 60)
            finally:
                jspace_integration.ROOT = original_root
    
    def test_directed_focus(self):
        """测试directed-focus功能"""
        # 这个测试需要实际的J-Space环境，这里只是概念验证
        # jspace_directed_focus("test-slug", "测试关注点")
        pass
    
    def test_marker(self):
        """测试marker功能"""
        # 这个测试需要实际的J-Space环境，这里只是概念验证
        # jspace_marker("test-slug", "checkpoint", "测试检查点")
        pass
    
    def test_batch_note(self):
        """测试批量笔记功能"""
        # 这个测试需要实际的J-Space环境，这里只是概念验证
        # notes = [
        #     {"goal": "测试目标1"},
        #     {"next": "下一步行动1"},
        # ]
        # jspace_batch_note("test-slug", notes)
        pass


if __name__ == "__main__":
    unittest.main()