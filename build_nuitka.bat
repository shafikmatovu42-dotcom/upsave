@echo off
set OUT_DIR=build
rmdir /s /q %OUT_DIR% 2>nul
mkdir %OUT_DIR%

REM Use the project's virtualenv Python if present; otherwise fallback to system python
setlocal
set VENV_PY=%~dp0.venv\Scripts\python.exe
if exist "%VENV_PY%" (
  set PYTHON_EXE=%VENV_PY%
) else (
  set PYTHON_EXE=python
)

%PYTHON_EXE% -m nuitka ^
  --standalone ^
  --output-dir=%OUT_DIR% ^
  --show-progress ^
  --remove-output ^
  --include-package=streamlit ^
  --include-package=pandas ^
  --include-package=fpdf ^
  run_app.py

endlocal