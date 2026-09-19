# -*- coding: utf-8 -*-
"""
component_service 最小回归测试。
使用临时 SQLite 文件，不碰真实数据库。
运行：.venv\\Scripts\\python.exe -m unittest tests.test_services -v
"""
import os
import sys
import tempfile
import unittest

# 让 tests 目录能 import 项目根目录的模块
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


class ComponentServiceTest(unittest.TestCase):
    """CRUD 基本回归"""

    @classmethod
    def setUpClass(cls):
        # 把数据库指到临时文件，测试完就删
        cls._tmpdir = tempfile.mkdtemp(prefix="matlib_test_")
        cls._db_path = os.path.join(cls._tmpdir, "test.db")

        from utils import constants
        constants.DATABASE_DIR = cls._tmpdir
        constants.DATABASE_PATH = cls._db_path

        # 建表
        from database.schema import init_db
        init_db()

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls._tmpdir, ignore_errors=True)

    def setUp(self):
        # 每个测试前清空
        from database.schema import get_connection
        conn = get_connection()
        conn.execute("DELETE FROM components")
        conn.commit()
        conn.close()

    # ---------- 基本 CRUD ----------

    def test_add_and_get_by_lcsc_id(self):
        """加完能按 LCSC 编号查回来"""
        from models.component import Component
        from services import component_service

        comp = Component(
            purpose="USB Hub 主控",
            generic_desc="USB Hub IC",
            model="SL2.1A",
            package="SOP-16",
            pin_count=16,
            lcsc_id="C192893",
            current_price=0.766,
        )
        new_id = component_service.add_component(comp)
        self.assertIsInstance(new_id, int)

        got = component_service.get_component_by_lcsc_id("C192893")
        self.assertIsNotNone(got)
        self.assertEqual(got.model, "SL2.1A")
        self.assertEqual(got.package, "SOP-16")
        self.assertEqual(got.pin_count, 16)

    def test_get_by_model(self):
        """按型号查回来"""
        from models.component import Component
        from services import component_service

        component_service.add_component(Component(
            purpose="电阻", generic_desc="1kΩ 0603", model="1kΩ",
            package="R0603", lcsc_id="C21190",
        ))
        got = component_service.get_component_by_model("1kΩ")
        self.assertIsNotNone(got)
        self.assertEqual(got.lcsc_id, "C21190")

    def test_update_component(self):
        """更新价格和封装"""
        from models.component import Component
        from services import component_service

        cid = component_service.add_component(Component(
            purpose="电容", generic_desc="0.1uF 0603", model="0.1uF",
            package="C0603", lcsc_id="C1590", current_price=0.02,
        ))
        component_service.update_component(cid, current_price=0.03, package="C0805")

        got = component_service.get_component_by_id(cid)
        self.assertEqual(got.current_price, 0.03)
        self.assertEqual(got.package, "C0805")

    def test_delete_component(self):
        """删除后查不到"""
        from models.component import Component
        from services import component_service

        cid = component_service.add_component(Component(
            purpose="测试", generic_desc="测试", model="TEST-1",
            lcsc_id="C999999",
        ))
        component_service.delete_component(cid)
        self.assertIsNone(component_service.get_component_by_lcsc_id("C999999"))

    def test_search_components_multi(self):
        """多关键词搜索能命中"""
        from models.component import Component
        from services import component_service

        component_service.add_component(Component(
            purpose="晶振", generic_desc="12MHz 晶振", model="YC12MLBCD2XT",
            package="CRYSTAL-SMD_4P", lcsc_id="C51484101",
        ))
        component_service.add_component(Component(
            purpose="电阻", generic_desc="1kΩ 0603", model="1kΩ",
            package="R0603", lcsc_id="C21190",
        ))

        results = component_service.search_components_multi("晶振")
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0].lcsc_id, "C51484101")

    # ---------- 边界情况 ----------

    def test_get_nonexistent_returns_none(self):
        """查不到返回 None，不抛异常"""
        from services import component_service
        self.assertIsNone(component_service.get_component_by_lcsc_id("C000000"))
        self.assertIsNone(component_service.get_component_by_model("NOT-EXIST"))
        self.assertIsNone(component_service.get_component_by_id(999999))

    def test_empty_search_returns_list(self):
        """空库搜索返回空列表，不报错"""
        from services import component_service
        self.assertEqual(component_service.search_components_multi("随便什么"), [])

    def test_list_all_empty(self):
        """空库 list_all 返回空列表"""
        from services import component_service
        self.assertEqual(component_service.list_all_components(), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)