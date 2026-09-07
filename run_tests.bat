@echo off
cd /d "%~dp0"
set PYTHONPATH=backend
if exist pytest_tmp5 rd /s /q pytest_tmp5
python -m pytest tests/test_friday_tools.py::TestToolPermissions::test_default_tool_permissions_are_automatic tests/test_kasa_agent.py tests/test_live_video.py -v --basetemp=pytest_tmp5 > pytest_final5.txt 2>&1
echo EXIT_%ERRORLEVEL% > pytest_final5_exit.txt
if exist pytest_tmp6 rd /s /q pytest_tmp6
python -m pytest tests/test_autonomy_pipeline.py tests/test_capability_learning.py -v --basetemp=pytest_tmp6 > pytest_final_pl.txt 2>&1
echo EXIT_%ERRORLEVEL% > pytest_final_pl_exit.txt
