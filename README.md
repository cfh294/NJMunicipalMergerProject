NJ Municipal Merger Project
========

## What are municipal mergers? 

Municipal mergers are a oft-used solution to administrative inefficiency. By merging two municipalities, many of the costs of running two municipalities would then be one. There is debate over the effectiveness of such policies, however they have been successful with national, top-down policies (for more info: https://en.wikipedia.org/wiki/Merger_(politics) ). 

## Why New Jersey? 

New Jersey has a lot of municipalities relative to its area. 565 to be exact. Due to New Jersey's high local and state taxes, there have been efforts to initiate municipal mergers as a possible solution. 

## So what is this? 

I decided to try to model a state-wide merger policy that distributes geography evenly. The model takes a population minimum and merges until all new munis. meet the requirement. Town names are combined, new muncipal codes are crafted, and population and population density values are both re-calculated.

## Requirements...

- ArcMap 10+. I know, I'm sorry. 
- NJ municipalities shapefile or feature class that contains the population values for each municipality. These shapefiles are located in the folder provided in this repository. The field names and values are prepared exactly for this project, so these should be the only inputs used. To use this file, just download this repo as a zip file. 
- Patience...while the original methodology for this program ran for literally 15 hours for the entire state, this one still   takes around an hour. Not too bad, especially if you are only doing one or two counties (roughly 5-10 minutes per county). 

## Performance...

So far the program works pretty well for lower thresholds (under around 15,000 people). However, anything over seems to cause memory leaks (shocker ArcMap) on the computers I'm using. However, one can work around this by simply renaming the temp file that is produced by the program before it crashes, and putting back in as an input. Unfortunately, this is the only solution I have found so far, but I am currently trying to find the cause of this problem. So this is where you possibly come in! Someone in the open source world, please help me out if you know what could be causing my computer's memory usage to look like a seismograph! 

## The Future...

Ideally, I'd like to re-write this process using the QGIS python library to make it completely free to use. I am also going to explore using PostgreSQL and PostGIS functions to possibly re-write it in SQL to improve performance. 
