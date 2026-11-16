import subprocess
import sys
import time
import os

repo_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(repo_dir)

print(f"Starting servers from {repo_dir}...")

api_cmd = [sys.executable, "-m", "uvicorn", "src.api.main:app", "--host", "127.0.0.1", "--port", "8000"]
dash_cmd = [sys.executable, "-m", "streamlit", "run", "src/dashboard/app.py", "--server.port", "8501", "--server.headless", "true"]

p_api = subprocess.Popen(api_cmd)
print(f"Uvicorn API started (PID {p_api.pid}) on http://127.0.0.1:8000")

time.sleep(2)

p_dash = subprocess.Popen(dash_cmd)
print(f"Streamlit Dashboard started (PID {p_dash.pid}) on http://127.0.0.1:8501")

try:
    while True:
        time.sleep(2)
        if p_api.poll() is not None:
            print(f"Uvicorn exited with code {p_api.returncode}")
            break
        if p_dash.poll() is not None:
            print(f"Streamlit exited with code {p_dash.returncode}")
            break
except KeyboardInterrupt:
    print("Shutting down servers...")
    p_api.terminate()
    p_dash.terminate()
