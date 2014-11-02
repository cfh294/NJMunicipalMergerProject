###############################################################################
# Address List to Parcel Feature Class Tool 
# Author: Connor Hornibrook 
# Version: 2.0
# Date: 31 October 2014
# 
# Description:
#	Using the arcpy library, this script allows the user to input a table of
#	addresses (in the form of a Microsoft Excel sheet) and a parcel layer of
#	their choice. The script then outputs only the parcels that match the 
#	addresses in the list and names the output file using a datestamp. This 
#	version only supports one-way file type usage. For instance, if a shapefile
#	is used as the input parcel layer, but a geodatabase is input as the output
#	location, this tool will not work (and vice versa). 
#
################################################################################

import arcpy
import datetime
from arcpy import env

arcpy.env.overwriteOutput = True

# Creating the output file name
currentTime = datetime.datetime.now()
datestamp = currentTime.strftime('%d_%m_%Y')
parcelName = r'\parcels_' + datestamp

# Getting each of the parameters and converting them to strings
# The table is a Microsoft Excel sheet, the parcels are either a
# shapefile or a feature class, and the output is of type 
# workspace (can either be a folder or a geodatabase)

table = arcpy.GetParameterAsText(0)
parcels = arcpy.GetParameterAsText(1)
output = arcpy.GetParameterAsText(2)

# Doing necessary steps to execute a join between the parcel
# file and the address list, and then executing said join

layer = arcpy.MakeFeatureLayer_management(parcels, 'par_layer')
view = arcpy.MakeTableView_management(table, 'tbl')
arcpy.AddJoin_management(layer, 'Prop_locat', view, 'ADDRESS')

# Creating an output filepath, creating the isolated parcel layer
# and saving it to the filepath location

path = output + parcelName
arcpy.Select_analysis(layer, path, '"ADDRESS" IS NOT NULL')
arcpy.RemoveJoin_management(layer)                        
