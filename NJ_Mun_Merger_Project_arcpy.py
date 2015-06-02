#############################################################################################################
#
# Author: Connor Hornibrook
# Version: 5.0
# Date: 02 June 2015
# 
# Created at various computer labs at Rowan University, specifically Robinson Hall 301 (the Geolab)
#
#############################################################################################################


import arcpy
from arcpy import env
import sets
import gc


arcpy.env.overwriteOutput = True

#############################################################################################################
# Parameters & Workspace 

# Multivalue list of counties to be run through the program
county_list = arcpy.GetParameterAsText(0).split(';')

# The desired population minimum to be used
popMin = int(arcpy.GetParameterAsText(1))

# Where the output files will be saved
outputWorkspace = arcpy.GetParameterAsText(2)

# Setting the workspace
arcpy.env.workspace = outputWorkspace

# List of finalized, merged counties. Used as input for the merge tool at the end of the process i.e. merging
# all counties into one state-wide feature class
finalMergeFiles = []

#############################################################################################################
#############################################################################################################
# Methods and global variables

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
			

# Needed due to inconsistencies between cloud python and desktop python, replaces the len() method. Cloud uses a version of python
# that no longer recognizes len(), while desktop still uses 2.7.		
def manualLength(string): 
	length = 0
	for s in string: 
		length += 1
	return length

# Takes an array of municipality names and parses them together. Allows the user to see who merged with whom after the process is finished.
# Helps populate the 'MUN' field.
def newMuniName(oldNames):
	newName = ''
	for name in oldNames: 
		newName += (name + '-')
	
	# Return the new string with out the extraneous '-' character 
	return newName[:-1]
	

# Credit to Brett Cannon on code.ActiveState.com, slight modifications by myself.
# Returns a raw string representation of text and eliminates all special backslash characters
def raw(text):
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
		
	del r, cursor 	
	return mergerMunCode
	
#############################################################################################################
#############################################################################################################

