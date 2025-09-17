Set WshShell = CreateObject("WScript.Shell")
caseid = WScript.Arguments(0)
WshShell.Run "u:\docketwatch\python\pdf_download_processor.bat " & caseid, 0, False
WScript.Quit