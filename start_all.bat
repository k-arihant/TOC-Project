@echo off
title TOC PS9 - Starting Services
cd /d "%~dp0"
echo ============================================================
echo   TOC PS9: Anomaly Detection in Process Workflows
echo ============================================================
echo Starting FastAPI backend on http://127.0.0.1:8000 ...
start "TOC FastAPI Backend" cmd /k "python -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000"

timeout /t 3 /nobreak >nul

echo Starting Streamlit Dashboard on http://127.0.0.1:8501 ...
start "TOC Streamlit Dashboard" cmd /k "streamlit run src/dashboard/app.py --server.port 8501"

echo ============================================================
echo Both servers have been launched in separate windows!
echo FastAPI docs: http://127.0.0.1:8000/docs
echo Streamlit UI: http://127.0.0.1:8501
echo ============================================================
pause
