@echo off
setlocal

set SOURCE=\\10.146.176.84\general\docketwatch\court-beta

set TARGET1=\\10.146.176.84\general\docketwatch\court
set TARGET2=\\10.146.176.84\general\tmztools\wwwroot\court
set TARGET3=\\10.146.176.84\general\tmztools\wwwroot\court-beta

:: Exclude .git folder
for %%T in ("%TARGET1%" "%TARGET2%" "%TARGET3%") do (
    echo Replacing contents of %%T with %SOURCE%
    robocopy "%SOURCE%" "%%~T" /MIR /XD "%SOURCE%\.git"
)

echo Done.
pause
