@echo off
rem Baut release\BlurSaveEditor.exe (eine einzelne Datei, ohne Python lauffaehig, zum Weitergeben).
rem Voraussetzung: Python 3 mit tkinter und pip (py -m ensurepip), dazu "py -m pip install pyinstaller".
rem The editor reads only save games and settings.xml; it does not access the game's files at run time. It does CONTAIN material from the game:
rem blursave_icons.zip (car silhouettes, manufacturer logos, Blur logo, mod symbols), sticker texts (blursave_stats.json), event and car names. See LICENSES.txt.
setlocal
cd /d "%~dp0.."
set T=%CD%\tools
py -m PyInstaller --noconfirm --clean --onefile --windowed --exclude-module numpy --exclude-module PIL --name BlurSaveEditor ^
  --paths "%T%" --add-data "%T%\blursave_vehicles.json;." ^
  --add-data "%T%\blursave_paints.json;." --add-data "%T%\blursave_icons.zip;." --add-data "%T%\blursave_events.json;." --add-data "%T%\blursave_stats.json;." --add-data "%T%\blursave_new.bin;." --add-data "%T%\blursave_ranks.json;." --add-data "%T%\blursave_campaign.json;." --add-data "%T%\LICENSES.txt;." ^
  --distpath release --workpath build_editor\work --specpath build_editor "%T%\blursave_editor.py"
