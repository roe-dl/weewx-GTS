#!/usr/bin/python3
# Workaround for calculation of barometer values by different algorithms
# Copyright (C) 2023 Johanna Roedenbeck

# derived from weewx.wxxtypes
# thanks to and copyright by Tom Keffer

"""

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""

"""

    By 2023 the parameter `option_dict` of `get_scalar` is not fully
    implemented in WeeWX. Therefore no thing like 
    `$current.barometer(algorithm="paManBar") would work to specify
    another algorithm to calculate barometric pressure for display
    in skins or diagrams. But WeeWX includes several algorithms 
    in uwxutils.py that cannot be used otherwise.
    
    While `option_dict` cannot be used to specify the algorithm, this
    XType extension provides a workaround. The algorithm name is
    to be added to the observation type, forming a new observation
    type.
    
    See 
    https://github.com/weewx/weewx/pull/874
    for comments of Tom Keffer regarding the misuse of observation
    types for this purpose.
    
    Additionally the barometer formula of the German Weather Service
    DWD is added.
    
"""

VERSION = "1.0"

if __name__ == '__main__':
    # for testing
    import sys
    sys.path.append('/usr/share/weewx')

import math

import weewx.units
import weewx.xtypes
import weewx.wxformulas
import weewx.uwxutils
from weewx.units import ValueTuple

BAROMETER_ALGORITHMS = ('paWView','paUnivie','paDavisVp','paManBar','paDWD')
VAPOR_ALGORITHMS = ('vaDavisVp','vaBuck','vaBuck81','vaBolton','vaTetenNWS','vaTetenMurray','vaTeten','vaDWD')

class TWxUtils(weewx.uwxutils.TWxUtils):

    @staticmethod
    def StationToSeaLevelPressure(pressureHPa, elevationM,
                                  currentTempC, meanTempC, humidity,
                                  algorithm = 'paManBar'):
        Result = pressureHPa * TWxUtils.PressureReductionRatio(pressureHPa,
                                                               elevationM,
                                                               currentTempC,
                                                               meanTempC,
                                                               humidity,
                                                               algorithm)
        return Result

    @staticmethod
    def PressureReductionRatio(pressureHPa, elevationM,
                               currentTempC, meanTempC, humidity,
                               algorithm = 'paManBar'):
        if algorithm == 'paDWD':
            # German Weather Service DWD
            # https://www.dwd.de/DE/leistungen/pbfb_verlag_vub/pdf_einzelbaende/vub_2_binaer_barrierefrei.pdf?__blob=publicationFile&v=4
            vp = TWxUtils.ActualVaporPressure(currentTempC,humidity,'vaDWD')
            Result = math.exp(TWxUtils.gravity/TWxUtils.gasConstantAir*elevationM/(weewx.uwxutils.CToK(currentTempC)+vp*0.12+TWxUtils.standardLapseRate*elevationM/2))
            if __name__ == '__main__':
                print('ratio DWD',Result)
            
        else:
            Result = super(TWxUtils,TWxUtils).PressureReductionRatio(
                          pressureHPa, elevationM,
                          currentTempC, meanTempC, humidity,
                          algorithm = algorithm)
        
        return Result

    @staticmethod
    def ActualVaporPressure(tempC, humidity, algorithm='vaBolton'):
        result = (humidity * TWxUtils.SaturationVaporPressure(tempC, algorithm)) / 100.0
        return result

    @staticmethod
    def SaturationVaporPressure(tempC, algorithm='vaBolton'):
        if algorithm == 'vaDWD':
            # German Weather Service DWD
            # https://www.dwd.de/DE/leistungen/pbfb_verlag_vub/pdf_einzelbaende/vub_2_binaer_barrierefrei.pdf?__blob=publicationFile&v=4
            Result = 6.11213*math.exp(17.5043*tempC/(241.2+tempC))
            if __name__ == '__main__':
                print('SVP DWD',Result)
        else:
            Result = super(TWxUtils,TWxUtils).SaturationVaporPressure(tempC, algorithm)
        return Result


class TWxUtilsUS(weewx.uwxutils.TWxUtilsUS):

    @staticmethod
    def StationToSeaLevelPressure(pressureIn, elevationFt,
                                  currentTempF, meanTempF, humidity,
                                  algorithm='paManBar'):
        """Example:
        >>> p = TWxUtilsUS.StationToSeaLevelPressure(24.692, 5431, 59.0, 50.5, 40.5)
        >>> print("Station to SLP = %.3f" % p)
        Station to SLP = 30.006
        """
        Result = pressureIn * TWxUtilsUS.PressureReductionRatio(pressureIn,
                                                                elevationFt,
                                                                currentTempF,
                                                                meanTempF,
                                                                humidity,
                                                                algorithm)
        return Result

    @staticmethod
    def PressureReductionRatio(pressureIn, elevationFt,
                               currentTempF, meanTempF, humidity,
                               algorithm='paManBar'):
        Result = TWxUtils.PressureReductionRatio(
                               weewx.uwxutils.InToHPa(pressureIn),
                               weewx.uwxutils.FtToM(elevationFt),
                               weewx.uwxutils.FToC(currentTempF),
                               weewx.uwxutils.FToC(meanTempF),
                               humidity, algorithm)
        return Result


class PressureCooker(weewx.xtypes.XType):
    """Pressure related extensions to the WeeWX type system. 
    
       Copyright Tom Keffer, extended by Johanna Roedenbeck
       
       from weewx.wxxtypes.PressureCooker
       
    """

    def __init__(self, altitude_vt,
                 max_delta_12h=1800,
                 altimeter_algorithm='aaASOS',
                 barometer_algorithm='paWView'):

        # Algorithms can be abbreviated without the prefix 'aa':
        if not altimeter_algorithm.startswith('aa'):
            altimeter_algorithm = 'aa%s' % altimeter_algorithm
        if not barometer_algorithm.startswith('pa'):
            barometer_algorithm = 'pa%s' % barometer_algorithm

        self.altitude_vt = altitude_vt
        self.max_delta_12h = max_delta_12h
        self.altimeter_algorithm = altimeter_algorithm
        self.barometer_algorithm = barometer_algorithm

        # Timestamp (roughly) 12 hours ago
        self.ts_12h = None
        # Temperature 12 hours ago as a ValueTuple
        self.temp_12h_vt = None
        
        # Initialize additional observation types
        for algorithm in BAROMETER_ALGORITHMS:
            weewx.units.obs_group_dict.setdefault(
                'barometer'+algorithm[2:],'group_pressure')

    def _get_temperature_12h(self, ts, dbmanager):
        """Get the temperature as a ValueTuple from 12 hours ago.  The value will
         be None if no temperature is available.
         """

        ts_12h = ts - 12 * 3600

        # Look up the temperature 12h ago if this is the first time through,
        # or we don't have a usable temperature, or the old temperature is too stale.
        if self.ts_12h is None \
                or self.temp_12h_vt is None \
                or abs(self.ts_12h - ts_12h) > self.max_delta_12h:
            # Hit the database to get a newer temperature.
            if dbmanager:
                record = dbmanager.getRecord(ts_12h, max_delta=self.max_delta_12h)
            else:
                record = None
            if record and 'outTemp' in record:
                # Figure out what unit the record is in ...
                unit = weewx.units.getStandardUnitType(record['usUnits'], 'outTemp')
                # ... then form a ValueTuple.
                self.temp_12h_vt = weewx.units.ValueTuple(record['outTemp'], *unit)
            else:
                # Invalidate the temperature ValueTuple from 12h ago
                self.temp_12h_vt = None
            # Save the timestamp
            self.ts_12h = ts_12h

        return self.temp_12h_vt

    def get_scalar(self, key, record, dbmanager, **option_dict):
        if key == 'pressure':
            return self.pressure(record, dbmanager)
        elif key == 'altimeter':
            return self.altimeter(record)
        elif key == 'barometer':
            return self.barometer(record,self.barometer_algorithm)
        elif key.startswith('barometer'):
            algorithm = key[9:]
            if algorithm:
                if not algorithm.startswith('pa'):
                    algorithm = 'pa'+algorithm
                return self.barometer(record, dbmanager, algorithm)
        raise weewx.UnknownType(key)

    def pressure(self, record, dbmanager):
        """Calculate the observation type 'pressure'."""

        # All of the following keys are required:
        if any(key not in record for key in ['usUnits', 'outTemp', 'barometer', 'outHumidity']):
            raise weewx.CannotCalculate('pressure')

        # Get the temperature in Fahrenheit from 12 hours ago
        temp_12h_vt = self._get_temperature_12h(record['dateTime'], dbmanager)
        if temp_12h_vt is None \
                or temp_12h_vt[0] is None \
                or record['outTemp'] is None \
                or record['barometer'] is None \
                or record['outHumidity'] is None:
            pressure = None
        else:
            # The following requires everything to be in US Customary units.
            # Rather than convert the whole record, just convert what we need:
            record_US = weewx.units.to_US({'usUnits': record['usUnits'],
                                           'outTemp': record['outTemp'],
                                           'barometer': record['barometer'],
                                           'outHumidity': record['outHumidity']})
            # Get the altitude in feet
            altitude_ft = weewx.units.convert(self.altitude_vt, "foot")
            # The outside temperature in F.
            temp_12h_F = weewx.units.convert(temp_12h_vt, "degree_F")
            pressure = weewx.uwxutils.uWxUtilsVP.SeaLevelToSensorPressure_12(
                record_US['barometer'],
                altitude_ft[0],
                record_US['outTemp'],
                temp_12h_F[0],
                record_US['outHumidity']
            )

        return ValueTuple(pressure, 'inHg', 'group_pressure')

    def altimeter(self, record):
        """Calculate the observation type 'altimeter'."""
        if 'pressure' not in record:
            raise weewx.CannotCalculate('altimeter')

        # Convert altitude to same unit system of the incoming record
        altitude = weewx.units.convertStd(self.altitude_vt, record['usUnits'])

        # Figure out which altimeter formula to use, and what unit the results will be in:
        if record['usUnits'] == weewx.US:
            formula = weewx.wxformulas.altimeter_pressure_US
            u = 'inHg'
        else:
            formula = weewx.wxformulas.altimeter_pressure_Metric
            u = 'mbar'
        # Apply the formula
        altimeter = formula(record['pressure'], altitude[0], self.altimeter_algorithm)

        return ValueTuple(altimeter, u, 'group_pressure')

    def barometer(self, record, dbmanager=None, algorithm=None):
        """Calculate the observation type 'barometer'"""

        if 'pressure' not in record or 'outTemp' not in record:
            raise weewx.CannotCalculate('barometer')

        # Convert altitude to same unit system of the incoming record
        altitude = weewx.units.convertStd(self.altitude_vt, record['usUnits'])
        
        if algorithm is not None and algorithm!='paWView':
            if record['usUnits'] == weewx.US:
                formula = TWxUtilsUS.StationToSeaLevelPressure
                u = 'inHg'
            else:
                formula = TWxUtils.StationToSeaLevelPressure
                u = 'mbar'
            temp_12h_vt = self._get_temperature_12h(record['dateTime'], dbmanager)
            if temp_12h_vt:
                temp_12h = weewx.units.convertStd(temp_12h_vt,record['usUnits'])[0]
            else:
                temp_12h = record['outTemp']
            meanTemp = (record['outTemp']+temp_12h)/2.0
            try:
                barometer = formula(record['pressure'],altitude[0],
                                    record['outTemp'],meanTemp,
                                    record.get('outHumidity',50.0),algorithm)
            except ValueError as e:
                raise weewx.UnknownType(str(e))
            return ValueTuple(barometer, u, 'group_pressure')

        # Figure out what barometer formula to use:
        if record['usUnits'] == weewx.US:
            formula = weewx.wxformulas.sealevel_pressure_US
            u = 'inHg'
        else:
            formula = weewx.wxformulas.sealevel_pressure_Metric
            u = 'mbar'
        # Apply the formula
        barometer = formula(record['pressure'], altitude[0], record['outTemp'])

        return ValueTuple(barometer, u, 'group_pressure')


if __name__ == '__main__':

    p = TWxUtils.StationToSeaLevelPressure(1013.25,170,15.0,15.0,50,'paManBar')
    print(p)
    p = TWxUtils.StationToSeaLevelPressure(1013.25,170,15.0,15.0,50,'paDWD')
    print(p)
    p = TWxUtilsUS.StationToSeaLevelPressure(24.692, 5431, 59.0, 50.5, 40.5) # paManBar
    print(p==30.005996158533517,p)
    p = TWxUtilsUS.StationToSeaLevelPressure(24.692, 5431, 59.0, 50.5, 40.5, algorithm='paDWD')
    print(p)
    
    pc = PressureCooker(ValueTuple(170,'meter','group_altitude'))
    p = pc.get_scalar('barometerDWD',{'usUnits':16,'dateTime':1689084000,'outTemp':15,'outHumidity':50,'pressure':1013.25},None)
    print(p)
    pc = PressureCooker(ValueTuple(5431,'foot','group_altitude'))
    p = pc.get_scalar('barometerManBar',{'usUnits':1,'dateTime':1689084000,'outTemp':54.75,'outHumidity':40.5,'pressure':24.692},None)
    print(p,TWxUtilsUS.StationToSeaLevelPressure(24.692, 5431, 54.75, 54.75, 40.5))
