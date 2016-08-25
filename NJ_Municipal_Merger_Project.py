__author__ = 'CFH'
import psycopg2, sets, heapq, sys

# connection to the database
conn = psycopg2.connect(database='njmergers', user='postgres', host='localhost', port='5433')
cursor = conn.cursor()

# every county in NJ by name
NJ_COUNTIES = ['ATLANTIC', 'BERGEN', 'BURLINGTON', 'CAMDEN', 'CAPEMAY', 'CUMBERLAND', 'ESSEX', 'GLOUCESTER', 'HUDSON',
               'HUNTERDON', 'MERCER', 'MIDDLESEX', 'MONMOUTH', 'MORRIS', 'OCEAN', 'PASSAIC', 'SALEM', 'SOMERSET',
               'SUSSEX', 'UNION', 'WARREN']

# From 2010 Census
COUNTY_GROWTH_RATES = {'ATLANTIC' : .087, 'BERGEN' : .024, 'BURLINGTON' : .06, 'CAMDEN' : .009,
                       'CAPEMAY' : -0.049, 'CUMBERLAND' : .071, 'ESSEX' : -0.012, 'GLOUCESTER' : .132,
                       'HUDSON' : .042, 'HUNTERDON' : .052, 'MERCER' : .045, 'MIDDLESEX' : .08,
                       'MONMOUTH' : .025, 'MORRIS' : .047, 'OCEAN' : .128, 'PASSAIC' : .025,
                       'SALEM' : .028, 'SOMERSET' : .087, 'SUSSEX' : .035, 'UNION' : .027,
                       'WARREN' : .061}

# constants for conversion
SQFT_2_SQMI = 27878400
MILES_2_FT = 5280

class Geometry(object):
    def __init__(self, shape):
        self.shape = shape

class Area(Geometry):
    def __init__(self, population, area):
        super(Area, self).__init__('POLYGON')
        self.population = population
        self.area = area
        self.density = SQFT_2_SQMI * (self.population / self.area)

class Border(Geometry):
    def __init__(self, munis, length):
        super(Border, self).__init__('LINE')
        self.munis = munis # list of Munis
        self.length = length

    def grabOtherMuni(self, thisMuni):
        if self.munis[0] == thisMuni:
            return self.munis[1]
        elif self.munis[1] == thisMuni:
            return self.munis[0]
        else: # Muni not found in border
            return None

    def __eq__(self, other):

        if (self.munis[0] not in other.munis) or (self.munis[1] not in other.munis):
            return False
        if other.shape != 'LINE':
            return False
        if self.length != other.length:
            return False
        else:
            return True

    def nameEq(self, other):
        town1 = self.munis[0].name
        town2 = self.munis[1].name

        otherTown1 = other.munis[0].name
        otherTown2 = other.munis[1].name

        if (town1 == otherTown1 or town1 == otherTown2) and (town2 == otherTown1 or town2 == otherTown2):
            return True
        else:
            return False

    def setMuni(self, muni):
        for oldMuni in self.munis:
            if oldMuni == muni:
                other = self.grabOtherMuni(oldMuni)
                self.munis = [muni, other]

    def __cmp__(self, other):
        return cmp(self.length, other.length)

    def __str__(self):
        return '%s and %s, %s miles'%(self.munis[0].name, self.munis[1].name, (self.length / MILES_2_FT))

class County(Area):
    def __init__(self, name, target):

        cursor.execute("SELECT sum(pop), sum(area) FROM munis WHERE county = '%s'"%name)
        population = 0
        area = 0
        for dataRow in [row for row in cursor]:
            population = row[0]
            area = row[1]

        super(County, self).__init__(population, area)
        self.name = name
        self.munis = []
        self.borders = set()
        self.growthRate = COUNTY_GROWTH_RATES[self.name]

        # Compute threshold to take into account population growth. If growth rate is under zero,
        # the target will be used as is
        self.thresh = target
        if self.growthRate > 0:
            self.thresh -= (self.growthRate * target)


        #####################################################################
        cursor.execute("SELECT * FROM munis WHERE county = '%s'"%(self.name))
        for muniRow in [row for row in cursor]:
            muni = Muni(self, muniRow[2], muniRow[4], muniRow[5], muniRow[8])
            self.munis.append(muni)
        self.munis.sort()
        #####################################################################

        dups = set()
        for muni in self.munis: # creating the border objects
            cursor.execute("SELECT adjcode, length FROM borders WHERE sourcecode = '%s'"%(muni.code))
            for borderRow in [row for row in cursor]:
                nbrCode = borderRow[0]
                length = borderRow[1]
                if length > 0.0 and (muni.code[:2] == nbrCode[:2]): # only within county
                    bdrStr1 = muni.code + ':' + nbrCode
                    dups.add(bdrStr1)
                    otherMuni = self.getMuniByCode(nbrCode)
                    newBorder = Border([muni, otherMuni], length)

                    if (nbrCode + ':' + muni.code) not in dups: # check for inverse duplicates
                        self.borders.add(newBorder)
                        muni.muniBorders.add(newBorder)
                    else:
                        muni.muniBorders.add(self.getBorderByMuniList([muni, otherMuni]))

                    muni.borderCount += 1

    # adds a new muni to the list, sorts the list
    def addMuni(self, muni):
        self.munis.append(muni)
        self.munis.sort()

    def getBorderByMuniList(self, muniList):
        i = 0
        muni1 = muniList[0]
        muni2 = muniList[1]
        for border in self.borders:
            if muni1 in border.munis and muni2 in border.munis:
                return border
        return None # No match found


    def getMuniByCode(self, code):
        for countyMuni in self.munis:
            if countyMuni.code == code:
                return countyMuni
        return None # no match found

    def __str__(self):
        muniStr = 'Municipalities:\n'
        i = 1
        for muni in self.munis:
            muniStr += "\t%d. %s\n"%(i, muni.name)
            i += 1
        return '%s COUNTY, POPULATION: %d\n'%(self.name, self.population) + muniStr

