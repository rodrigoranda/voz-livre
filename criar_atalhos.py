# Cria atalhos "Voz Livre" na Area de Trabalho e no Menu Iniciar (chamado pelo instalar.bat)
import os, sys, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import voz_livre

if not os.path.exists(voz_livre.ICO):
    voz_livre.desenhar(voz_livre.CORES["pronto"], 256).save(
        voz_livre.ICO, sizes=[(16, 16), (32, 32), (48, 48), (256, 256)])
alvo = os.path.join(voz_livre.BASE, "voz_livre.py")
ps = f"""
$ws = New-Object -ComObject WScript.Shell
foreach ($p in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))) {{
  $l = $ws.CreateShortcut("$p\\Voz Livre.lnk")
  $l.TargetPath = '{voz_livre.PYTHONW}'
  $l.Arguments = '"{alvo}"'
  $l.WorkingDirectory = '{voz_livre.BASE}'
  $l.IconLocation = '{voz_livre.ICO}'
  $l.Description = 'Voz Livre - ditado por voz'
  $l.Save()
  Write-Output "  Atalho criado: $p\\Voz Livre.lnk"
}}
"""
subprocess.run(["powershell", "-NoProfile", "-Command", ps])
