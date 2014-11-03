#######################################################################################
# Address List to Parcel Feature Class Tool 
# Author: Connor Hornibrook 
# Version: 3.0
# Date: 03 November 2014
# 
# Description:
#
#	For use with ArcGIS 10.1 and newer versions
#	
#	Using the arcpy library, this script allows the user to input a table of
#	addresses (in the form of a Microsoft Excel sheet) and a parcel layer of
#	their choice. The script then outputs only the parcels that match the 
#	addresses in the list and names the output file using a datestamp. This 
#	version supports the mixed use of gdb's and shapefiles (and vice versa). 
#	For instance, if a shapefile is used as the input parcel layer, but a gdb
#	is input as the output location, this tool will not work (and vice versa). 
#
# How to use this tool:
#
#	Within a toolbox in ArcCatalog, add a new script and title it 
#	"ListToParcels". Under the "General" tab, type "List to Parcels" into the 
#	"Label" field. Click the "Parameters" tab. The first parameter display name  
#	should be entered as "Table" and it's datatype should be entered as "Table". 
#	The second parameter display name should be entered as "Parcels", it should be of 
#	datatype "Feature Class". The third and final parameter display name should be 
#	entered as "Output Location", it should be of datatype "Workspace". None of the 
#	parameters are multivalued. All of them should have their "Type" (found under
#	"Parameter Properties") set to "Required". 
#
#	Go to the "Source" tab. Set the source of the script to the location of this
#	python file. Click "OK". 
#
########################################################################################

import arcpy
import datetime
from arcpy import env


# Creating the output file name
currentTime = datetime.datetime.now()
datestamp = currentTime.strftime('%m_%d_%Y')
parcelName = r'\parcels_' + datestamp

# Getting each of the parameters and converting them to strings
# The table is a Microsoft Excel sheet, the parcels are either a
# shapefile or a feature class, and the output is of type 
# workspace (can either be a folder or a gdb)

table = arcpy.GetParameterAsText(0)
parcels = arcpy.GetParameterAsText(1)
output = arcpy.GetParameterAsText(2)
savePath = output + parcelName

# Converting shapefiles to feature classes or feature classes to 
# shapefiles, if needed (i.e. the input was a shapefile and the 
# output was a geodatabase, or vice versa)

if(parcels[-4:] == '.shp' and output[-4:] == '.gdb'):
	fc = arcpy.FeatureClassToFeatureClass_conversion(parcels, output, 'convertedParcels')
	status = 0
elif(parcels[-4:] != '.shp' and output[-4:] != '.gdb'):
	fc = arcpy.FeatureClassToFeatureClass_conversion(parcels, output, 'convertedParcels')
	status = 0
else:
	fc = parcels
	status = 1

# Doing necessary steps to execute a join between the parcel
# file and the address list, and then executing said join

layer = arcpy.MakeFeatureLayer_management(fc, 'par_layer')
view = arcpy.MakeTableView_management(table, 'tbl')
arcpy.AddJoin_management(layer, 'Prop_locat', view, 'ADDRESS')

# Creating an output filepath, creating the isolated parcel layer
# and saving it to the filepath location. If the input parcels file had
# to be converted, the conversion file is now deleted. 

arcpy.Select_analysis(layer, savePath, '"ADDRESS" IS NOT NULL')
arcpy.RemoveJoin_management(layer)
if(status != 1):
	arcpy.Delete_management(fc)          

