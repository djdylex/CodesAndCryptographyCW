import subprocess
import secrets

outFile = open("out.txt", 'a')
inFile = open("in.txt", 'a')

for i in range(0, 100000):
    if i % 100 == 0:
        print(i)
        
    hexArg = secrets.token_hex(16)
    args = "encrypt.exe " + hexArg
    out = str(subprocess.check_output(args, stderr=subprocess.DEVNULL, creationflags=0x08000000))
    inFile.write(hexArg + "\n")
    outFile.write(out[2:-5] + "\n")

outFile.close()
inFile.close()
