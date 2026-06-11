#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from xml.etree import ElementTree as etree
import pprint
import sys
import binascii
import re

pp = pprint.PrettyPrinter(width=200,compact=True)

# This path needs to be adjusted to point to a directory for all XML files
DATAPATH = "../data/"

MAX_STR_LENGTH = 1000 # certain strings (e.g. conditions) can be very long. This shortens them. 1000 matches "print everything"

def _localname(tag):
	# Strip any XML namespace from a tag: '{ns}Name' -> 'Name'
	if isinstance(tag, str) and tag.startswith('{'):
		return tag.split('}', 1)[1]
	return tag

def _strip_namespaces(root):
	# Remove XML namespaces in-place so element tags become bare local names
	# ('{urn:...}ecnEventType' -> 'ecnEventType'). This lets the rest of the
	# parser match plain tag names regardless of the namespaces Vitosoft emits.
	for elem in root.iter():
		if isinstance(elem.tag, str) and elem.tag.startswith('{'):
			elem.tag = elem.tag.split('}', 1)[1]
	return root

textList = {}
def parse_Textresource(lang):
	# Newer Vitosoft exports ship a single 'Textresource.xml' containing ALL
	# languages, discriminated by a 'CultureId' attribute, instead of one
	# 'Textresource_<lang>.xml' per language. Support the new single-file
	# layout and fall back to the legacy per-language file.
	import os
	singleFile = DATAPATH + "Textresource.xml"
	legacyFile = DATAPATH + "Textresource_%s.xml" % lang
	path = singleFile if os.path.exists(singleFile) else legacyFile
	root = etree.parse(path).getroot()

	# Resolve the requested language name (e.g. 'de') to its CultureId by
	# reading the <Cultures> table. Legacy single-language files have no
	# <Cultures> section, in which case we do not filter.
	cultureId = None
	hasCultures = False
	for section in root:
		if _localname(section.tag) == 'Cultures':
			hasCultures = True
			for culture in section:
				if culture.attrib.get('Name') == lang:
					cultureId = culture.attrib.get('Id')
			break
	if hasCultures and cultureId is None:
		available = []
		for section in root:
			if _localname(section.tag) == 'Cultures':
				available = [c.attrib.get('Name') for c in section]
		raise ValueError("Language %r not found in %s. Available: %s"
						 % (lang, path, ', '.join(filter(None, available))))

	for section in root:
		if _localname(section.tag) != 'TextResources':
			continue
		for textNode in section:
			attrib = textNode.attrib
			if 'Label' not in attrib or 'Value' not in attrib:
				continue
			# In the consolidated file keep only rows for the requested culture.
			if cultureId is not None and attrib.get('CultureId') not in (None, cultureId):
				continue
			textList[attrib['Label']] = attrib['Value'].replace('##ecnnewline##','\\n').replace('##ecntab##','\\t')

def translate(node,key):
	if key in node and node[key] and node[key].startswith('@@'):
		if node[key][2:] in textList and len(node[key][2:]):
			node[key] = textList[node[key][2:]]

def _readable(label):
	# Fallback for labels that translate() could not resolve. The 2026 export
	# references display names via '@@viessmann.<type>.name.<TECH>' (and similar)
	# but ships none of those strings in Textresource.xml, so the labels arrive
	# unresolved. Recover the underlying technical name instead of printing the
	# raw '@@...' label. Resolved (already-translated) values pass through.
	if not isinstance(label, str) or not label.startswith('@@'):
		return label
	s = label[2:]
	if '.name.' in s:                       # ...eventtype.name.Outside_Temp -> Outside_Temp
		return s.split('.name.', 1)[1]
	parts = s.split('.')                    # ...eventvaluetype.K52_KonfiWeiche~0 -> K52_KonfiWeiche~0
	if len(parts) >= 3 and parts[0] in ('viessmann', 'econtrolnet'):
		return '.'.join(parts[2:])
	return s

