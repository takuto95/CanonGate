Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "cmd.exe /c """ & CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName) & "\run_bg.bat""", 0, False
