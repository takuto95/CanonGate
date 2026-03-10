' CanonGate: Choose tech / life / dual and pass to run_bg.bat
' Fixed encoding: Use English text to avoid mojibake in Windows InputBox
Option Explicit
Dim fso, shell, folder, choice, cmd, msg

Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
folder = fso.GetParentFolderName(WScript.ScriptFullName)

msg = "Select CanonGate Domain (ALE / simple_chat):" & vbCrLf & vbCrLf
msg = msg & "  tech = Work only (Default)" & vbCrLf
msg = msg & "  life = Private only" & vbCrLf
msg = msg & "  dual = Both (Tech + Life)" & vbCrLf & vbCrLf
msg = msg & "Input (Empty/Cancel = tech):"

choice = InputBox(msg, "CanonGate Startup", "tech")

If choice = "" Then choice = "tech"
choice = LCase(Trim(choice))

' Validation
If choice <> "tech" And choice <> "life" And choice <> "dual" Then choice = "tech"

' Execute run_bg.bat with the chosen domain
' Use 0 to hide the command window
cmd = "cmd.exe /c """ & folder & "\run_bg.bat " & choice & """"
shell.Run cmd, 0, False
