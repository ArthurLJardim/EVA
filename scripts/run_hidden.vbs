' Executa um script PowerShell sem exibir nenhuma janela de console.
' Uso: wscript.exe run_hidden.vbs "<caminho_do_script.ps1>"

Set objArgs = WScript.Arguments
If objArgs.Count < 1 Then
    WScript.Quit 1
End If

scriptPath = objArgs(0)

Set objShell = CreateObject("WScript.Shell")
command = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File """ & scriptPath & """"
objShell.Run command, 0, True