def _friendly(label):
	# Friendly (human) name for an entity. Strategy: if 'label' resolved to a
	# real translation (anything not still starting with '@@'), use it verbatim.
	# Otherwise derive one from the technical identifier by turning '_' into
	# spaces. This is a deliberately light touch -- it cleans snake_case names
	# (Outside_Temp -> "Outside Temp") but leaves Viessmann's camelCase/coding
	# compounds (K00_..., ...A1M1) largely as-is; a real translation source is
	# still preferable where clean labels matter. The technical id is always
	# carried separately (see the bracketed [address]/[id] in the output).
	if isinstance(label, str) and label and not label.startswith('@@'):
		return label
	return _readable(label).replace('_', ' ').strip()

def parse_node(dataRoots,nodeName):
	# 'dataRoots' is the list of <ECNDataSet> diffgram elements; the rows we
	# want are their direct children. (Originally this searched the entire
	# document with './/', which also reached other datasets and the schema.)
	elements = []
	matches = []
	for dataRoot in dataRoots:
		matches.extend(dataRoot.findall(nodeName))
	for xmlEvent in matches:
		dp = {}
		for cell in xmlEvent:
			if cell.tag in ['Description','URL','DefaultValue','Filtercriterion','Reportingcriterion','Priority']:
				continue
			if cell.tag in ['Conversion','EnumType']: # these are not needed
				continue
			value = cell.text
			if value == 'true':
				value = True
			elif value == 'false':
				value = False
			if cell.tag in ['ConverterId','Id','Type','ConfigSetId','EventValueId','EnumAddressValue','StatusTypeId','EventTypeValueCondition','EventTypeIdCondition','ConditionGroupId','EventTypeGroupIdDest','EventTypeIdDest','EventTypeId','EventTypeGroupId','DataPointTypeId','DeviceTypeId','DataPointTypeId','OrderIndex','EventTypeOrder','ParentId','StatusDataPointTypeId','TechnicalIdentificationAddress','SortOrder']:
				value = int(value)
			if cell.tag == 'ParentId' and value == -1:
				continue
			dp[cell.tag] = value
			if cell.tag in ['Description','Name','EnumReplaceValue']:
				translate(dp,cell.tag)
		elements.append(dp)
	return elements

ecnEventTypes = {}
def parse_ecnEventTypes():
	for nodes in etree.parse(DATAPATH + "ecnEventType.xml").getroot():
		eventType = {}
		for cell in nodes:
			if cell.tag in []:
				continue
			value = cell.text
			if cell.tag == 'ValueList':
				valueDict = {}
				for valueEnum in value.split(';'):
					valueEnumVal,valueEnumStr = valueEnum.split('=', 1)
					if valueEnumStr.startswith('@@'):
						if valueEnumStr[2:] in textList and len(valueEnumStr[2:]):
							valueEnumStr = textList[valueEnumStr[2:]]
					try:
						valueEnumVal = int(valueEnumVal)
					except:
						pass
					valueDict[valueEnumVal] = valueEnumStr
				value = valueDict
			if value == 'true':
				value = True
			elif value == 'false':
				value = False
			elif cell.tag in ['BitLength', 'BitPosition', 'BlockLength', 'ByteLength', 'BytePosition', 'RPCHandler', 'MappingType']:
				try:
					value = int(value)
				except:
					pass
			elif cell.tag in ['ConversionFactor', 'Stepping', 'UpperBorder', 'LowerBorder']:
				try:
					value = float(value)
				except:
					pass