for county_shp in county_list:
	
	# Some counties will require more than one round of mergers, i.e. a merger occurs and the population 
	# minimum is still not met.
	iteration = 1
	
	# Trigger variable that alerts the program if all municipalities meet the population minimum requirement.
	popReqMet = False

	# A dictionary that will contain the new municipal codes and names, paired together. Used to populate 
	# fields after each iteration.
	muni_dict = {}
	
	# Removing the file path from the name. The county_name variable will be used for file naming purposes throughout the 
	# program.
	splitPath = raw(county_shp).split('\\')
	county_name = splitPath[manualLength(splitPath) - 1]
	arcpy.AddMessage(county_name)
	
	# The main process: continue until all municipalities in this county have a population over the desired minimum that
	# was input by the user. 
	while popReqMet == False: 
		
		baseFile = ''
		if(iteration == 1):
			baseFile = county_shp
		else:
			baseFile = county_name
			
		fields = arcpy.ListFields(baseFile)
		fieldName = [f.name for f in fields]
		
		# This field will contain a number pertaining to which merge in sequence each municipality belongs to. If two municipalities
		# are merging, they will both have the same ID. 
		if('MERGE_ID' not in fieldName):
			arcpy.AddField_management(baseFile, 'MERGE_ID', 'LONG')
			
		# Boolean field that flags all municipalities that are initial basic candidates i.e. those that are below the minimum.
		if('isCand' not in fieldName):
			arcpy.AddField_management(baseFile, 'isCand', 'SHORT')
			
		# Calculating the isCand field. 
		code = """def isCand(x):
			if(x < %s):
				return 1
			else:
				return 0"""%(popMin)

		arcpy.CalculateField_management(baseFile, 'isCand', 'isCand(!POP2010!)', 'PYTHON_9.3', code)
		
		# Creating a polygon neighbor analysis table. It will contain all border information for every municipality. 		
		in_fields = [r'MUN_CODE', r'isCand']
		polyAnalysis = arcpy.PolygonNeighbors_analysis(baseFile, 'poly_analysis', in_fields)
		arcpy.AddField_management(polyAnalysis, 'BESTMERGE', 'TEXT')
		
		# Creating a merge key, which will contain pairs of municipalities that are best fits to merge together. 
		name = 'mergeKey'
		mergeKey = arcpy.CreateTable_management(outputWorkspace, name)
		arcpy.AddField_management(mergeKey, 'CODE', 'TEXT')
		arcpy.AddField_management(mergeKey, 'BESTMERGE', 'TEXT')

		
		# Updating the new fields in the Polygon Neighbors table. 
		cursor = arcpy.UpdateCursor(polyAnalysis) 
		row = cursor.next()
		arcpy.AddMessage('Finding merge partners...')
		while row: 
			srcMunCode = row.getValue('src_MUN_CODE')
			borders = getAllBorders(srcMunCode)
			longestBorder = 0
			if(manualLength(borders) > 1):
				longestBorder = max(borders)
			else:
				longestBorder = borders[0]
			row.setValue('BESTMERGE', getFellowMerger(longestBorder, srcMunCode))
			cursor.updateRow(row)
			row = cursor.next()
		del row, cursor 
		

		# Getting values for the key, eliminates extraneous information from the Polygon 
		# Neighbors table. Stores the pairs as tuples within a set. This prevents any duplicate
		# scenarios. 
		codeList = set()
		
		cursor = arcpy.SearchCursor(polyAnalysis)
		arcpy.AddMessage('Tuple-ing...')
		row = cursor.next()
		
		while row:
			srcMun = row.getValue('src_MUN_CODE') 
			mergeMun = row.getValue('BESTMERGE')
			tup = (srcMun, mergeMun)
			if(mergeMun != ''): 
				codeList.add(tup) 
			else:
				codeList.add((srcMun, None))
			cursor.updateRow(row)
			row = cursor.next() 
		del row, cursor

		# Populates the key table using the set of tuples constructed in the previous lines. 
		arcpy.AddMessage('Updating Key...')
		cursor = arcpy.InsertCursor(mergeKey)
		
		for source_mun, merge_mun in codeList:
			row = cursor.newRow()
			row.setValue('CODE', source_mun)
			row.setValue('BESTMERGE', merge_mun)
			cursor.insertRow(row)
			
			if(merge_mun != None): 
				arcpy.AddMessage("Source: " + source_mun + ", Best Merge: " + merge_mun)
			else:
				arcpy.AddMessage("Source: " + source_mun + ", Best Merge: <Null>")
		del row, cursor
		
		# Joining the feature class to the merge key.
		baseCountyName = 'base_county_' + str(iteration)
		arcpy.AddJoin_management(arcpy.MakeFeatureLayer_management(baseFile, 'lyr'), 'MUN_CODE', arcpy.MakeTableView_management(mergeKey, 'tbl'), 'CODE', 'KEEP_ALL')
		arcpy.Select_analysis('lyr', baseCountyName)
		arcpy.MakeFeatureLayer_management(baseCountyName, 'muni_lyr')
		
		arcpy.AddMessage('KEY AND GEOMETRY JOINED')
		arcpy.AddMessage('ITERATION: %s'%(str(iteration)))
		
		# Used to create new municipal codes for the post-merge municipalities. A Sussex County municipality, for example, 
		# may be SUX_1. 
		newMunCode = 1
		
		# Populating the MERGE_ID field and crafting new municipal names. 
		cursor = arcpy.UpdateCursor('muni_lyr')
		row = cursor.next()
		while row: 
			code = row.getValue('mergeKey_CODE')
			bestMerge = row.getValue('mergeKey_BESTMERGE')
			merge_ID = row.getValue('%s_MERGE_ID'%(county_name))
			
			if(bestMerge != None and merge_ID == None):
				oldNames = set()
				sql = '\"mergeKey_CODE\" = \'' + bestMerge + '\' OR \"mergeKey_BESTMERGE\" = \'' + bestMerge + '\' OR \"mergeKey_CODE\" = \'' + code + '\' OR \"mergeKey_BESTMERGE\" = \'' + code + '\''
				arcpy.SelectLayerByAttribute_management('muni_lyr', 'NEW_SELECTION', sql)
				arcpy.CalculateField_management('muni_lyr', '%s_MERGE_ID'%(county_name), newMunCode, 'PYTHON_9.3')
				
				nameCursor = arcpy.SearchCursor('muni_lyr')
				for nameRow in nameCursor: 
					oldNames.add(nameRow.getValue('%s_MUN'%(county_name)))
				del nameRow, nameCursor
				
				muni_dict[str(newMunCode)] = newMuniName(oldNames)
				newMunCode += 1
				
			cursor.updateRow(row)
			row = cursor.next()
		del row, cursor 
		
		arcpy.SelectLayerByAttribute_management('muni_lyr', 'CLEAR_SELECTION')
		cursor = arcpy.UpdateCursor('muni_lyr')
		row = cursor.next()
		
		while row:
			merge_ID = row.getValue('%s_MERGE_ID'%(county_name))
			if(merge_ID == None):
				row.setValue('%s_MERGE_ID'%(county_name), newMunCode)
				muni_dict[str(newMunCode)] = row.getValue('%s_MUN'%(county_name))
				newMunCode += 1
				
			cursor.updateRow(row)
			row = cursor.next()
		del row, cursor
		
		# Dissolving the file on the MERGE_ID field, this is the actual 'merge'. Using the POP_2010 field as statistic 
		# field to get the new population of each municipality. Deleting all temp files. 
		arcpy.Dissolve_management('muni_lyr', 'temp', '%s_MERGE_ID'%(county_name), '%s_POP2010 SUM'%(county_name))
		arcpy.Delete_management(baseCountyName)	
		arcpy.Rename_management('temp', baseCountyName)
		
		# Adding clean field names to avoid problems if more iterations are needed. 
		arcpy.AddField_management(baseCountyName, 'MUN', 'TEXT', '', '', 300)
		arcpy.AddField_management(baseCountyName, 'MUN_CODE', 'TEXT')
		arcpy.AddField_management(baseCountyName, 'POP2010', 'LONG')
		arcpy.AddField_management(baseCountyName, 'POPDEN2010', 'LONG')
		arcpy.AddField_management(baseCountyName, 'COUNTY', 'TEXT')
		
		# Calculating these new, cleaner fields
		arcpy.CalculateField_management(baseCountyName, 'POP2010', '!SUM_%s_POP2010!'%(county_name), 'PYTHON_9.3')
		arcpy.CalculateField_management(baseCountyName, 'POPDEN2010', 'int(round(!POP2010! / (!Shape_Area! * 0.0000000358701)))', 'PYTHON_9.3') 
		arcpy.DeleteField_management(baseCountyName, 'SUM_%s_POP2010'%(county_name))
		arcpy.CalculateField_management(baseCountyName, 'COUNTY', '"' + county_name + '"', 'PYTHON_9.3')
		
		# Setting the new municipal codes
		cursor = arcpy.UpdateCursor(baseCountyName) 
		row = cursor.next()
		
		while row: 
			for code, name in muni_dict.iteritems(): 
				if(str(row.getValue('%s_MERGE_ID'%(county_name))) == code):
					row.setValue('MUN', name)
			cursor.updateRow(row)
			row = cursor.next()
		del row, cursor 
		
		# Setting the new municipal names
		cursor = arcpy.UpdateCursor(baseCountyName)
		row = cursor.next()
		
		countyAbr = county_name[:3]
		while row: 
			row.setValue('MUN_CODE', countyAbr + '_' + str(row.getValue('%s_MERGE_ID'%(county_name))))
			cursor.updateRow(row)
			row = cursor.next()
		del row, cursor 
		
		arcpy.DeleteField_management(baseCountyName, '%s_MERGE_ID'%(county_name))
		
		# Cleaning up temp files
		if(iteration == 1):
			arcpy.Rename_management(baseCountyName, county_name)
		else:
			arcpy.Rename_management(baseCountyName, 'temp')
			arcpy.Delete_management(county_name)
			arcpy.Rename_management('temp', county_name)
		
		# Checking to see if more iterations are needed
		cursor = arcpy.SearchCursor(county_name)
		row = cursor.next()
		lowPopCount = 0
		while row:
			if(row.getValue('POP2010') < popMin):
				lowPopCount += 1
			cursor.updateRow(row)
			row = cursor.next()
		del row, cursor 
		
		if(lowPopCount == 0):
			finalFilePath = county_name + '_%s'%(str(popMin))
			arcpy.Rename_management(county_name, finalFilePath)
			finalMergeFiles.append(finalFilePath)
			popReqMet = True 
		
		else:
			muniDict = {}
			
		iteration += 1



# Once the process is complete for all input files, merge them into one big file (only if there'
# more than one file present. 
if(manualLength(county_list) > 1): 		
	arcpy.Merge_management(finalMergeFiles, 'nj_merged_%s'%(str(popMin)))
	# Now that there is a unified file, delete the individual county ones. 
	for file in finalMergeFiles:
		arcpy.Delete_management(file)
arcpy.Delete_management('mergeKey')
arcpy.Delete_management('poly_analysis')

		
		
		
	

	
	
