$wshell = New-Object -ComObject Wscript.Shell
$wshell.Run("cmd /c ssh nora1@ssh-nora1.alwaysdata.net ""git clone https://github.com/Doniyorbek2000/aNora.git || (cd aNora && git pull)""", 1, $false)
