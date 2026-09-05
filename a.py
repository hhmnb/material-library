import os
import sys
import unittest
import tempfile
import shutil
import csv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import database.schema as schema
import services.component_service as service
from models.component import Component


class BomImportTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # 使用临时数据库
        cls.temp_dir = tempfile.mkdtemp()
        cls.old_data_dir = schema.constants.DATABASE_DIR
        schema.constants.DATABASE_DIR = cls.temp_dir
        schema.init_db()

    @classmethod
    def tearDownClass(cls):
        schema.constants.DATABASE_DIR = cls.old_data_dir
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def setUp(self):
        # 每个测试前清空数据
        conn = schema.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM components")
        conn.commit()
        conn.close()

    def _create_csv_file(self, content, encoding='utf-8-sig'):
        """创建临时 CSV 文件，返回文件路径"""
        filepath = os.path.join(self.temp_dir, 'test_bom.csv')
        with open(filepath, 'w', newline='', encoding=encoding) as f:
            f.write(content)
        return filepath

    def test_import_utf8_csv(self):
        csv_content = (
            "No.,Quantity,Comment,Designator,Footprint,Manufacturer Part,Manufacturer,Supplier Part,Supplier\n"
            "1,3,10uF,C1,C0603,10uF,,,\n"
            "2,1,SL2.1A,U1,SOP-16,SL2.1A,CoreChips,C192893,LCSC\n"
        )
        filepath = self._create_csv_file(csv_content, encoding='utf-8-sig')
        result = service.import_bom_from_csv(filepath)

        self.assertEqual(result['success'], 2)
        self.assertEqual(len(result['failures']), 0)

        # 验证数据
        comp1 = service.get_component_by_model('10uF')
        self.assertIsNotNone(comp1)
        self.assertEqual(comp1.package, 'C0603')
        comp2 = service.get_component_by_lcsc_id('C192893')
        self.assertIsNotNone(comp2)
        self.assertEqual(comp2.model, 'SL2.1A')

    def test_import_utf16_csv(self):
        csv_content = (
            "No.,Quantity,Comment,Designator,Footprint,Manufacturer Part,Manufacturer,Supplier Part,Supplier\n"
            "1,5,100uF,C2,C0805,GRM21BR60J107ME15L,muRata,C141660,LCSC\n"
        )
        filepath = self._create_csv_file(csv_content, encoding='utf-16')
        result = service.import_bom_from_csv(filepath)

        self.assertEqual(result['success'], 1)
        self.assertEqual(len(result['failures']), 0)

        comp = service.get_component_by_lcsc_id('C141660')
        self.assertIsNotNone(comp)
        self.assertEqual(comp.package, 'C0805')

    def test_import_duplicate_skips(self):
        # 先手动添加一个元件
        existing = Component(
            purpose="测试",
            generic_desc="测试",
            model="SL2.1A",
            package="SOP-16",
            lcsc_id="C192893",
        )
        service.add_component(existing)

        csv_content = (
            "No.,Quantity,Comment,Designator,Footprint,Manufacturer Part,Manufacturer,Supplier Part,Supplier\n"
            "1,1,SL2.1A,U1,SOP-16,SL2.1A,CoreChips,C192893,LCSC\n"
        )
        filepath = self._create_csv_file(csv_content, encoding='utf-8-sig')
        result = service.import_bom_from_csv(filepath)

        self.assertEqual(result['success'], 0)
        self.assertEqual(len(result['failures']), 1)
        self.assertIn('重复', result['failures'][0])

    def test_import_invalid_row(self):
        csv_content = (
            "No.,Quantity,Comment,Designator,Footprint,Manufacturer Part,Manufacturer,Supplier Part,Supplier\n"
            "1,1,,C1,C0603,,,\n"   # 缺少有效型号
        )
        filepath = self._create_csv_file(csv_content, encoding='utf-8-sig')
        result = service.import_bom_from_csv(filepath)

        self.assertEqual(result['success'], 0)
        self.assertEqual(len(result['failures']), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)