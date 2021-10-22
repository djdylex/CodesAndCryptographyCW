import math
import bitstream
import numpy as np
import sys
BITSIZE = 32 # Don't change without changing casts
HALF = 2 ** (BITSIZE - 1)
EOT = chr(3)
ESC = chr(27)
ORDER = 5


# Analyse text and return symbosl and their frequency
# print(bin(lower)[2:].zfill(32))

def getStartDict(charSet = '01'): # Gives start dictionary based on char set
    freqs = {}
    if charSet == '00': # Standard char set
        # Define EOF
        freqs[EOT] = 1
        freqs[chr(13)] = 1
        freqs[chr(9)] = 1
        freqs[chr(10)] = 1
        for i in range (32, 127):
            freqs[chr(i)] = 1
    elif charSet == '01': # Full char set
        for i in range (0, 128):
            freqs[chr(i)] = 1
    elif charSet == '10': # Boook char set
        freqs[EOT] = 1
        freqs['('] = 1
        freqs[')'] = 1
        freqs['!'] = 1
        freqs['?'] = 1
        freqs['"'] = 1
        freqs[','] = 1
        freqs['.'] = 1
        freqs['-'] = 1
        freqs["'"] = 1
        for i in range (48, 60):
            freqs[chr(i)] = 1
        for i in range (65, 91):
            freqs[chr(i)] = 1
        for i in range (97, 123):
            freqs[chr(i)] = 1
    else:
        print("charSet not recognized.")
        return
    return freqs, len(freqs)


def binaryChucker(iLow, iUp, bitSize): # No writing, just chucking stuff out
    shiftBy = 0
    while (iLow < HALF) == (iUp < HALF): # Keep iterating until can not longer match bits
        iLow = (iLow << 1) % 2** bitSize # Keep result constraint to bit sized, otherwise will fake python 'overflow'
        iUp = (iUp << 1) % 2** bitSize
        iUp += 1 # upper bound always 1 incomming
        shiftBy += 1
    return iLow, iUp, shiftBy


def scaleCounts(counts, total, bitSize): # Inplace
    maxCum = 2 ** 10#2 ** (bitSize - 2) # The largest all the freqs can add up to, high values increase model accuracy, lower values increase locality. This effectively resets
    scaleBy = math.ceil(total / maxCum)
    for symbol in counts:
        counts[symbol] = int(counts[symbol] / scaleBy) # Scale them down
        counts[symbol] = counts[symbol] if counts[symbol] != 0 else 1 # Make sure all are one otherwise looses a symbol

def computeCum(counts, cum): # Inplace modification of cumulative count
    valBefore = 0
    for sym in counts:
        cum[sym] = (valBefore, valBefore + counts[sym])
        valBefore = valBefore + counts[sym]
    return valBefore # valBefore set to total count of symbols at end, we need to have this as its updated value due to scaling

def updateValues(contexts, workContx, c, cntxLimit=0):
    while len(workContx) >= cntxLimit:
        if workContx not in contexts: # Create new context
            contexts[workContx] = {}
            contexts[workContx]['tot'] = 2
            contexts[workContx]['freq'] = {ESC: 0, c: 1}
            contexts[workContx]['cum'] = {}
        else:
            if c not in contexts[workContx]['freq']:  # If we havent seen c then need to create it with freq 1, update ESC value
                contexts[workContx]['freq'][c] = 1
                contexts[workContx]['freq'][ESC] += 1
                contexts[workContx]['tot'] += 2
            else:
                contexts[workContx]['freq'][c] += 1
            contexts[workContx]['tot'] += 1

        scaleCounts(contexts[workContx]['freq'], contexts[workContx]['tot'], BITSIZE)
        contexts[workContx]['tot'] = computeCum(contexts[workContx]['freq'],
                                                contexts[workContx]['cum'])  # Inplace modifcation of cumulative freq

        if workContx == "":
            break
        workContx = workContx[1:]