#			elif cell.tag in ['PrefixRead', 'PrefixWrite', 'ALZ'] and value:
#				if value.startswith('0x'):
#					value = value[2:]
#				value = binascii.unhexlify(value)
			eventType[cell.tag] = value
			if cell.tag in ['Description']:
				translate(eventType,cell.tag)
			if cell.tag in []:#['Unit']:
				if eventType[cell.tag] in textList and len(eventType[cell.tag]):
					eventType[cell.tag] = textList[eventType[cell.tag]]
		eventID = eventType['ID']
		del eventType['ID']
		if 'Conversion' in eventType:
			if eventType['Conversion'] == 'NoConversion':
				del eventType['Conversion']
				if 'ConversionFactor' in eventType:
					del eventType['ConversionFactor']
				if 'ConversionOffset' in eventType:
					del eventType['ConversionOffset']
		if 'FCRead' in eventType and eventType['FCRead'] == 'undefined':
			eventType['FCRead'] = None
		if 'FCWrite' in eventType and eventType['FCWrite'] == 'undefined':
			eventType['FCWrite'] = None
		if 'OptionList' in eventType:
			eventType['OptionList'] = eventType['OptionList'].split(';')
		ecnEventTypes[eventID] = eventType

usedEventTypes = set()
def eventTypeDescr(eventID):
	if eventID not in ecnEventTypes:
		return eventID
	usedEventTypes.add(eventID)
	et = ecnEventTypes[eventID]
	result = eventID
	#cmd = et['FCRead']
	#if cmd == 'Virtual_READ':
	#	cmd = 'VR'
	#elif cmd == 'Virtual_WRITE':
	#	cmd = 'VW'
	#result += ': ' + cmd
	#result += ':' + et['Address']
	#if et['BlockLength'] == et['ByteLength']:
	#	result += ':%d' % et['BlockLength']
	#else:
	#	result += ':%d' % et['ByteLength']
	result += ' (%s)' % et['Parameter']
	return result

def parse_DPDefinitions(selectedDatapointTypeAddress):
	classes = set()
	# Parse the file directly so ElementTree honours the XML declaration's
	# encoding (newer exports are UTF-8, older ones UTF-16) and so we avoid
	# reading a ~200 MB file into a string just to run a regex over it.
	tree = etree.parse(DATAPATH + "DPDefinitions.xml")
	root = _strip_namespaces(tree.getroot())

	# The container ('ImportExportDataHolder') holds one or more datasets, each
	# serialised as an inline <xs:schema> followed by a <diffgram>. We only want
	# the rows of the 'ECNDataSet' dataset and must ignore any others (e.g.
	# 'DocumentServerDataSet'). Collect every ECNDataSet payload root.
	dataRoots = []
	for diffgram in root.iter('diffgram'):
		for child in diffgram:
			if child.tag == 'ECNDataSet':
				dataRoots.append(child)
	if not dataRoots:
		raise RuntimeError("No <ECNDataSet> diffgram found in DPDefinitions.xml - "
						   "the export structure may have changed.")

	for dataRoot in dataRoots:
		for xmlEvent in dataRoot:
			classes.add(xmlEvent.tag)

	nodeListe = {}
	for cl in classes:
		nodes = parse_node(dataRoots,cl)
		if True:
			if cl == 'ecnEventValueType':
				for dd in nodes:
					st = int(dd['StatusTypeId'])
					if st == 5:
						dd['StatusTypeId'] = '@@viessmann.vitodata.valuestatus.notevaluate'
					elif st == 4:
						dd['StatusTypeId'] = '@@viessmann.vitodata.valuestatus.outofinterval'
					elif st == 3:
						dd['StatusTypeId'] = 'Error'
					elif st == 2:
						dd['StatusTypeId'] = 'Warning'
					elif st == 1:
						dd['StatusTypeId'] = 'OK'
					elif st == 0:
						dd['StatusTypeId'] = 'Undefined'
					else:
						dd['StatusTypeId'] = '???'
			if len(nodes) > 0 and 'Id' in nodes[0]:
				dd = {}
				for e in nodes:
					foundId = e['Id']
					del e['Id']
					dd[foundId] = e
				nodes = dd
		nodeListe[cl] = nodes
		if cl in [ 'ecnVersion',
				   'ecnDeviceType',
				   'ecnStatusType',
				   'ecnDatapointType','ecnDeviceTypeDataPointTypeLink',
				   'ecnEventType','ecnDataPointTypeEventTypeLink',
				   'ecnTableExtension','ecnTableExtensionValue',
				   'ecnEventValueType','ecnEventTypeEventValueTypeLink',
				   'ecnEventTypeGroup','ecnEventTypeEventTypeGroupLink',
				   'ecnConverter','ecnConverterDeviceTypeLink','ecnCulture',
				    ]:
