@echo off
REM Compile les sources de test (src\langage, src\builtins) avec le ktrans installe
REM sur ce PC, pour chaque version WinOLPC installee. Aucune saisie demandee.
REM Resultats : pc\<version>\..., journaux : log\<version>\... (non versionnes).
REM ktrans ecrit le .pc dans le dossier courant : on se place donc dans le dossier de sortie.
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
REM Liste des versions installees (sortie de ktrans sans argument, fichier local non versionne).
"%KTRANS%" < nul > versions_installees.txt 2>&1
if "%VERS%"=="" (
  for /f "tokens=1" %%A in ('findstr /r /c:"^ *V[0-9]" versions_installees.txt') do set VERS=!VERS! %%A
)
REM Incremental : un source deja compile (journal present) n'est pas recompile.
REM Pour tout refaire, supprimer les dossiers pc et log.
for %%V in (%VERS%) do (
  echo ===== %%V
  for %%D in (langage builtins) do (
    if not exist "%ROOT%\pc\%%V\%%D" mkdir "%ROOT%\pc\%%V\%%D"
    if not exist "%ROOT%\log\%%V\%%D" mkdir "%ROOT%\log\%%V\%%D"
    pushd "%ROOT%\pc\%%V\%%D"
    REM fichiers inclus : ktrans les cherche dans le dossier courant
    if exist "%ROOT%\src\include\*.kl" copy /y "%ROOT%\src\include\*.kl" . > nul
    for %%F in ("%ROOT%\src\%%D\*.kl") do (
      if not exist "%ROOT%\log\%%V\%%D\%%~nF.txt" "%KTRANS%" "%%~fF" /ver %%V < nul > "%ROOT%\log\%%V\%%D\%%~nF.txt" 2>&1
    )
    if exist "%ROOT%\src\include\*.kl" for %%I in ("%ROOT%\src\include\*.kl") do del /q "%%~nxI"
    popd
  )
)
echo Compilation terminee.
