' CanonGate: tech / life / dual を選んで run_bg.bat に渡す
Option Explicit
Dim fso, shell, folder, choice, cmd, msg

Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
folder = fso.GetParentFolderName(WScript.ScriptFullName)

msg = "ALE / simple_chat のドメインを選んでください:" & vbCrLf & vbCrLf
msg = msg & "  tech = 仕事用のみ" & vbCrLf
msg = msg & "  life = プライベート用のみ" & vbCrLf
msg = msg & "  dual = 両方" & vbCrLf & vbCrLf
msg = msg & "入力 (未入力/Cancel = tech):"

choice = InputBox(msg, "CanonGate", "tech")

If choice = "" Then choice = "tech"
choice = LCase(Trim(choice))
If choice <> "tech" And choice <> "life" And choice <> "dual" Then choice = "tech"

cmd = "cmd.exe /c """ & folder & "\run_bg.bat " & choice & """"
shell.Run cmd, 0, False
