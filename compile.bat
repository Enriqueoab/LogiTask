@echo off
setlocal enabledelayedexpansion

:: Create a list of all Java source files
set sourceFiles=
for /r src\main\java %%f in (*.java) do (
    set sourceFiles=!sourceFiles! "%%f"
)

:: Compile all Java files
javac -d out !sourceFiles!
