"""Тесты работают на отдельной временной БД и не трогают рабочий campusflow.db."""
import os
import tempfile

_tmp = tempfile.mkdtemp()
os.environ["CAMPUSFLOW_DB_URL"] = "sqlite:///" + os.path.join(_tmp, "test.db").replace("\\", "/")