class Muni(Area):
    def __init__(self, county, name, code, pop, area):
        super(Muni, self).__init__(pop, area)
        self.county = county
        self.name = name
        self.code = code
        self.mergerPartner = None
        self.borderCount = 0
        self.muniBorders = set()

        self.oldMunCodes = set([self.code]) # if this is a merged muni, this will contain the codes of all the old munis

        # determining if this muni falls below the population minimum
        self.isCand = False
        if self.population < county.thresh:
            self.isCand = True

        self.wasMerged = False

    def getLongestBorder(self):
        longest = 0
        longestBorder = None
        for border in self.muniBorders:
            if border.length > longest:
                longest = border.length
                longestBorder = border
        return longestBorder


    # if this Muni is a post-merger town, return true
    def getIsMerger(self):
        return len(self.oldMunCodes) > 1

    def setOldMunCodes(self, newSet):
        self.oldMunCodes.add(newSet)

    def __eq__(self, other):

        # checking type
        if type(other) is not type(self):
            return False

        # backward compatibility: old munis are equal to the muni they merged into
        if other.code in self.oldMunCodes:
            return True

        # NJ municipal codes are unique to their munis, if the codes are equal, then the two
        # towns must be the same
        else:
            return self.code == other.code

    def __cmp__(self, other):
        return cmp(self.population, other.population)


    def __str__(self):
        return self.name + ', Mun. Code: ' + self.code + ', Pop. (2010): ' + str(self.population)

