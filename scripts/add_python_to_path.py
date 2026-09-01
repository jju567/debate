"""Lisää Python 3.13:n suoraan käyttäjän PATH-ympäristömuuttujaan, jotta 'python' toimii suoraan."""
import os
import winreg

py_dir = r"C:\Users\Jarmo\AppData\Local\Programs\Python\Python313"
py_scripts = r"C:\Users\Jarmo\AppData\Local\Programs\Python\Python313\Scripts"

key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment", 0, winreg.KEY_ALL_ACCESS)
try:
    current_path, _ = winreg.QueryValueEx(key, "Path")
except FileNotFoundError:
    current_path = ""

paths = [p for p in current_path.split(";") if p]

if py_dir not in paths or py_scripts not in paths:
    # Lisätään alkuun
    new_paths = [py_dir, py_scripts] + [p for p in paths if p not in (py_dir, py_scripts)]
    new_path_str = ";".join(new_paths)
    winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, new_path_str)
    print("Python 3.13 lisätty onnistuneesti User PATH -muuttujaan!")
else:
    print("Python 3.13 on jo User PATH -muuttujassa.")

winreg.CloseKey(key)
