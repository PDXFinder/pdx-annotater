#!/usr/bin/python2.7
# -*- coding: utf-8 -*-
import csv
import json
import os
import sys
import time
import logging
import re
import pandas as pa

import AnnotationFilter

mergedPointsMissed = 0

if len(sys.argv) > 1:
    tsvFilePath = sys.argv[1]
    tsvFileName = os.path.basename(tsvFilePath)
    parentDirectory = os.path.dirname(sys.argv[1])
    provider = os.path.dirname(parentDirectory)
    Updog = os.path.dirname(provider)

    logging.basicConfig(filename='{}.log'.format(tsvFilePath), filemode='a+', level=logging.DEBUG)
    logging.info(" Beginning to compile annotation with provider data ")
else:
    sys.stderr.write(" Warning: Merger is being ran without file input. This should only be used for testing ")


def run():
    mergeRowsAndWrite()
    logging.info("Merge complete")

def mergeRowsAndWrite():
    with open(tsvFilePath + ".hmz", 'w') as finalTemplate, \
            open(tsvFilePath + ".ANN", 'r') as annoFile, \
            open(tsvFilePath, 'r') as tsvFile:
        outFileWriter = csv.writer(finalTemplate, delimiter="\t")
        tsvReader = getTsvReader(tsvFile)
        annoReader = pa.read_csv(annoFile, delimiter='\t', error_bad_lines=False, header=97)
        headers = buildHeaders()
        outFileWriter.writerow(headers)
        logBeginningOfMerge(tsvFilePath)
        iterateThroughRowsAndMerge(tsvReader,annoReader, outFileWriter)

def getTsvReader(tsvFile):
    if tsvFilePath.endswith(".csv"):
        tsvReader = csv.DictReader(tsvFile, delimiter=",")
    else:
        tsvReader = csv.DictReader(tsvFile, delimiter="\t")
    return tsvReader

def logBeginningOfMerge(tsvFilePath):
    message = ("Merging original data :"
               " {0} /n and annotated data : {1} at {2}".format(tsvFilePath, tsvFilePath + "ANN", time.ctime()))
    logging.info(message)

def iterateThroughRowsAndMerge(reader, annoReader, outFileWriter):
    rowNum = 0
    rowAdded = 0
    for row in reader:
        rowNum += 1
        if rowIsValidForMerge(row):
            mergedRow = mergeRows(row, annoReader, rowNum)
            if len(mergedRow) >= 26:
                outFileWriter.writerow(mergedRow)
                rowAdded += 1
            else:
                message = ("Info: Row Number {0}: "
                           "Dropping row for being invalid (size or column headers) "
                           "or missing match in annotations (Chromosome position error). "
                           "Row: {0} - Length {1} - data {2}".format(rowNum, len(mergedRow), mergedRow))
                logging.warning(message)
        else:
            message2 = ("Info: Row Number {0}: is broken or legacy".format(rowNum))
            logging.warning(message2)
    message3 = ("{0} The completed file file {1} has {2}"
                " data points (including header)".format(time.ctime(), tsvFileName + ".ANN", rowAdded))
    logging.info(message3)

def rowIsValidForMerge(row):
    return rowIsHg38(row) and getFromRow(row, "chromosome") and getFromRow(row, "seq_start_position")


def rowIsHg38(row):
    hg38Regex = "(?i)(hg38|GRCh38|38)"
    return re.match(hg38Regex, getFromRow(row, "genome_assembly"))


def mergeRows(row, annoReader, rowNum):
    annoRows = compareKeysOfFileAndReturnMatchingRows(row, annoReader, rowNum)
    if len(annoRows) == 0:
        builtRow = pa.Series()
    else:
        twoMatchingRows = AnnotationFilter.run(annoRows, tsvFileName, parentDirectory)
        builtRow = buildFinalTemplate(twoMatchingRows, row, rowNum)
    return builtRow


def compareKeysOfFileAndReturnMatchingRows(row, annoReader, rowNum):
    annotationKey = createAnnotationKey(row)
    resultdf = annoReader[annoReader['#Uploaded_variation'] == annotationKey]
    if len(resultdf) == 0:
        logMissedPosition(row, annotationKey)
    return resultdf

def createAnnotationKey(row):
    return "{}_{}_{}_{}".format(vcfUtilities.formatChromo(row["chromosome"]),
                                row["seq_start_position"], row["ref_allele"], row["alt_allele"])

def extraColumnToJSON(extra):
    if extra:
        semiToComma = re.sub(';', '","', extra)
        equalsToColon = re.sub("=", '":"', semiToComma)
        addCurlyToStart = re.sub('(?m)^', '{"', equalsToColon)
        JSONstr = re.sub('(?m)$', '"}', addCurlyToStart)
        extraJson = json.loads(JSONstr) if extra != "" else pa.Series()
    else:
        extraJson = pa.Series()
    return extraJson


def buildHeaders():
    return ["model_id", "sample_id", "sample_origin", "host_strain_nomenclature", "passage", "symbol", "biotype",
            "coding_sequence_change",
            "variant_class", "codon_change", "amino_acid_change", "consequence", "functional_prediction", "read_depth",
            "allele_frequency",
            "chromosome", "seq_start_position", "ref_allele", "alt_allele", "ucsc_gene_id", "ncbi_gene_id",
            "ncbi_transcript_id", "ensembl_gene_id",
            "ensembl_transcript_id", "variation_id", "genome_assembly", "platform"]


