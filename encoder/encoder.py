import math
import bitstream
#import os
import sys
BITSIZE = 32 # Don't change without changing casts
HALF = 2 ** (BITSIZE - 1)
EOT = chr(3)
ESC = chr(27)
ORDER = 5

LATEX_DICT = {
    'tot': 0,
    'freq': {
        ESC: 17,
        'documentclass': 1,
        'begin': 1,
        'maketitle': 1,
        'pagenumbering': 1,
        'newpage': 1,
        'section': 1,
        'subsection': 1,
        'usepackage': 1,
        'underline': 1,
        'includegraphics': 1,
    },
    'cum': {}
}


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

def binaryMatcher(iLow, iUp, stream, bitSize):
    while True: # Keep iterating until can not longer match bits
        if iLow < HALF and iUp < HALF:
            stream.write(False, bool)
        elif iLow >= HALF and iUp >= HALF:
            stream.write(True, bool)
        else:
            break # No match so stop

        iLow = (iLow << 1) % 2**bitSize
        iUp = (iUp << 1) % 2**bitSize
        iUp += 1 # upper bound always 1 incomming
    return iLow, iUp


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
            if c not in contexts[workContx]['freq']:  # If we havent seen c then need to create it with freq 1
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

def writeRange(context, c, low, hi, stream):
    #print(c, context)
    total = context['tot']
    numRange = hi - low + 1
    hi = low + int((numRange * context['cum'][c][1]) / total - 1)  # Dont miss out the brackets around the -1 otherwise it will overflow to 0's and cause a negative number
    low = low + int((numRange * context['cum'][c][0]) / total)
    low, hi = binaryMatcher(low, hi, stream, BITSIZE)  # Match and shift out bits to the bit stream
    return low, hi

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

def encode(inFileName, outFileName, order):
    #fileSize = os.path.getsize(inFileName)

    # this dictionary is a dictionary of contexts and their frequencies/cumulative freq, they also store a total
    # Structure
    #    Context: (length 0 - order)
    #       tot: int
    #       Freq: {'a' : 10 ...}
    #       Cum: {'a': (0, 10), 'b': (10, 13) ...}
    contexts = {'': {'tot': 0, 'freq': getStartDict()[0] , 'cum': {}}}
    contexts[""]['tot'] = computeCum(contexts[""]['freq'], contexts['']['cum']) # Handle slightly differently here due to program layout
    inFile = open(inFileName, 'r', encoding='ascii')
    outFile = open(outFileName, 'wb')
    stream = bitstream.BitStream()

    lower = 0
    upper = (2 ** BITSIZE) - 1

    c = inFile.read(1) # Iterate through file character by character

    context = "" # Context we are currently dealing with
    #escWritten = 0
    while True:
        workContx = "#" + context # The reason i do this is because i want to reuse workContx after and because it makes the loop a little clearer
        contextSel = {}
        """if workContx[-1] == '\\' and c.isalpha():  # Command handler for latex, reads ahead in file to see if we have something we've seen.
            leftOff = inFile.tell()  # Get index of file
            command = ""
            tC = c
            while tC.isalpha():
                command += tC
                tC = inFile.read(1)
            if len(command) > 10:
                if command in LATEX_DICT['freq']:
                    c = tC
                    lower, upper = writeRange(LATEX_DICT, command, lower, upper, stream)
                    LATEX_DICT['freq'][command] += 1
                    LATEX_DICT['tot'] = computeCum(LATEX_DICT['freq'], LATEX_DICT['cum'])
                    #context = command[-order:]
                else: # If we havent seen this command before, write esc then add to dict
                    escWritten += 1
                    inFile.seek(leftOff)
                    lower, upper = writeRange(LATEX_DICT, ESC, lower, upper, stream)
                    LATEX_DICT['freq'][command] = 1
                    LATEX_DICT['freq'][ESC] += 1
                    LATEX_DICT['tot'] = computeCum(LATEX_DICT['freq'], LATEX_DICT['cum'])
            else:
                inFile.seek(leftOff)"""
        #print(inFile.tell())

        if not c: # Once at end set character to EOT to write that
            c = EOT
        seenChars = set()
        while workContx: # Goes through contexts until it finds one it has seen before, once it does it sets the current cumHi and low values
            contextSel = {} # Investigate this !!!!!!!!!!!!
            workContx = workContx[1:] # Drop down a context
            if workContx in contexts: # Check if we've seen this context before, if not we don't do anything as we decoder will know we are shifting down a context (theres no other option)
                if c in contexts[workContx]['freq']:
                    contextSel = restrictContext(contexts, workContx, seenChars)
                    break
                else:
                    # Write esc to stream
                    #escWritten += 1
                    contextSel = restrictContext(contexts, workContx, seenChars)
                    lower, upper = writeRange(contextSel, ESC, lower, upper, stream)
                    seenChars = seenChars.union(set(contextSel['freq'].keys())) # Add the set we've the list of characters it can't be next
                    seenChars.remove(ESC)

            if not workContx: # This means we drop back to the default dict, -1 order
                workContx = '#defDict'
        lower, upper = writeRange(contextSel, c, lower, upper, stream)


        if len(stream) >= 8: # Write while we are working in order to save on working memory, otherwise large documents could take up lots of memory
            outFile.write(stream.read(bytes, 1))

        # Update values for contexts n to 0, doing this after makes sense as it is easier for the decoder to figure out whats happened
        updateValues(contexts, context, c, len(workContx))

        context += c # Update context
        context = context[-order:order+1][:order]

        if c == EOT: # If we get an EOT its the end
            break
        c = inFile.read(1)


    # Bitstream is clearly buggy, but is quite fast so will just work around, have to write last part manually for some reason
    for b in bin(int((lower + upper) / 2))[2:].zfill(BITSIZE):
        stream.write(b == '1', bool)

    # Write as many bytes as possible
    while len(stream) >= 8:
        outFile.write(stream.read(bytes, 1))

    # Write final few bits, bit clunky
    if len(stream) > 0:
        leftOver = stream.read(bool, len(stream))
        final = 0
        for i, bit in enumerate(leftOver):
            final += 2**(7-i) if bit else 0
        outFile.write(bytes([final]))

    inFile.close()
    outFile.close()
    #encSize = os.path.getsize(outFileName) * 8
    """print("Out Size: ", encSize)
    print("BPC: ", encSize/fileSize)
    print("Ratio: ", fileSize/(encSize/8))"""

if not sys.argv[1]:
    print("Please input the latex file to compress")
    exit()

encode(sys.argv[1], sys.argv[1][:-4] + '.lz', 5)
#decode("out.lz", "output.txt", 5)