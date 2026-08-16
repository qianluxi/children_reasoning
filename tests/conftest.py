"""测试隔离：所有测试使用临时数据目录，绝不触碰 data/ 下的真实题库与儿童档案。

在导入任何 logic_kids 模块之前设置环境变量（config.py 在导入时读取它），
这样 tests/test_adaptive.py 等测试对题库的 clear/重建只影响临时目录。
"""
import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="logic_kids_test_")
os.environ["LOGIC_KIDS_DATA_DIR"] = _TMP