#				   'ecnConfigSet','ecnStatusType','ecnConfigSetParameter']:
#			continue
			pass
		if False and cl == 'ecnDisplayConditionGroup':
			print(cl, len(nodeListe[cl]), type(nodeListe[cl]))
			for node in nodeListe:
				if isinstance(nodeListe[cl], list): 
					pp.pprint(nodeListe[cl])
				elif isinstance(nodeListe[cl], dict): 
					pp.pprint(nodeListe[cl])
			print('-' * 40)
	#			break
			#sys.exit(0)
			pass

	usedConditionEventTypeIds = set()
	def getCondStr(groupId,groupOrEvent='EventTypeGroupIdDest'):
		condDict = { 0:'=', 1:'≠', 2:'>', 3:'≥', 4:'<', 5:'≤' }
		operDict = { 1:'AND', 2:'OR' }
		shortName = { # to avoid the conditions get incredibly long, we shorten some known common events
					'(00) Heizkreis-Warmwasserschema':'00_WWS',
					'(54) Solarregelung':'54_SR',
					'(7F) Unterscheidung Einfamilienhaus - Mehrparteienhaus':'7F_EFH',
					'Software-Index des Gerätes':'SWIdx',
					'SW-Index Solarmodul SM1':'SWIdxSolarSM1',
					'HW-Index Solarmodul SM1':'HWIdxSolarSM1',
					'(00) Anlagen-Warmwasserschema':'00_AnlWWS',
					'(76) Konfiguration Kommunikationsmodul':'76_KonfKommMod',
					'(76) Kommunikationsmodul':'76_KommMod',
					'(A0) Kennung Fernbedienung A1M1':'A0_KennFBA1M1',
					'(A0) Kennung Fernbedienung M2':'A0_KennFBM2',
					'(A0) Kennung Fernbedienung M3':'A0_KennFBM3',
					'Fernbedienung Heizkreis A1M1':'FBA1M1',
					'Fernbedienung Heizkreis M2':'FBM2',
					'Fernbedienung Heizkreis M3':'FBM3',
					'(E5) Kennung Pumpe Heizkreis A1':'E5_KennPumpHzkA1',
					'(E5) Kennung Pumpe Heizkreis M2':'E5_KennPumpHzkM2',
					'(E5) Kennung Pumpe Heizkreis M3':'E5_KennPumpHzkM3',
					'Status Raumtemp.-Sensor HK1':'RaumTempSensHK1',
					'Status Raumtemp.-Sensor HK2':'RaumTempSensHK2',
					'Status Raumtemp.-Sensor HK3':'RaumTempSensHK3',
					'(30) Kennung Interne Umwälzpumpe':'30_KennIntUmwPumpe',
					'(91) Zuordnung externe Betriebsarten-umschaltung':'ZuordExtBetrUmsch',
					'(35) Kennung Anschlusserweiterung EA1':'35_KennAnschlErwEA1',
					'(5B) Kennung Anschlusserweiterung EA1':'5B_KennAnschlErwEA1',
					'(32) Kennung Anschlusserweiterung AM1':'32_KennAnschlErwAM1',
					}

		groupCond = ''
		for displayConditionGroupId,displayConditionGroup in nodeListe['ecnDisplayConditionGroup'].items():
			if displayConditionGroup[groupOrEvent] != groupId:
				continue
			ll = []
			for dispCondId,dispCond in nodeListe['ecnDisplayCondition'].items():
				if dispCond['ConditionGroupId'] != displayConditionGroupId:
					continue
				eventTypeId = int(dispCond['EventTypeIdCondition'])
				usedConditionEventTypeIds.add(eventTypeId)
				eventType = nodeListe['ecnEventType'][eventTypeId]
				name = _readable(eventType['Name']).strip()
				if name in shortName:
					name = shortName[name]
				else:
					name = '"%s"' % name
				#name += ' (%d)' % (eventTypeId)
				condInt = int(dispCond['Condition'])
				# Per VitosoftXML.md: for Condition >= 2 (>, >=, <, <=) the comparison
				# value is the literal 'ConditionValue'; only Equal/NotEqual (0/1)
				# compare against the 'EventTypeValueCondition' enum value.
				if condInt >= 2:
					val = '%s' % dispCond.get('ConditionValue', '?')
				else:
					eventValue = nodeListe['ecnEventValueType'][int(dispCond['EventTypeValueCondition'])]
					if 'EnumReplaceValue' in eventValue:
						val = '"%s"' % _readable(eventValue['EnumReplaceValue'])
					elif 'EnumAddressValue' in eventValue:
						val = '"%s"' % _readable(eventValue['EnumAddressValue'])
					else:
						val = '"%s"' % _readable(eventValue.get('Name', '?'))
				ll.append(name + condDict[condInt] + val)
			groupCond += (' ' + operDict[displayConditionGroup['Type']] + ' ').join(ll)
		if groupCond:
			return ' HIDDEN:(%s)' % groupCond
		return ''

	# find datapoint for a given address
	for datapointTypeId,datapointType in nodeListe['ecnDatapointType'].items():
		if datapointType['Address'] != selectedDatapointTypeAddress:
			continue
		print(datapointType['Name'])
		print('=' * len(datapointType['Name']))
		break

	# find all event IDs for a given data datapoint ID
	eventTypeIds = set()
	for dataPointTypeEventTypeLink in nodeListe['ecnDataPointTypeEventTypeLink']:
		if dataPointTypeEventTypeLink['DataPointTypeId'] != datapointTypeId:
			continue
		eventTypeIds.add(dataPointTypeEventTypeLink['EventTypeId'])

	usedGroups = {}
	for eventTypeId in eventTypeIds:
		eventType = nodeListe['ecnEventType'][eventTypeId].copy()
		eventType['Id'] = eventTypeId
		eventTypeAddress = eventType['Address']
		#del eventType['Address']
		if eventTypeAddress == 'DatabaseVersionForExport':
			continue
		if eventType['Name'] in ['ecnStatusEventType','ecnsysEventType~ErrorNotification']:
			continue
		if eventTypeAddress in ecnEventTypes and 'FCRead' in ecnEventTypes[eventTypeAddress]:
			eventType['FCRead'] = ecnEventTypes[eventTypeAddress]['FCRead']
			#if eventType['FCRead'] == 'Remote_Procedure_Call':
			#	continue
			pass
		else:
			continue # URL only event
		#if eventTypeAddress in ecnEventTypes and 'FCWrite' in ecnEventTypes[eventTypeAddress] and ecnEventTypes[eventTypeAddress]['FCWrite']:
		#	eventType['FCWrite'] = ecnEventTypes[eventTypeAddress]['FCWrite']
		del eventType['Type']

		# build a list of value types for an event type
		if True: # for enums there is a list of possible values
			evalueDict = {}
			evalueList = []
			for evl in nodeListe['ecnEventTypeEventValueTypeLink']:
				if evl['EventTypeId'] != eventTypeId:
					continue
				eventValueType = nodeListe['ecnEventValueType'][evl['EventValueId']]
				if 'Name' in eventValueType:
					del eventValueType['Name']
				if 'StatusTypeId' in eventValueType and eventValueType['StatusTypeId'] == 'Undefined':
					del eventValueType['StatusTypeId']
				if 'Unit' in eventValueType:
					if eventValueType['Unit'] == None:
						del eventValueType['Unit']
					elif eventValueType['Unit'].startswith('ecnUnit.'):
						eventValueType['Unit'] = eventValueType['Unit'][8:]
				if eventValueType['DataType'] == 'Int':
					if 'ValuePrecision' in eventValueType:
						eventValueType['ValuePrecision'] = int(eventValueType['ValuePrecision'])
					if 'LowerBorder' in eventValueType:
						eventValueType['LowerBorder'] = int(eventValueType['LowerBorder'])
					if 'UpperBorder' in eventValueType:
						eventValueType['UpperBorder'] = int(eventValueType['UpperBorder'])
					if 'Stepping' in eventValueType:
						eventValueType['Stepping'] = int(eventValueType['Stepping'])
						if eventValueType['Stepping'] == 1:
							del eventValueType['Stepping']
				elif eventValueType['DataType'] == 'Float':
					if 'LowerBorder' in eventValueType:
						eventValueType['LowerBorder'] = float(eventValueType['LowerBorder'])
					if 'UpperBorder' in eventValueType:
						eventValueType['UpperBorder'] = float(eventValueType['UpperBorder'])
					if 'Stepping' in eventValueType:
						eventValueType['Stepping'] = float(eventValueType['Stepping'])
						if eventValueType['Stepping'] == 1.0:
							del eventValueType['Stepping']
				elif eventValueType['DataType'] == 'DateTime':
					if 'ValuePrecision' in eventValueType:
						eventValueType['ValuePrecision'] = int(eventValueType['ValuePrecision'])
				elif eventValueType['DataType'] == 'Binary':
					if 'LowerBorder' in eventValueType:
						eventValueType['LowerBorder'] = float(eventValueType['LowerBorder'])
					if 'UpperBorder' in eventValueType:
						eventValueType['UpperBorder'] = float(eventValueType['UpperBorder'])
					if 'Stepping' in eventValueType:
						eventValueType['Stepping'] = float(eventValueType['Stepping'])
						if eventValueType['Stepping'] == 1.0:
							del eventValueType['Stepping']
