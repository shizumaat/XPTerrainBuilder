@echo off
rem Associates .xptb packages (#2014) with this copy of XPTerrainBuilder for
rem the current user (no administrator rights; HKCU only).  The portable
rem zip has no installer, so the user runs this once from the folder that
rem holds XPTerrainBuilder.exe; double-clicking a .xptb then opens the app,
rem which shows the package's contents and asks before installing it
rem (O4_Qt_Tile_Package, through the launch arguments).
rem Undo: reg delete HKCU\Software\Classes\.xptb /f
rem       reg delete HKCU\Software\Classes\XPTerrainBuilder.Package /f
set "EXE=%~dp0XPTerrainBuilder.exe"
if not exist "%EXE%" (
  echo XPTerrainBuilder.exe is not in %~dp0 - run this from the app's folder.
  exit /b 1
)
reg add "HKCU\Software\Classes\.xptb" /ve /d "XPTerrainBuilder.Package" /f >nul
reg add "HKCU\Software\Classes\.xptbundle" /ve /d "XPTerrainBuilder.Package" /f >nul
reg add "HKCU\Software\Classes\XPTerrainBuilder.Package" /ve /d "XPTerrainBuilder package" /f >nul
reg add "HKCU\Software\Classes\XPTerrainBuilder.Package\DefaultIcon" /ve /d "\"%EXE%\",0" /f >nul
reg add "HKCU\Software\Classes\XPTerrainBuilder.Package\shell\open\command" /ve /d "\"%EXE%\" \"%%1\"" /f >nul
echo .xptb packages now open with %EXE%
