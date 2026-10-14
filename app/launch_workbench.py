"""GUI entry point with a persistent error log instead of a silent exit."""
import ctypes,datetime,os,runpy,sys,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parent
os.chdir(ROOT)
logs=ROOT/'logs'; logs.mkdir(exist_ok=True)
with (logs/'startup.log').open('a',encoding='utf-8',buffering=1) as log:
    sys.stdout=log; sys.stderr=log
    print('\nSTART',datetime.datetime.now().isoformat(),sys.executable)
    try:
        runpy.run_path(str(ROOT/'config_app_v2.py'),run_name='__main__')
    except Exception:
        traceback.print_exc()
        ctypes.windll.user32.MessageBoxW(None,'工作台启动失败。错误已记录在：\n'+str(logs/'startup.log')+'\n\n请使用文件夹中的“打开工作台.bat”重新检查依赖。','VBA 工作台',0x10)
        raise SystemExit(1)