class Merger(object):
    def __init__(self):
        return

    @staticmethod
    def merge(muni, mergeID):
        foundPartner = None

        if muni.isCand or muni.borderCount == 1: # if this muni is a candidate or a donut hole...

            codePrefix = muni.county.name[:3]
            longestBorder = muni.getLongestBorder()

            longestBorderPartner = longestBorder.grabOtherMuni(muni)
            longestBorderPartnersLongestBorderPartner = longestBorderPartner.getLongestBorder().grabOtherMuni(
                                                        longestBorderPartner)

            muniBordersByLength = heapq.nlargest(len(muni.muniBorders), muni.muniBorders)
            # foundPartner = None

            trigger = (len(muniBordersByLength) > 1)

            if muni.borderCount <= 1: # donut hole muni, only borders one other municipality
                foundPartner = longestBorderPartner

            # if both are candidates and both share a longest border...
            elif longestBorderPartner.isCand and longestBorderPartnersLongestBorderPartner == muni:
                foundPartner = longestBorderPartner

            # if both are candidates but don't share a longest border...
            elif trigger and longestBorderPartner.isCand and longestBorderPartnersLongestBorderPartner != muni:

                secondLongestBorderPartner = muniBordersByLength[1].grabOtherMuni(muni)
                if secondLongestBorderPartner.isCand: # second longest bord. partner is a candidate
                    foundPartner = secondLongestBorderPartner

                elif secondLongestBorderPartner.isCand == False and len(muniBordersByLength) >= 3:
                    thirdLongestBorderPartner = muniBordersByLength[2].grabOtherMuni(muni)
                    if thirdLongestBorderPartner.isCand:
                        foundPartner = thirdLongestBorderPartner
                    else: # to avoid thin, sprawling munis, merge the non-candidate
                        foundPartner = secondLongestBorderPartner
                else: # all else failed, just merge 'em
                    foundPartner = longestBorderPartner

            elif trigger and longestBorderPartner.isCand == False and \
                            longestBorderPartnersLongestBorderPartner != muni:

                secondLongestBorderPartner = muniBordersByLength[1].grabOtherMuni(muni)
                thirdLongestBorderPartner = None
                if len(muniBordersByLength) >= 3:
                    thirdLongestBorderPartner = muniBordersByLength[2].grabOtherMuni(muni)
                if secondLongestBorderPartner.isCand:
                    foundPartner = secondLongestBorderPartner
                elif thirdLongestBorderPartner is not None and thirdLongestBorderPartner.isCand:
                    foundPartner = thirdLongestBorderPartner
                else:
                    foundPartner = longestBorderPartner

            else:
                foundPartner = longestBorderPartner


            # grab all of the old mun codes (just 2 if this is the first merger ever between
            # the two munis
            oldCodes = set()

            # Only add the old-style NJ municipal codes
            if not muni.wasMerged:
                oldCodes.add(muni.code)
            if not foundPartner.wasMerged:
                oldCodes.add(foundPartner.code)

            oldCodes |= muni.oldMunCodes
            oldCodes |= foundPartner.oldMunCodes

            # used for reassigning of pointers for the new muni
            oldMunis = set([muni, foundPartner])

            # All of the old borders from muni and foundPartner
            oldBorders = set()
            oldBorders |= muni.muniBorders
            oldBorders |= foundPartner.muniBorders

            # Grab new field values for the new muni
            newCode = codePrefix + '_%d'%mergeID
            newName = muni.name + '-' + foundPartner.name # to be concat. with other muni names
            newPop = muni.population + foundPartner.population # to be added up with other muni pops
            newArea = muni.area + foundPartner.area # to be added up with other muni areas

            # Create object for the new muni
            newMuni = Muni(muni.county, newName, newCode, newPop, newArea)
            newMuni.oldMunCodes = oldCodes
            newMuni.wasMerged = True
            newMuni.muniBorders = oldBorders

            # Delete the border between foundPartner and muni, it is no longer valid
            deleteBorders = set()
            for b in newMuni.muniBorders:
                if b.munis[0] in oldMunis and b.munis[1] in oldMunis:
                    deleteBorders.add(b)
            for b in deleteBorders:
                newMuni.muniBorders.remove(b)

            # reassign still-valid borders to new muni
            for b in newMuni.muniBorders:
                mun1 = b.munis[0]
                mun2 = b.munis[1]
                if mun1 in oldMunis:
                    b.munis[0] = newMuni
                else:
                    b.munis[1] = newMuni

            newMuni.county.munis.remove(foundPartner)
            newMuni.county.munis.remove(muni)

            newMuni.county.munis.append(newMuni)

            newMuni.county.munis = list(set(newMuni.county.munis))
            newMuni.county.munis.sort()

    @staticmethod
    def meetsThreshold(county):
        if len(county.munis) > 1:
            for m in county.munis:
                if m.population < county.thresh:
                    return False
            return True

        # else, all mergers that were possible have happened, but pop min not met, end process
        # as there are no more options
        else:
            return True

    @staticmethod
    def fixCodes(county):
        count = 1
        codePrefix = county.name[:3]
        for m in county.munis:
            m.code = codePrefix + '_%d'%count
            count += 1

