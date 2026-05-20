$ErrorActionPreference = "Stop"
Copy-Item -Force "logo.ico" "$env:LOCALAPPDATA\Nora\logo.ico"

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$HOME\Desktop\NORA Personal AI.lnk")
$Shortcut.IconLocation = "$env:LOCALAPPDATA\Nora\logo.ico"
$Shortcut.Save()

Copy-Item -Force "logo.ico" "NoraSetup\dist\logo.ico"
Copy-Item -Force "NoraInstaller.bat" "NoraSetup\NoraInstaller.bat"
Compress-Archive -Path "NoraSetup\*" -DestinationPath "NoraSetup.zip" -Force
