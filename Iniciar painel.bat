@echo off
rem Abre o painel "Transcrição de áudio do Plaud Note Pro" (duplo clique).
rem Mantenha esta janela aberta enquanto usa o painel; feche-a para encerrar.
chcp 65001 >nul
title Transcricao de audio do Plaud Note Pro
cd /d "%~dp0"
".venv\Scripts\painel.exe"
if errorlevel 1 (
  echo.
  echo Nao foi possivel iniciar o painel. Veja a secao "Problemas comuns" do README.
  pause
)