class Driver(object):
    def __init__(self):

        self.clearScreen()
        print "Welcome to the New Jersey Municipal Merger Project!"
        print

        done = False

        while not done:
            self.mainMenu()
            self.mergerMenu()

            # methods have power to exit the system, not
            # actually an infinite loop

    def clearScreen(self):
        i = 0
        while i < 20:
            print
            i += 1

    def mainMenu(self):
        print
        print "Select an option by entering the corresponding number:"
        print "1. Execute a merger"
        print "2. Exit program"

        valid = False
        choiceInput = None

        while not valid:
            choiceInput = input("Choice: ")
            if choiceInput <= 2 and choiceInput > 0:
                valid = True
            else:
                print "Invalid Entry!"

        if choiceInput == 2:
            print 'Goodbye.'
            sys.exit()

        # if system doesn't exit, the next menu is initiated (see constructor)

    def mergerMenu(self):
        print
        print
        print
        print "Please enter the corresponding number for the county you'd like to merge:"
        print "0. All of them"

        countyName = ''
        count = 1
        for county in NJ_COUNTIES:
            print "%d. %s"%(count, county)
            count += 1

        valid = False
        choiceInput = None
        while not valid:
            choiceInput = input("Choice: ")
            if choiceInput >= 0 and choiceInput <= 21:
                countyName = NJ_COUNTIES[choiceInput - 1]
                valid = True
            else:
                print "Invalid input!"

        if choiceInput > 0:
            print countyName + " chosen."
            valid = False
            while not valid:
                choiceInput = input("Enter your post-merger population target: ")
                if choiceInput > 0:
                    # if merger already was executed in the past, delete its table from the db to
                    # avoid duplication error
                    cursor.execute('DROP TABLE IF EXISTS %s'%(countyName + 'merged' + str(choiceInput)))
                    target = choiceInput
                    valid = True
                else:
                    print "Invalid! Must be over 0!"

            self.main([countyName], choiceInput)
        else:
            print "You have chosen to simulate a statewide merger."
            valid = False
            while not valid:
                choiceInput = input("Enter your post-merger population target: ")
                if choiceInput > 0:
                    # if merger already was executed in the past, delete its table from the db to
                    # avoid duplication error
                    cursor.execute('DROP TABLE IF EXISTS %s'%('njmerged' + str(choiceInput)))
                    target = choiceInput
                    valid = True
                else:
                    print "Invalid! Must be over 0!"
            self.main(NJ_COUNTIES, choiceInput)

    def main(self, countyList, target):
        muniCount = 0
        countyCount = 1
        outAreaName = ''

        if len(countyList) == 1:
            outAreaName = countyList[0]
        else:
            outAreaName = 'nj'

        newTableFields = 'county varchar, mun varchar, muncode varchar(6), pop int, popden double precision, '
        newTableFields += 'area double precision, merged int'

        cursor.execute('CREATE TABLE joinKey (old char(4), new varchar(6));')
        cursor.execute('CREATE TABLE newmunis (%s)'%newTableFields)

        for county in countyList:
            c = County(county, target)
            codePrefix = c.name[:3]
            mergeID = 1
            munis = list(c.munis)
            while not Merger.meetsThreshold(c):
                muni = munis.pop(0)
                if muni in c.munis:
                    Merger.merge(muni, mergeID)
                    mergeID += 1
                munis = list(c.munis)
            Merger.fixCodes(c)
            for m in c.munis:
                muniCount+=1
            countyCount+=1

            for m in c.munis:
                mergeStatus = 0
                if m.wasMerged:
                    mergeStatus = 1

                for old in m.oldMunCodes:
                    cursor.execute("INSERT INTO joinkey (old, new) VALUES ('%s', '%s');"%(old, m.code))
                cursor.execute("INSERT INTO newmunis VALUES ('%s', '%s', '%s', %d, %d, %d, %d)"%(m.county.name,
                                                                                                 m.name, m.code,
                                                                                                 m.population,
                                                                                                 m.density, m.area,
                                                                                                 mergeStatus))
        print
        print 'Pre-merger muni count: 565'
        print 'Post-merger muni count: %d'%muniCount
        print 'Merging geometries...'
        joinQuery = 'SELECT * FROM munis INNER JOIN joinkey ON joinkey.old=munis.muncode ORDER BY county'
        cursor.execute('CREATE TABLE munijoin AS (%s)'%joinQuery)

        stUnionQuery = 'SELECT new, ST_Union(geom) FROM munijoin GROUP BY new'
        cursor.execute('CREATE TABLE tmp AS (%s)'%stUnionQuery)

        tableName = '%smerged'%(outAreaName) + str(target)
        joinQuery = 'SELECT * FROM newmunis INNER JOIN tmp ON tmp.new=newmunis.muncode ORDER BY county'
        cursor.execute('CREATE TABLE %s AS (%s)'%(tableName, joinQuery))

        cursor.execute('ALTER TABLE %s DROP COLUMN new'%tableName)
        cursor.execute('ALTER TABLE %s RENAME COLUMN st_union TO geom'%tableName)


        # The following query cleans up potential slivers that were appearing as a result of
        # the running of ST_Union. Compliments to the article found at this url:
        # http://geospatial.commons.gc.cuny.edu/2013/11/04/filling-in-holes-with-postgis/
        # This solution was integral to solving a major topology bug in this program.

        cleanupQ =      """UPDATE %s t
                        SET geom = a.geom
                        FROM (
                            SELECT muncode, ST_Collect(ST_MakePolygon(geom)) AS geom
                            FROM (
                                SELECT muncode, ST_NRings(geom) AS nrings,
                                    ST_ExteriorRing((ST_Dump(geom)).geom) AS geom
                                FROM %s
                                WHERE ST_NRings(geom) > 1
                                ) s
                            GROUP BY muncode, nrings
                            HAVING nrings > COUNT(muncode)
                            ) a
                        WHERE t.muncode = a.muncode;"""%(tableName, tableName)

        cursor.execute(cleanupQ)


        cursor.execute('DROP TABLE newmunis')
        cursor.execute('DROP TABLE tmp')
        cursor.execute('DROP TABLE munijoin')
        cursor.execute('DROP TABLE joinkey')
        conn.commit()
        print 'Finished. Data now in PostgreSQL database.'

if __name__ == '__main__':
    d = Driver()















