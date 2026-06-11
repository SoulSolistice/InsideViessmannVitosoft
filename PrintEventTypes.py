from xml.etree import ElementTree as etree


# This path needs to be adjusted to point to a directory for all XML files
DATAPATH = "../data/"

def _localname(tag):
	# Strip any XML namespace from a tag: '{ns}Name' -> 'Name'
	if isinstance(tag, str) and tag.startswith('{'):
		return tag.split('}', 1)[1]
	return tag

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
			textList[attrib['Label']] = attrib['Value']

def parse_ecnEventType():
	root = etree.parse(DATAPATH + "ecnEventType.xml").getroot()
	for xmlEvent in root.findall("EventType"):
		event = {}
		for cell in xmlEvent:
			event[cell.tag] = cell.text
		if 'Address' in event:
			IDstr = event['ID'].split('~')[0]
			if 'viessmann.eventtype.name.' + IDstr in textList:
				IDstr = textList['viessmann.eventtype.name.' + IDstr]
			border = ''
			if 'Conversion' in event and event['Conversion'] != 'NoConversion':
				if event['Conversion'] == 'Div10':
					border += '/10'
				elif event['Conversion'] == 'Div100':
					border += '/100'
				elif event['Conversion'] == 'Div1000':
					border += '/1000'
				elif event['Conversion'] == 'Div2':
					border += '/2'
				elif event['Conversion'] == 'Mult2':
					border += '*2'
				elif event['Conversion'] == 'Mult5':
					border += '*5'
				elif event['Conversion'] == 'Mult10':
					border += '*10'
				elif event['Conversion'] == 'Mult100':
					border += '*100'
				elif event['Conversion'] == 'MultOffset':
					if 'ConversionFactor' in event and event['ConversionFactor'] != '0':
						border += '*%s' % event['ConversionFactor']
					if 'ConversionOffset' in event and event['ConversionOffset'] != '0':
						border += '+%s' % event['ConversionOffset']
				elif event['Conversion'] == 'DateBCD':
					border += 'DateBCD(Y1Y2.MM.DD HH.MM.SS)'
				elif event['Conversion'] == 'DateMBus':
					border += 'NOTIMPL: %s' % event['Conversion']
				elif event['Conversion'] == 'DatenpunktADDR':
					border += 'NOTIMPL: %s' % event['Conversion']
				elif event['Conversion'] == 'DateTimeBCD':
					border += 'DateTimeBCD(Y1Y2.MM.DD HH.MM.SS)'
				elif event['Conversion'] == 'DateTimeMBus':
					border += 'NOTIMPL: %s' % event['Conversion']
				elif event['Conversion'] == 'DateTimeVitocom':
					border += 'NOTIMPL: %s' % event['Conversion']
				elif event['Conversion'] == 'Estrich':
					border += 'NOTIMPL: %s' % event['Conversion']
				elif event['Conversion'] == 'HexByte2AsciiByte':
					border += 'HexByte2AsciiByte(..)'
				elif event['Conversion'] == 'HexByte2DecimalByte':
					border += 'HexByte2DecimalByte(..)'
				elif event['Conversion'] == 'HexToFloat':
					border += 'NOTIMPL: %s' % event['Conversion']
				elif event['Conversion'] == 'HourDiffSec2Hour':
					border += 'NOTIMPL: %s' % event['Conversion']
				elif event['Conversion'] == 'IPAddress':
					border += 'IPAddress(a,b,c,d)'
				elif event['Conversion'] == 'Kesselfolge':
					border += 'NOTIMPL: %s' % event['Conversion']
				elif event['Conversion'] == 'MultOffsetBCD':
					border += 'BCD(11223344):'
					if 'ConversionFactor' in event and event['ConversionFactor'] != '0':
						border += '*%s' % event['ConversionFactor']
					if 'ConversionOffset' in event and event['ConversionOffset'] != '0':
						border += '+%s' % event['ConversionOffset']
				elif event['Conversion'] == 'MultOffsetFloat':
					border += 'NOTIMPL: %s' % event['Conversion']
				elif event['Conversion'] == 'Phone2BCD':
					border += 'Phone2BCD(..)'
				elif event['Conversion'] == 'RotateBytes':
					border += 'RotateBytes(..)'
				elif event['Conversion'] == 'Sec2Hour':
					border += 'Sec2Hour(/3600.0)'
				elif event['Conversion'] == 'Sec2Minute':
					border += 'Sec2Minute(/60.0)'
				elif event['Conversion'] == 'Sec2Day':
					border += 'Sec2Day(/86400.0)'
				elif event['Conversion'] == 'Sec2Week':
					border += 'Sec2Week(/604800.0)'
				elif event['Conversion'] == 'Sec2Month':
					border += 'NOTIMPL: %s' % event['Conversion']
				elif event['Conversion'] == 'Time53':
					border += 'Time53(hh:mm)'
				elif event['Conversion'] == 'UTCDiff2Hour':
					border += 'NOTIMPL: %s' % event['Conversion']
				elif event['Conversion'] == 'UTCDiff2Day':
					border += 'NOTIMPL: %s' % event['Conversion']
				elif event['Conversion'] == 'UTCDiff2Month':
					border += 'NOTIMPL: %s' % event['Conversion']
				elif event['Conversion'] == 'Convert4BytesToFloat':
					border += 'Convert4BytesToFloat(IEEE754)'
				elif event['Conversion'] == 'Steuerzeichen':
					border += 'NOTIMPL: %s' % event['Conversion']
				elif event['Conversion'] == 'ImpulszaehlerV300FA2':
					border += 'NOTIMPL: %s' % event['Conversion']
				elif event['Conversion'] == 'Vitocom300SGEinrichtenKanalLON':
					border += 'NOTIMPL: %s' % event['Conversion']
				elif event['Conversion'] == 'Vitocom300SGEinrichtenKanalMBUS':
					border += 'NOTIMPL: %s' % event['Conversion']
				elif event['Conversion'] == 'Vitocom300SGEinrichtenKanalWILO':
					border += 'NOTIMPL: %s' % event['Conversion']
				elif event['Conversion'] == 'Vitocom3NV':
					border += 'NOTIMPL: %s' % event['Conversion']
				elif event['Conversion'] == 'VitocomEingang':
					border += 'NOTIMPL: %s' % event['Conversion']
				elif event['Conversion'] == 'VitocomNV':
					border += 'NOTIMPL: %s' % event['Conversion']
				elif event['Conversion'] == 'FixedStringTerminalZeroes':
					border += 'FixedStringTerminalZeroes(str)'
				elif event['Conversion'] == 'HexByte2UTF16Byte':
					border += 'HexByte2UTF16Byte()'
				elif event['Conversion'] == 'HexByte2Version':
					border += 'HexByte2Version()'
				elif event['Conversion'] == 'BinaryToJson':
					border += 'BinaryToJson()'
				elif event['Conversion'] == 'DayMonthBCD':
					border += 'DayMonthBCD()'
				elif event['Conversion'] == 'LastBurnerCheck':
					border += 'LastBurnerCheck()'
				elif event['Conversion'] == 'LastCheckInterval':
					border += 'LastCheckInterval()'
				elif event['Conversion'] == 'DayToDate':
					border += 'DayToDate(..)' # up to 8 bytes offset to 1.1.1970
				else:
					border += '#### %s' % event['Conversion']
			if len(border)==0:
				border = '*1'
			if 'LowerBorder' in event:
				border += ' %s' % (event['LowerBorder'])
			if 'UpperBorder' in event:
				border += '-%s' % (event['UpperBorder'])
			elif 'LowerBorder' in event:
				border += '-?'
			if 'Stepping' in event:
				border += ':%s' % event['Stepping']
			parameter = ''
			if 'Parameter' in event:
				parameter += '%s/%s' % (event['Parameter'],event['BlockLength'])
			parameter += ' Byte:%s/%s' % (event['BytePosition'],event['ByteLength'])
			if event['BitLength'] != '0':
				parameter += ' Bit:%s/%s' % (event['BitPosition'],event['BitLength'])
			print('%6s %s %s %s --- %s' % (event['Address'],event['FCRead'],border,parameter,IDstr))

if __name__ == "__main__":
	parse_Textresource('de') # load english localization, 'de' is German
	parse_ecnEventType();
