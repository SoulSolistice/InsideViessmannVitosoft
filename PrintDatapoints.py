#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from xml.etree import ElementTree as etree
import pprint
import sys

pp = pprint.PrettyPrinter(width=200,compact=True)

# This path needs to be adjusted to point to a directory for all XML files
DATAPATH = "../data/"

def _strip_namespaces(root):
	# Remove XML namespaces in-place so element tags become bare local names
	# ('{urn:...}ControllerType' -> 'ControllerType'). Harmless on files that
	# carry no namespace; keeps the tag comparisons below working if a future
	# Vitosoft export wraps this file in a namespace.
	for elem in root.iter():
		if isinstance(elem.tag, str) and elem.tag.startswith('{'):
			elem.tag = elem.tag.split('}', 1)[1]
	return root

def print_allDataPoints():
	# print supported Optolink systems (at least remove all MBus, LON, etc ones)
	evnDataPointTypes = {}
	def parse_ecnDataPointType():
		root = _strip_namespaces(etree.parse(DATAPATH + "ecnDataPointType.xml").getroot())
		for nodes in root:
			dataPointType = {}
			for cell in nodes:
				value = cell.text
				if cell.tag in ['Description','EventOptimisationExceptionList','EventOptimisation','Options','ErrorType']:
					continue
				if cell.tag in ['ControllerType','ErrorType','EventOptimisation']:
					value = int(value)
					if cell.tag in ['EventOptimisation']:
						value = value != 0
				dataPointType[cell.tag] = value
			ID = dataPointType['ID'].strip()
			if len(ID)==0:
				continue
			del dataPointType['ID']
			evnDataPointTypes[ID] = dataPointType
	parse_ecnDataPointType()

	# print it in a readable form
	lines = []
	for ID,dataPointType in evnDataPointTypes.items():
		if 'Identification' not in dataPointType:
			continue
		if not dataPointType['Identification'].startswith('20'): # ignore non-heating systems
			continue
		if 'IdentificationExtension' in dataPointType and len(dataPointType['IdentificationExtension'])!=4:
			continue
		idStr = 'ecnsysDeviceIdent:' + dataPointType['Identification']
		if 'IdentificationExtension' in dataPointType:
			idStr += ' sysHardware/SoftwareIndexIdent:' + dataPointType['IdentificationExtension']
			if 'IdentificationExtensionTill' in dataPointType:
				idStr += '-' + dataPointType['IdentificationExtensionTill']
		if 'F0' in dataPointType:
			idStr += ' ecnsysDeviceIdentF0:' + dataPointType['F0']
			if 'F0Till' in dataPointType:
				idStr += '-' + dataPointType['F0Till']
		lines.append('%s : %s' % (idStr,ID))
	lines.sort()
	for l in lines:
		print(l)

if __name__ == "__main__":
	print_allDataPoints()
