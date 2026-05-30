Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "cmd /c cd /d C:\Users\andyc\Downloads\painpoint-scout && venv\Scripts\streamlit.exe run dashboard.py", 0, False
