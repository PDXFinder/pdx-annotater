#!/usr/local/bin/python
# -*- coding: utf-8 -*-

import os
import re


def logMessage (updogDir,filename, logMessage) :
    with open(upDogDir + "/log".format(filename), 'a+') as log:

        print(logMessage)
        log.write(logMessage + "\n")

def chmodFile(annoFilename):
        os.chmod(annoFilename, 0o666)

def flushCloseFile(fileToClose):
    fileToClose.flush()
    fileToClose.close()


def masterlogMessage(masterLog, logMessage):
    with open(masterLog, 'a+') as log:

       print(logMessage)
       log.write(logMessage + "\n")

def formatChromo(givenChromo):

    incorrectChrFormat = "(?i)^chr([0-9]{1,2}|[xym]{1}|mt|un)$"
    isMatch = re.match(incorrectChrFormat,givenChromo)
    if isMatch: chromo = isMatch.group(1)
    else: chromo = givenChromo
    return chromo


