!include "MUI2.nsh"

Name "PySoundPad"
OutFile "PySoundPad_Setup.exe"
InstallDir "$PROGRAMFILES\PySoundPad"

!define VBCABLE "$EXEDIR\VBCABLE_Setup.exe"
!define VOICEMEETER "$EXEDIR\VoicemeeterBananaSetup.exe"

Section "Instalar PySoundPad"

  SetOutPath "$INSTDIR"

  File /r "SoundPad.exe"

  DetailPrint "Instalando VB Cable..."
  ExecWait '"${VBCABLE}" /S' ; instalação silenciosa

  DetailPrint "Instalando VoiceMeeter Banana..."
  ExecWait '"${VOICEMEETER}" /SilentInstall'

  Sleep 5000

  DetailPrint "Configurando dispositivos de áudio..."

  ;; Definir VoiceMeeter como entrada padrão
  ExecWait 'powershell.exe -ExecutionPolicy Bypass -Command "Set-AudioDevice -Index (Get-AudioDevice -List | Where-Object { $_.Name -like '*VoiceMeeter Output*' }).Index -Role Communications,Console, Multimedia"'

  ;; Definir VB-Cable como loop interno
  ExecWait 'powershell.exe -ExecutionPolicy Bypass -Command "Set-AudioDevice -Index (Get-AudioDevice -List | Where-Object { $_.Name -like '*CABLE Input*' }).Index -Role Default"'

  ;; Reiniciar engine do VoiceMeeter
  ExecWait 'cmd.exe /C "start voicemeeter -r"'

  DetailPrint "Instalação concluída!"
  
  CreateShortcut "$DESKTOP\PySoundPad.lnk" "$INSTDIR\SoundPad.exe"

SectionEnd