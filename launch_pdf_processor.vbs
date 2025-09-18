Set WshShell = CreateObject("WScript.Shell")
caseid = WScript.Arguments(0)
WshShell.Run "\\10.146.176.84\general\docketwatch\python\process_single_case_event.bat " & caseid, 0, False
WScript.Quit