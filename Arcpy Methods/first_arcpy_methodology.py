import arcpy
from arcpy import env
import sets

arcpy.env.overwriteOutput = True

muniParam = arcpy.GetParameterAsText(0)
muniList = muniParam.split(';')
popMin = arcpy.GetParameterAsText(1)
outputWorkspace = arcpy.GetParameterAsText(2)

arcpy.env.workspace = outputWorkspace

# Dictionary used in the raw() method 
escape_dict={'\a':r'\a',
             '\b':r'\b',
             '\c':r'\c',
             '\f':r'\f',
             '\n':r'\n',
             '\r':r'\r',
             '\t':r'\t',
             '\v':r'\v',
             '\'':r'\'',
             '\"':r'\"'}

# Credit to Brett Cannon on code.ActiveState.com, slight modifications by myself.
def raw(text):
    # Returns a raw string representation of text and eliminates all special backslash characters
    new_string=''
    for char in text:
        try: 
            new_string += escape_dict[char]
        except KeyError: 
            new_string += char
    return new_string

# Function that returns an array of border lengths for the given municipality. Parameter
# is a municipal code String. 
def getAllBorders(munCode):
	cursor = arcpy.SearchCursor(polyAnalysis)
	lengths = []
	for r in cursor:
		if(r.getValue('src_MUN_CODE') == munCode):
			border = r.getValue('LENGTH')
			lengths.append(border)
	del cursor
	del r
	return lengths
	
# Returns the merger partner, based on the source municipality's municipal code and the 
# length of the border that the two municipality's share. Returns the merger partner's 
# municipal code String. 
def getFellowMerger(length, srcMunCode):
	cursor = arcpy.SearchCursor(polyAnalysis)
	mergerMunCode = '' 
	for r in cursor:
	
		# Towns with longest borders are both merger candidates
		if(r.getValue('src_MUN_CODE') == srcMunCode and r.getValue('LENGTH') == length and r.getValue('src_isCand') == 1 and r.getValue('nbr_isCand') == 1):
		   
			mergerMunCode = r.getValue('nbr_MUN_CODE')
		
		# Doughnut hole: small municipality merger candidate entirely within a non candidate. Merge them.
		elif(r.getValue('src_MUN_CODE') == srcMunCode and r.getValue('src_isCand') == 1 and r.getValue('nbr_isCand') == 0 and r.getValue('LENGTH') == length):
			
			mergerMunCode = r.getValue('nbr_MUN_CODE')
		
			
	return mergerMunCode
	del cursor, r

	
# Renames the name of field in a feature class. Needed due to the 'Alter Field' tool not being available prior to 10.2. Credit to Josh Werts for 
# this elegant solution at joshwerts.com 	
def rename_fields(table, out_table, new_name_by_old_name):
	""" Renames specified fields in input feature class/table 
	:table:                 input table (fc, table, layer, etc)
	:out_table:             output table (fc, table, layer, etc)
	:new_name_by_old_name:  {'old_field_name':'new_field_name',...}
	->  out_table
	"""
	existing_field_names = [field.name for field in arcpy.ListFields(table)]

	field_mappings = arcpy.FieldMappings()
	field_mappings.addTable(table)

	for old_field_name, new_field_name in new_name_by_old_name.iteritems():

		if(old_field_name not in existing_field_names):
			message = "Field: {0} not in {1}".format(old_field_name, table)

		else:
			mapping_index = field_mappings.findFieldMapIndex(old_field_name)
			field_map = field_mappings.fieldMappings[mapping_index]
			output_field = field_map.outputField
			output_field.name = new_field_name
			output_field.aliasName = new_field_name
			field_map.outputField = output_field
			field_mappings.replaceFieldMap(mapping_index, field_map)
			
	# use merge with single input just to use new field_mappings
	arcpy.Merge_management(table, out_table, field_mappings)
	return out_table
	