#				else:
#					pp.pprint(eventValueType)
				if 'EnumAddressValue' in eventValueType and 'EnumReplaceValue' in eventValueType:
					evalueDict[int(eventValueType['EnumAddressValue'])] = eventValueType['EnumReplaceValue']
				else:
					if 'EnumAddressValue' in eventValueType:
						del eventValueType['EnumAddressValue']
					if 'EnumReplaceValue' in eventValueType:
						del eventValueType['EnumReplaceValue']
					evalueList.append(eventValueType)
			if len(evalueList):
				if len(evalueList)==1:
					eventType['_VALUE_'] = evalueList[0]
				else:
					eventType['_VALUE_'] = evalueList
			else:
				eventType['_VALUE_'] = evalueDict

		if True: # events can be in several groups
			foundGroup = False
			for eventTypeEventTypeGroupLink in nodeListe['ecnEventTypeEventTypeGroupLink']:
				if eventTypeEventTypeGroupLink['EventTypeId'] != eventTypeId:
					continue
				if eventTypeEventTypeGroupLink['EventTypeGroupId'] not in nodeListe['ecnEventTypeGroup']: # the DP is missing entries!
					continue
				etgOrder = eventTypeEventTypeGroupLink['EventTypeOrder']
				eventTypeGroup = nodeListe['ecnEventTypeGroup'][eventTypeEventTypeGroupLink['EventTypeGroupId']]
				if eventTypeGroup['DataPointTypeId'] == datapointTypeId:
					group = eventTypeGroup.copy()
					del group['EntrancePoint'] # always true
					if 'ParentId' in group:
						parent = nodeListe['ecnEventTypeGroup'][group['ParentId']].copy()
						del group['ParentId']
						del parent['DataPointTypeId']
						del parent['DeviceTypeId']
						pname = parent['Name']
						if pname in textList and len(pname):
							pname = textList[pname]
							parent['Name'] = pname
						group['Name'] = '%s - %s' % (pname, group['Name'])
					del group['DataPointTypeId']
					del group['DeviceTypeId']
					del group['OrderIndex']
					if eventTypeEventTypeGroupLink['EventTypeGroupId'] not in usedGroups:
						usedGroups[eventTypeEventTypeGroupLink['EventTypeGroupId']] = {}
					etgOrder *= 10
					while etgOrder in usedGroups[eventTypeEventTypeGroupLink['EventTypeGroupId']]:
						etgOrder += 1
					usedGroups[eventTypeEventTypeGroupLink['EventTypeGroupId']][etgOrder] = eventType
					foundGroup = True
			if not foundGroup:
				if '_NO_GROUP_' in usedGroups:
					usedGroups[0].append(eventType)
				else:
					usedGroups[0] = [eventType]

	# --- Print the datapoint's event groups as a tree -----------------------
	# Data extraction above is complete; everything below is presentation. The
	# 2026 export nests functional ("@@...") groups beneath top-level
	# "ecnsys..." UI-section groups, and some events sit directly in a group, so
	# the old fixed two-level printer (which also skipped every "ecnsys" parent)
	# emitted nothing. Print the real hierarchy at its natural depth and show any
	# group that itself, or transitively, carries events.
	groups = {}
	for gid, g in nodeListe['ecnEventTypeGroup'].items():
		if g.get('DataPointTypeId') == datapointTypeId:
			groups[gid] = g

	childrenOf = {}
	topLevel = []
	for gid, g in groups.items():
		pid = g.get('ParentId')
		if pid is None or pid not in groups:
			topLevel.append(gid)
		else:
			childrenOf.setdefault(pid, []).append(gid)

	def groupHasEvents(gid, seen=None):
		if seen is None:
			seen = set()
		if gid in seen:
			return False
		seen.add(gid)
		if gid in usedGroups and len(usedGroups[gid]):
			return True
		return any(groupHasEvents(c, seen) for c in childrenOf.get(gid, []))

	def groupName(g):
		n = g.get('Name', '')
		if n in textList and len(n):
			n = textList[n]
		return _friendly(n)

	def orderOf(gid):
		return groups[gid].get('OrderIndex', 0)

	def clip(s):
		if len(s) > MAX_STR_LENGTH:
			return s[:MAX_STR_LENGTH] + '\u2026)'
		return s

	def printGroup(gid, depth):
		g = groups[gid]
		indent = '    ' * depth
		bullet = '# ' if depth == 0 else '- '
		techId = g.get('Address') or _readable(g.get('Name', ''))
		print()
		print('%s%s%s (%d) [%s]%s' % (indent, bullet, groupName(g).strip(), gid, techId, clip(getCondStr(gid))))
		if gid in usedGroups and len(usedGroups[gid]):
			for kk in sorted(usedGroups[gid]):
				ev = usedGroups[gid][kk]
				line = _friendly(ev['Name']).strip() + ' (%d)' % ev['Id']
				line += ' [' + eventTypeDescr(ev['Address']) + ']'
				line += clip(getCondStr(ev['Id'], 'EventTypeIdDest'))
				print('%s    - %s' % (indent, line))
		for cid in sorted(childrenOf.get(gid, []), key=orderOf):
			if groupHasEvents(cid):
				printGroup(cid, depth + 1)

	for gid in sorted(topLevel, key=orderOf):
		if groupHasEvents(gid):
			printGroup(gid, 0)

		if False:
			print()
			for eventTypeId in sorted(usedConditionEventTypeIds):
				eventType = nodeListe['ecnEventType'][eventTypeId]
				name = eventType['Name'].strip()
				print('%s (%d) %s' % (name,eventTypeId,eventType['Address']))


if __name__ == "__main__":
	# print all events with their conditions, sorted by groups for a specific data point
	parse_Textresource('de') # load english localization, 'de' is German
	parse_ecnEventTypes()
	parse_DPDefinitions('VScotHO1_72')
	# 20cb 0351 0000 0146
