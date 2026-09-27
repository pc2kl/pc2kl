@echo off
REM Validation aller-retour : recompile les sources produits par pc2kl (roundtrip\kl,
REM voir outils\decompiler_tout.py) avec la meme version de ktrans que l'original.
REM Resultats : roundtrip\pc, journaux : roundtrip\log (non versionnes).
setlocal enabledelayedexpansion
cd /d "%~dp0"
set ROOT=%CD%
if "%KTRANS%"=="" (
  for %%P in (ktrans.exe) do set KTRANS=%%~$PATH:P
)
if "%KTRANS%"=="" if exist "C:\Program Files (x86)\FANUC\WinOLPC\bin\ktrans.exe" set KTRANS=C:\Program Files (x86)\FANUC\WinOLPC\bin\ktrans.exe
if "%KTRANS%"=="" (
  for /f "delims=" %%P in ('where /r "C:\Program Files (x86)\FANUC" ktrans.exe 2^>nul') do if "!KTRANS!"=="" set KTRANS=%%P
)
if "%KTRANS%"=="" (
  echo ktrans.exe introuvable : definir la variable KTRANS.
  exit /b 1
)
for /d %%V in ("%ROOT%\roundtrip\kl\*") do (
  for %%D in (langage builtins) do (
    if exist "%%V\%%D" (
      if not exist "%ROOT%\roundtrip\pc\%%~nxV\%%D" mkdir "%ROOT%\roundtrip\pc\%%~nxV\%%D"
      if not exist "%ROOT%\roundtrip\log\%%~nxV\%%D" mkdir "%ROOT%\roundtrip\log\%%~nxV\%%D"
      pushd "%ROOT%\roundtrip\pc\%%~nxV\%%D"
      for %%F in ("%%V\%%D\*.kl") do (
        if not exist "%ROOT%\roundtrip\log\%%~nxV\%%D\%%~nF.txt" "%KTRANS%" "%%~fF" /ver %%~nxV < nul > "%ROOT%\roundtrip\log\%%~nxV\%%D\%%~nF.txt" 2>&1
      )
      popd
    )
  )
)
echo Recompilation terminee.