def restrictContext(contexts, workContx, seenChars):
    contextSel = {}
    if seenChars:  # Recalculate freqs/cums for characters we know will not occur, so can restrict possible characters for decoder
        contextSel['freq'] = {k: contexts[workContx]['freq'][k] for k in contexts[workContx]['freq'].keys() if
                              k not in seenChars}
        contextSel['cum'] = {}
        contextSel['tot'] = computeCum(contextSel['freq'], contextSel['cum'])
    else:
        contextSel = contexts[workContx]
    return contextSel

defaultDict = {'tot': 0, 'freq': getStartDict()[0], 'cum': {}}
defaultDict['tot'] = computeCum(defaultDict['freq'], defaultDict['cum'])
#LATEX_DICT['tot'] = computeCum(LATEX_DICT['freq'], LATEX_DICT['cum'])

def decode(inFileName, outFileName, order): # This decodes by retracing the steps of the encoder exactly, keeps memory usage minimal
    inFile = open(inFileName, 'rb')
    outFile = open(outFileName, 'w')

    t = bitstream.BitStream()
    t.write(inFile.read(int(2 * BITSIZE/8)), bytes) # No big problem if we read too many
    tar = t.read(np.uint32) # tar is the integer number we are currently working on, by default 32 bits, this is sufficient.]

    contexts = {'': {'tot': 0, 'freq': getStartDict()[0] , 'cum': {}}}
    contexts[""]['tot'] = computeCum(contexts[""]['freq'], contexts['']['cum'])

    lower = 0
    upper = 0xFFFFFFFF
    string = "" # Output string
    context = ""
    while True: # Retrace steps of the encoder
        numRange = upper - lower + 1
        workContx = '#' + context

        search = True
        seenChars = set()
        while search:
            contextSel = {}
            workContx = workContx[1:]
            if workContx in contexts:
                contextSel = restrictContext(contexts, workContx, seenChars)
                for c in contextSel['cum']: # Go through all cum freqs and match
                    total = contextSel['tot']
                    tempUpper = lower + int((numRange * contextSel['cum'][c][1]) / total - 1)
                    tempLower = lower + int((numRange * contextSel['cum'][c][0]) / total)
                    if tempLower <= tar <= tempUpper:
                        if c == EOT:  # If we get the EOT character then we are done
                            inFile.close()
                            outFile.close()
                            return

                        lower = tempLower
                        upper = tempUpper
                        lower, upper, shiftBy = binaryChucker(lower, upper, BITSIZE)  # Shift out bits
                        numRange = upper - lower + 1

                        if c != ESC: # If its not an escape then we are done looping through contexts
                            string += c
                            outFile.write(c)
                            updateValues(contexts, context, c, 0 if workContx == 'defDict' else len(workContx))
                            search = False
                        else:
                            seenChars = seenChars.union(set(contexts[workContx]['freq'].keys()))
                            seenChars.remove(ESC) # Add to seen characters (without esc character, don't want to ignore that)

                        for i in range(shiftBy):  # Shift by amount from binaryChucker, read next bit from bitstream
                            tar = (tar << 1) % 2 ** BITSIZE # Shift target
                            try:
                                tar += 1 if t.read(bool, 1)[0] else 0  # Get new bits, error if there arn't any (no EOT in file)
                            except:
                                inFile.close()
                                print("Error: End of stream reached before end of text symbol. Invalid encoding file")
                                return

                        if len(t) < 2 * BITSIZE:  # Get more bits if needed from bit stream
                            r = inFile.read(1)
                            if r:
                                t.write(r, bytes)
                        break
            if not workContx: # This means we drop back to the default dict, -1 order
                workContx = "#defDict"

        context += c # Update context
        context = context[-order:order+1][:order]

    inFile.close()
    outFile.close()

if not sys.argv[1]:
    print("Please input the latex file to compress")
    exit()

decode(sys.argv[1], sys.argv[1][:-3] + '-decoded.tex', 5)