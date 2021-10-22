cmd /C exit %RANDOM%
set ran1=%=ExitCode:~-3%
cmd /C exit %RANDOM%
set ran2=%=ExitCode:~-3%
cmd /C exit %RANDOM%
set ran3=%=ExitCode:~-3%
cmd /C exit %RANDOM%
set ran4=%=ExitCode:~-3%
cmd /C exit %RANDOM%
set ran5=%=ExitCode:~-3%
cmd /C exit %RANDOM%
set ran6=%=ExitCode:~-3%
cmd /C exit %RANDOM%
set ran7=%=ExitCode:~-3%
cmd /C exit %RANDOM%
set ran8=%=ExitCode:~-3%
cmd /C exit %RANDOM%
set ran9=%=ExitCode:~-3%
cmd /C exit %RANDOM%
set ran10=%=ExitCode:~-3%
cmd /C exit %RANDOM%
set ran11=%=ExitCode:~-2%

set rand=%ran1%%ran2%%ran3%%ran4%%ran5%%ran6%%ran7%%ran8%%ran9%%ran10%%ran11%
(echo %rand%)>>in.txt
set %~1=%rand%