"""启动 Web 辩论界面"""
import subprocess
import webbrowser
import sys
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

# 打开浏览器
webbrowser.open("http://localhost:8501")

# 启动 streamlit
subprocess.run([sys.executable, "-m", "streamlit", "run", "webui.py"])