def parseFilteredRows(twoMatchingRows):
    annoRow = pa.DataFrame()
    NCBIrow = pa.DataFrame()
    if len(twoMatchingRows) > 1:
        annoRow = twoMatchingRows.iloc[0]
        NCBIrow = twoMatchingRows.iloc[1]
    elif len(twoMatchingRows) == 1:
        annoRow = twoMatchingRows.iloc[0]
    return [annoRow, NCBIrow]


def isEnsemblData(row):
    geneId = getFromRow(row, 'Gene')
    transcriptId = getFromRow(row, 'Feature')
    return re.match("ENS", geneId) and re.match("ENS", transcriptId) if (geneId and transcriptId) else False


def buildFinalTemplate(twoMatchingRows, row, rowNum):
    ncbiRow = pa.DataFrame()
    builtRow = []

    if len(twoMatchingRows) > 0:
        parsedRows = parseFilteredRows(twoMatchingRows)
        if parsedRows[0].size > 0 :
            annoRow = parsedRows[0]
            if parsedRows[1].size > 0 and not isEnsemblData(parsedRows[1]):
                ncbiRow = parsedRows[1]
            extra = getFromRow(annoRow, 'Extra')
            if extra is None:
                extra = ""
                logging.info("Extra Column not found for row")
            annotationExtras = extraColumnToJSON(extra)
            builtRow = buildRow(row, annoRow, annotationExtras, ncbiRow)
        else:
            logging.debug("Info: Row Number {2}: Annotations not valid. Possibly no ENSEMBL accession. Queried annotations:  {0} \n {1}"
                          .format(parsedRows[0], parsedRows[1], rowNum))
    if len(builtRow) == 0:
        logging.info("Info: Row Number {0}: No annotations found for row with values : {1}".format(rowNum, row.values()))
        builtRow = list()
    return builtRow

def buildRow(row, annoRow, extraAnno, ncbiRow):
    return [getEitherFromRow(row, 'model_id', 'Model_ID'), getEitherFromRow(row, 'sample_id', 'Sample_ID'),
                        getFromRow(row, 'sample_origin'),
                        getEitherFromRow(row, 'host_strain_nomenclature', 'host strain nomenclature'),
                        getEitherFromRow(row, 'passage', 'Passage'), getFromRow(extraAnno, 'SYMBOL', ),
                        getFromRow(extraAnno, 'BIOTYPE'), parseHGSVc(getFromRow(extraAnno, 'HGVSc')),
                        getFromRow(extraAnno, 'VARIANT_CLASS'), getFromRow(annoRow, 'Codons'),
                        buildAminoAcidChange(getFromRow(annoRow, 'Amino_acids'),
                                             getFromRow(annoRow, 'Protein_position')),
                        getFromRow(annoRow, 'Consequence'),
                        parseFunctionalPredictions(getFromRow(extraAnno, 'PolyPhen'), getFromRow(extraAnno, 'SIFT')),
                        getFromRow(row, 'read_depth'), getEitherFromRow(row, 'Allele_frequency', 'allele_frequency'),
                        getFromRow(row, 'chromosome'),
                        getFromRow(row, 'seq_start_position'),
                        getFromRow(row, 'ref_allele'), getFromRow(row, 'alt_allele'), getFromRow(row, 'ucsc_gene_id'),
                        getFromRow(ncbiRow, 'Gene'),
                        getFromRow(ncbiRow, 'Feature'), getFromRow(annoRow, 'Gene'),
                        getFromRow(annoRow, 'Feature'),
                        getFromRow(annoRow, 'Existing_variation'),
                        getFromRow(row, 'genome_assembly'), getEitherFromRow(row, 'platform', 'Platform')]

def getEitherFromRow(row, attributeId, alternativeId):
    returnStr = getFromRow(row, attributeId)
    if not returnStr or returnStr == "":
        returnStr = getFromRow(row, alternativeId)
    return returnStr

def getFromRow(row, attributeID):
    returnStr = ""
    attribute = str(row.get(attributeID))
    attributeIsStrOrUnicode = (type(attribute) == str or type(attributeID) == unicode)
    if attribute and attributeIsStrOrUnicode:
        returnStr = row.get(attributeID)
    return returnStr

def parseHGSVc(HGSV):
    regexToRemoveAccession = "(?m)c\\.(.+$)"
    hgsvMatch = re.findall(regexToRemoveAccession, str(HGSV))
    return hgsvMatch[0] if len(hgsvMatch) > 0 else ""


def buildAminoAcidChange(aminoAcids, protienPosition):
    return aminoAcids[0] + protienPosition + aminoAcids[2] if (aminoAcids and protienPosition and
                                                               len(
                                                                   aminoAcids) == 3) else ""

def parseFunctionalPredictions(polyphen, sift):
    return "PolyPhen: {0} | SIFT: {1}".format(polyphen, sift) if (polyphen and sift) else ""


def isColumnHeader(line):
    return ((line[0] == '#') and (line[1] != '#'))


def isCanonical(line):
    return (line.find("CANONICAL=YES") != -1)


def logMissedPosition(row, chrStartPosKey):
    global mergedPointsMissed
    mergedPointsMissed += 1

    message = "Total dropped: {0} could not find {1} in annotations. Ref: {2} Alt {3} for sample {4}".format(
        mergedPointsMissed,
        chrStartPosKey,
        getFromRow(row, "ref_allele"),
        getFromRow(row, 'alt_allele'), getEitherFromRow(row, 'sample_id', 'Sample_ID'))
    logging.warning(message)


if len(sys.argv) > 1:
    run()