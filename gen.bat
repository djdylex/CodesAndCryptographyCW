@echo off
rem // Set ErrorLevel and exit code to a random number:
rem // Return the last digit of the hexadecimal exit code:
setlocal enabledelayedexpansion
for /l %%x in (1, 1, 100) do (
	call genrand var1
	encrypt.exe !var1!  >> out.txt
)