for muni in muniList:
	
	# Removing the file path from the name
	splitPath = raw(muni).split('\\')
	muniName = splitPath[len(splitPath) - 1]
	arcpy.AddMessage(muniName)
	
	cursor = arcpy.SearchCursor(muni)
	countyName = ''
	for row in cursor:
		countyName = row.getValue('COUNTY')
		break
	del row, cursor
	
	iteration = 1	
	mergeCount = 1	
	iterMergeCount = 1 
	lastJoinMerge = 0
	popReqMet = False
	while popReqMet == False:	
		
		thisIterationsMerges = 0
		# Getting the source municipality feature class. Checking to see if the isCand field exists.
		if(mergeCount > 1):
			arcpy.Rename_management('merge%s'%(mergeCount - 1), 'tempmerge%s'%(mergeCount - 1))
			newNameByOldName = {'%s_isCand'%(muniName) : 'isCand', '%s_MUN_CODE'%(muniName) : r'MUN_CODE', '%s_MUN'%(muniName) : 'MUN', '%s_POP2010'%(muniName) : 'POP2010', 'merge%s_MUN_CODE'%(lastJoinMerge) : 'MUN_CODE', 'merge%s_MUN'%(lastJoinMerge) : 'MUN', 'merge%s_POP2010'%(lastJoinMerge) : 'POP2010', 'merge%s_isCand'%(lastJoinMerge) : 'isCand'}
			if(iteration <= 2):
				arcpy.DeleteField_management('tempmerge%s'%(iterMergeCount - 1), ['%s_isCand'%(muniName), 'mergeKey_OBJECTID', 'mergeKey_MUN', 'mergeKey_BESTMERGE'])
			else:
				arcpy.DeleteField_management('tempmerge%s'%(mergeCount - 1), ['merge%s_isCand'%(lastJoinMerge), 'mergeKey_OBJECTID', 'mergeKey_MUN', 'mergeKey_BESTMERGE'])
			rename_fields('tempmerge%s'%(mergeCount - 1), 'merge%s'%(mergeCount - 1), newNameByOldName)
			NJmunis = 'merge%s'%(mergeCount - 1)
			arcpy.Delete_management('tempmerge%s'%(mergeCount - 1))
		else: 
			NJmunis = muni
		
		checkCursor = arcpy.SearchCursor(NJmunis)
		indPops = set()
		for checkRow in checkCursor:
			muniPop = checkRow.getValue('POP2010')
			indPops.add(muniPop)
		del checkRow, checkCursor
		
		popCounter = 0
		for pop in indPops:
			if(pop < int(popMin)):
				popCounter += 1
		if(popCounter == 0):
			popReqMet = True 
		if(iteration == 1):
			arcpy.AddMessage('%s Merge(s) Needed'%(str(popCounter)))
		else:
			arcpy.AddMessage('%s More Merge(s) Needed'%(str(popCounter)))
				
		NJmunis_fields = arcpy.ListFields(NJmunis)
		fieldName = [f.name for f in NJmunis_fields]
		if('isCand' not in fieldName):
			arcpy.AddField_management(NJmunis, 'isCand', 'LONG')
			
		code = """def isCand(pop):
			if(pop < %s):
				return 1
			else:
				return 0"""%(popMin)


		exp = 'isCand(!POP2010!)'
		arcpy.CalculateField_management(NJmunis, 'isCand', exp, 'PYTHON_9.3', code)

		# Executing the Polygon Neighbors tool and writing a new table to disk. 
		in_fields = [r'MUN_CODE', r'MUN', r'isCand']
		polyAnalysis = arcpy.PolygonNeighbors_analysis(NJmunis, 'poly_analysis', in_fields)

		# Adding all needed fields to the Polygon Neighbors table.
		if('CANDBORDERS' not in fieldName):
			arcpy.AddField_management(polyAnalysis, 'CANDBORDERS', 'LONG')
		if('BESTMERGE' not in fieldName):
			arcpy.AddField_management(polyAnalysis, 'BESTMERGE', 'TEXT')
			

		# Updating the new fields in the Polygon Neighbors table. 
		cursor = arcpy.UpdateCursor(polyAnalysis) 
		row = cursor.next()
		arcpy.AddMessage('Finding merge partners...')
		while row: 
			srcMunCode = row.getValue('src_MUN_CODE')
			borders = getAllBorders(srcMunCode)
			longestBorder = 0
			if(len(borders) > 1):
				longestBorder = max(borders)
			else:
				longestBorder = borders[0]
			row.setValue('BESTMERGE', getFellowMerger(longestBorder, srcMunCode))
			cursor.updateRow(row)
			row = cursor.next()
		del cursor
		del row

		# Creating a table that will contain merge candidates and their best partners.
		arcpy.AddMessage('Making key...')
		if(mergeCount > 1):
			arcpy.Delete_management('mergeKey')
		path = outputWorkspace
		name = 'mergeKey'
		mergeKey = arcpy.CreateTable_management(path, name)
		arcpy.AddField_management(mergeKey, 'MUN', 'TEXT')
		arcpy.AddField_management(mergeKey, 'BESTMERGE', 'TEXT')

		# Getting values for the key, eliminates extraneous information from the Polygon 
		# Neighbors table. Stores the pairs as tuples within a set. This prevents any duplicate
		# scenarios. 
		mergerList = set()
		cursor = arcpy.SearchCursor(polyAnalysis)
		arcpy.AddMessage('Tuple-ing...')
		for row in cursor:
			srcMun = row.getValue('src_MUN_CODE') 
			mergeMun = row.getValue('BESTMERGE')
			tup = (srcMun, mergeMun)
			mergerList.add(tup)
		del cursor 
		del row
		totalMergers = len(mergerList)

		# Populates the key table using the set of tuples constructed in the previous lines. 
		arcpy.AddMessage('Updating Key...')
		cursor = arcpy.InsertCursor(mergeKey)
		for row in range(len(mergerList)):
			newRow = cursor.newRow()
			pair = mergerList.pop()
			mun = pair[0]
			bestMerge = pair[1]
			newRow.setValue('MUN', mun)
			newRow.setValue('BESTMERGE', bestMerge)
			cursor.insertRow(newRow)
		del cursor

		# Joining the municipalities feature class with the merger key, and exporting it as its
		# own feature class.
		if(mergeCount == 1):
			baseMunis = muni
		else:
			baseMunis = 'merge%s'%(mergeCount - 1)
		layer = arcpy.MakeFeatureLayer_management(baseMunis, 'lyr')
		view = arcpy.MakeTableView_management(mergeKey, 'tbl')
		arcpy.AddJoin_management(layer, 'MUN_CODE', view, 'MUN')
		arcpy.Select_analysis(layer, 'join')

		arcpy.AddMessage('Merging Munis...')
		cursor = arcpy.SearchCursor('join')
		for row in cursor:
			
			if(iteration == 1):
				if(mergeCount > 1):
					layer = arcpy.MakeFeatureLayer_management('merge%s'%(mergeCount - 1), 'lyr')
				else:
					layer = arcpy.MakeFeatureLayer_management('join', 'lyr')	
			else:
				if(mergeCount > iterMergeCount):
					layer = arcpy.MakeFeatureLayer_management('merge%s'%(mergeCount - 1), 'lyr')
				else:
					layer = arcpy.MakeFeatureLayer_management('join', 'lyr')
				
			# Get this rows best merge municipality. Select this row, all other rows that share
			# the same best merge, and the best merge municipality using a SQL statement. 
			if(row.getValue('mergeKey_BESTMERGE') != '' and row.getValue('mergeKey_BESTMERGE') != None and row.getValue('mergeKey_BESTMERGE') != ' '):
				munCode = row.getValue('mergeKey_BESTMERGE')
				sql = '"mergeKey_BESTMERGE" =' + " '" + munCode + "'"
				arcpy.SelectLayerByAttribute_management(layer, 'NEW_SELECTION', sql)
				sql = '"mergeKey_MUN" =' + " '" + munCode + "'"
				arcpy.SelectLayerByAttribute_management(layer, 'ADD_TO_SELECTION', sql)
				
				#Getting the population total for the new municipality. 
				arcpy.Select_analysis(layer, 'selected')
				if(int(arcpy.GetCount_management('selected').getOutput(0)) != 0):
					popCursor = arcpy.SearchCursor('selected')
					totalPop = 0
					if(iteration < 2):
						field = '%s_POP2010'%(muniName)
					else:
						field = 'merge%s_POP2010'%(iterMergeCount - 1)
					for popRow in popCursor: 
						totalPop += popRow.getValue(field)
					del popRow, popCursor
							
					# Dissolve the selection to simulate a merging of the selected municipalities. 
					arcpy.Dissolve_management(layer, 'dissolve') 
					arcpy.Delete_management('selected')

					# With the pre-merger municipalities still selected, run the Delete Features tool 
					# in order to delete them.
					arcpy.DeleteFeatures_management(layer)
					
					# Merge the "chopped up" base layer with the new municipality to fill the void that 
					# the previous ones left when they were deleted. Add the new population figure to the POP2010 field.
					arcpy.Merge_management([layer, 'dissolve'], 'merge%s'%(mergeCount)) 
					nullCursor = arcpy.UpdateCursor('merge%s'%(mergeCount))
					
					if(iteration == 1):
						popVal = '%s_POP2010'%(muniName)
						mcVal = '%s_MUN_CODE'%(muniName)
					else:
						popVal = 'merge%s_POP2010'%(iterMergeCount - 1)
						mcVal = 'merge%s_MUN_CODE'%(iterMergeCount - 1)
					for nullRow in nullCursor:
						if(nullRow.isNull(popVal)):
							nullRow.setValue(popVal, totalPop)
							nullRow.setValue(mcVal, '%s'%(mergeCount))
							nullCursor.updateRow(nullRow)
					del nullRow, nullCursor
					
					#Clean up the temp files.
					if(mergeCount > 1):
						arcpy.Delete_management('merge%s'%(mergeCount - 1))
					arcpy.Delete_management('dissolve')
					
					mergeCount += 1
					thisIterationsMerges += 1
					
				else:
					arcpy.Delete_management('selected')
		arcpy.AddMessage('%s Merges Complete'%(str(mergeCount - 1)))
		iteration += 1
		lastJoinMerge = iterMergeCount - 1
		iterMergeCount += thisIterationsMerges
		del cursor, row
		
	# if(len(muniName) > 8):
		# muniName = muniName[:8]
		
	newFileName = '%s_merged'%(muniName) + '_' + str(popMin)
	
	
	if(mergeCount >= 2): 
		arcpy.Rename_management('merge%s'%(mergeCount - 1), newFileName)
	
	# Populating the County field 
	fields = [f.name for f in arcpy.ListFields(newFileName)]
	fieldName = ''
	for field in fields: 
		if('COUNTY' in field): 
			fieldName = field
			break
			
	cursor = arcpy.UpdateCursor(newFileName)
	for row in cursor:
		row.setValue(fieldName, countyName)
		cursor.updateRow(row)
	del row, cursor
	
	# Cleaning up workspace
	arcpy.Delete_management('join')
	arcpy.Delete_management('mergeKey')
	arcpy.Delete_management('poly_analysis')
	
