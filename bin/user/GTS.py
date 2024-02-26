# calculating Gruenlandtemperatursumme
# Copyright (C) 2021, 2022, 2023, 2024 Johanna Roedenbeck

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

  That extension calculates the "Gruenlandtemperatursumme" (GTS) and
  the date when it exceedes 200, which is considered the start of
  growing of plants in Europe.
  
  It supplies the following values:
  
  GTS: 
  
    Gruenlandtemperatursumme
    
    The value is based on daily average temperature. If that temperature
    is above 0°C (32°F) it is used, otherwise discarded. The calculation 
    always starts at the beginning of the year.
    * In January, all the averages are multiplied by 0.5
    * In February, all the averages are multiplied by 0.75
    * From March on up to the End of May the averages are used as is.
    * From June on no value is used.
    To get a day's value, all averages from the beginning of the
    year to that day, preprocessed as described, are summarized. 
    
  GTSdate: 
  
    The date when the GTS exceeds 200. There is one such event
    per year, only.

  utcoffsetLMT:
  
    time offset of the local mean time (LMT)
    
  LMTtime:
  
    user $current.LMTtime.raw to geht LMT of the last record
      
  dayET and ET24:
  
    ET is the opposite to rain. Both observation types are the
    sum over 1 archive interval. Especially for ET that is a
    very small value.
    
    Regarding rain, there are 2 additional values defined,
    'dayRain' and 'rain24'. That are some kind of aggregation,
    but they are provided as scalar values.
    
    This extension does the same for ET and provides dayET and
    ET24.
    
  radiation.energy_integral
  
    That is an additional aggregation, only. It is done for the
    observation type 'radiation' and calculates total energy
    received during the aggregation interval.
    
  As this is about growing of plants and the sun is important
  for that, day borders are based on local mean time for the
  station's location rather than local time according to the local 
  timezone, which can be hours away from that. Additionally,
  because of that, no daylight savings time switch is performed.
  
  If a value is requested, and no value within the same year was 
  requested before, all the values of that year are calculated and 
  saved into an array for further use. All subsequent calls return 
  values from memory. So the loop runs only once for each year
  after the start of WeeWX.
  
  If a new day starts and a value for that day is requested for
  the first time, that only value is calculated and added to
  the sum. 
    
  Note: archiveYearSpan(archiveYearSpan(some_ts)[0])[0] is the start
        of the previous year of some_ts!!!
        
        archiveYearSpan(some_ts)[0] ==> Jan 1st 00:00:00
        archiveYearSpan(some_ts)[1] ==> Dec 31st 24:00:00 
       
        some_ts ranges from Jan 1st 00:00:01 to Dec 31st 24:00:00
        
  Note: 1 day is 86400s, but once a year it is 90000 and once 82800, 
        when daylight saving time is switched on and off. 
        
"""

VERSION = "1.1"

# deal with differences between python 2 and python 3
try:
    # Python 3
    import queue
except ImportError:
    # Python 2
    # noinspection PyUnresolvedReferences
    import Queue as queue

try:
    # Python 3
    from urllib.parse import urlencode
except ImportError:
    # Python 2
    # noinspection PyUnresolvedReferences
    from urllib import urlencode

import time
import datetime
import threading
import math

import weedb
import weewx
import weewx.manager
import weewx.units
import weewx.defaults
import weewx.xtypes
import weewx.wxformulas
import weewx.uwxutils
from weeutil.weeutil import TimeSpan
from weewx.engine import StdService
from weewx.cheetahgenerator import SearchList
from weewx.tags import TimeBinder, TimespanBinder
from user.dayboundarystats import startOfDayTZ, startOfYearTZ

try:
    # Test for new-style weewx logging by trying to import weeutil.logger
    import weeutil.logger
    import logging
    log = logging.getLogger(__name__)

    def logdbg(msg):
        log.debug(msg)

    def loginf(msg):
        log.info(msg)

    def logerr(msg):
        log.error(msg)

except ImportError:
    # Old-style weewx logging
    import syslog

    def logmsg(level, msg):
        syslog.syslog(level, 'GTS: %s' % msg)

    def logdbg(msg):
        logmsg(syslog.LOG_DEBUG, msg)

    def loginf(msg):
        logmsg(syslog.LOG_INFO, msg)

    def logerr(msg):
        logmsg(syslog.LOG_ERR, msg)

try:
    from user.mqtt import UNIT_REDUCTIONS
    UNIT_REDUCTIONS['degree_C_day'] = 'Kd' # Kelvin days
except ImportError:
    pass

# The following functions are similar to that in weeutil/weeutil.py,
# but honour the timezone tz and do _not_ honour daylight savings time.

def dayOfGTSYear(time_ts,soy_ts):
    """ get the day of the year, starting at 0 for Jan 1st
    
        After May 31st the value of that day applies to all subsequent
        days of that year. 
        
        Returns a value between 0 and 150 as index for self.gts_values[]
        
        Unless archiveYearSpan() and archiveDaySpan() this function
        considers midnight as belonging to the new day. This is
        because those two functions return 00:00:00 as the start
        of the time span. So you can use the result of those 
        functions as the parameter time_ts for dayOfGTSYear().
        
    """
    # time_ts is before the beginning of the year
    # That should never happen in the program, but it is checked for safety.
    if time_ts<soy_ts: return 0
    # time_ts is after May 31st
    if time_ts>=soy_ts+13046400: return 150
    # time_ts is between Jan 1st and May 31st
    return int((time_ts-soy_ts)//86400)

def genDaySpansWithoutDST(start_ts, stop_ts):
    """Generator function that generates start/stop of days
       according to timezone tz"""
    if None in (start_ts, stop_ts): return
    for time_ts in range(int(start_ts),int(stop_ts),86400):
        yield TimeSpan(int(time_ts),int(time_ts+86400))

    
def boilingTemperatureCC(pressure, temp1=99.9743, deltaH=40.657):
    """ boiling temperature of water
    
        https://de.wikipedia.org/wiki/Clausius-Clapeyron-Gleichung
        
        The equation is valid for a invariable enthalpy of
        vaporization, which applies to small temperature
        ranges only.
    """
    p1 = 1013.25 # hPa           Normaldruck
    T1 = temp1+273.15 # K        Siedetemperatur bei Normaldruck
    deltaH *= 1000.0 # J/mol     molare Verdampfungsenthalpie bei 100°C
    R = 8.314462 # J mol^-1 K^-1 universelle Gaskonstante
    temp = 1.0/(1.0/T1 - math.log(pressure/p1)*R/deltaH)-273.15
    return temp


# unit g/m^2 and mg/m^2 for 'group_concentration'
weewx.units.conversionDict.setdefault('microgram_per_meter_cubed',{})
weewx.units.conversionDict.setdefault('milligram_per_meter_cubed',{})
weewx.units.conversionDict.setdefault('gram_per_meter_cubed',{})
weewx.units.conversionDict['gram_per_meter_cubed']['microgram_per_meter_cubed'] = lambda x : x*1000000
weewx.units.conversionDict['milligram_per_meter_cubed']['microgram_per_meter_cubed'] = lambda x : x*1000
weewx.units.conversionDict['microgram_per_meter_cubed']['gram_per_meter_cubed'] = lambda x : x*0.000001
weewx.units.conversionDict['microgram_per_meter_cubed']['milligram_per_meter_cubed'] = lambda x : x*0.001
weewx.units.conversionDict['milligram_per_meter_cubed']['gram_per_meter_cubed'] = lambda x : x*0.001
weewx.units.conversionDict['gram_per_meter_cubed']['milligram_per_meter_cubed'] = lambda x : x*1000
weewx.defaults.defaults['Units']['StringFormats'].setdefault('gram_per_meter_cubed',"%.1f")
weewx.defaults.defaults['Units']['Labels'].setdefault('gram_per_meter_cubed',u" g/m³")
weewx.defaults.defaults['Units']['StringFormats'].setdefault('milligram_per_meter_cubed',"%.1f")
weewx.defaults.defaults['Units']['Labels'].setdefault('milligram_per_meter_cubed',u" mg/m³")

# unit centibar for 'group_moisture'
# Note: The unit 'centibar' is defined in core WeeWX, but no conversion 
#       to other pressure units is defined.
weewx.units.conversionDict.setdefault('centibar',dict())
weewx.units.conversionDict['centibar']['mbar'] = lambda x: x*10.0
weewx.units.conversionDict['centibar']['hPa'] = lambda x: x*10.0
weewx.units.conversionDict['centibar']['kPa'] = lambda x: x
weewx.units.conversionDict['centibar']['mmHg'] = lambda x: x*7.5006168
weewx.units.conversionDict['centibar']['inHg'] = lambda x: x*weewx.units.INHG_PER_MBAR*10.0
weewx.units.conversionDict['mbar']['centibar'] = lambda x: x/10.0
weewx.units.conversionDict['hPa']['centibar'] = lambda x: x/10.0
weewx.units.conversionDict['kPa']['centibar'] = lambda x: x

# unit pF_value for 'group_moisture'
# Note: We assume that the suction pressure of plants physically cannot go 
#       down to 0. So, the logarithm cannot be undefined. Nevertheless,
#       the Davis soil moisture device can return a reading of 0. That's
#       why we have to handle this case. The lower limit of the pF value 
#       as shown in literature is 0.0. For those reasons a pF value of 0.0
#       is returned for all suction pressure readings below 0.1 centibar.
def hPa_to_pF(x):
    if x is None: return None
    return math.log10(abs(x)) if abs(x)>=1.0 else 0.0
weewx.units.conversionDict['centibar']['pF_value'] = lambda x: hPa_to_pF(x*10)
weewx.units.conversionDict['mbar']['pF_value'] = hPa_to_pF
weewx.units.conversionDict['hPa']['pF_value'] = hPa_to_pF
weewx.units.conversionDict['kPa']['pF_value'] = lambda x: hPa_to_pF(x*10)
weewx.defaults.defaults['Units']['StringFormats'].setdefault('pF_value','%.1f')
weewx.defaults.defaults['Units']['Labels'].setdefault('pF_value',u'')

class GTSType(weewx.xtypes.XType):

    # default growing degree days base and limit temperature
    GDD_BASE_VT = weewx.units.ValueTuple(10.0,'degree_C','group_temperature')
    GDD_LIMIT_VT = weewx.units.ValueTuple(30.0,'degree_C','group_temperature')

    def __init__(self,lat,lon,svp_config):

        # class XType has no constructor
        #super(GTSType,self).__init()
        
        # remember the station's location and determine the timezone
        # data for local mean time (LMT)
        self.latlon=(lat,lon)
        try:
            self.timeoffset=datetime.timedelta(seconds=lon*240)
            self.lmt_tz=datetime.timezone(self.timeoffset,"LMT")
        except ValueError:
            # Python before 3.7 requires timedelta to be whole minutes
            logerr("local time rounded to whole minutes. Use Python>=3.7 to prevent that")
            self.timeoffset = datetime.timedelta(minutes=(lon*240)//60)
            self.lmt_tz = datetime.timezone(self.timeoffset,"LMT")
            
        # possible values: vaDavisVp, vaBuck, vaBuckB1, vaBolton, vaTetenNWS, vaTetenMurray, vaTeten
        self.svp_method = svp_config.get('method','vaBolton')

        # attributes to save calculted values
        self.last_gts_date=None # last date GTS is calculated for
        self.gts_date={}        # the date when GTS exceeds 200
        self.gts_value=None     # last GTS value calculated
        self.gts_values={}      # calculated GTS values
        
        # register the values with WeeWX
        # GTS
        weewx.units.obs_group_dict.setdefault('GTS','group_degree_day')
        weewx.units.obs_group_dict.setdefault('GTSdate','group_time')
        weewx.units.obs_group_dict.setdefault('LMTtime','group_time')
        weewx.units.obs_group_dict.setdefault('utcoffsetLMT','group_deltatime')
        # GDD
        weewx.units.obs_group_dict.setdefault('yearGDD','group_degree_day')
        weewx.units.obs_group_dict.setdefault('seasonGDD','group_degree_day')
        weewx.units.agg_group.setdefault('GDD','group_degree_day')
        weewx.units.agg_group.setdefault('growdeg','group_degree_day')
        # ET
        weewx.units.obs_group_dict.setdefault('dayET','group_rain')
        weewx.units.obs_group_dict.setdefault('ET24','group_rain')
        # radiation integral
        weewx.units.agg_group.setdefault('energy_integral','group_radiation_energy')
        weewx.units.USUnits.setdefault('group_radiation_energy','watt_hour_per_meter_squared')
        weewx.units.MetricUnits.setdefault('group_radiation_energy','watt_hour_per_meter_squared')
        weewx.units.MetricWXUnits.setdefault('group_radiation_energy','watt_hour_per_meter_squared')
        weewx.units.default_unit_format_dict.setdefault('watt_hour_per_meter_squared',"%.0f")
        weewx.units.default_unit_label_dict.setdefault('watt_hour_per_meter_squared',u" Wh/m²")
        weewx.units.default_unit_format_dict.setdefault('kilowatt_hour_per_meter_squared',"%.3f")
        weewx.units.default_unit_label_dict.setdefault('kilowatt_hour_per_meter_squared',u" kWh/m²")
        if 'watt_hour_per_meter_squared' not in weewx.units.conversionDict:
            weewx.units.conversionDict['watt_hour_per_meter_squared']={}
        if 'kilowatt_hour_per_meter_squared' not in weewx.units.conversionDict:
            weewx.units.conversionDict['kilowatt_hour_per_meter_squared']={}
        weewx.units.conversionDict['watt_hour_per_meter_squared']['kilowatt_hour_per_meter_squared']= lambda x : x / 1000.0
        weewx.units.conversionDict['kilowatt_hour_per_meter_squared']['watt_hour_per_meter_squared']= lambda x : x * 1000.0
        # saturation vapor pressure
        weewx.units.obs_group_dict.setdefault('outSVP','group_pressure')
        # acutal vapor pressure
        weewx.units.obs_group_dict.setdefault('outVaporP','group_pressure')
        # absolute humidity
        weewx.units.obs_group_dict.setdefault('outHumAbs','group_concentration')
        # mixing ratio
        for ii in weewx.units.std_groups:
            weewx.units.std_groups[ii].setdefault('group_mixingratio','gram_per_kilogram')
        weewx.units.default_unit_format_dict.setdefault('gram_per_kilogram',"%.1f")
        weewx.units.default_unit_label_dict.setdefault('gram_per_kilogram',u" g/kg")
        weewx.units.obs_group_dict.setdefault('outMixingRatio','group_mixingratio')
        # equivalent temperature, equivalent potential temperature
        weewx.units.obs_group_dict.setdefault('outEquiTemp','group_temperature')
        weewx.units.obs_group_dict.setdefault('outThetaE','group_temperature')
        # boiling point
        weewx.units.obs_group_dict.setdefault('boilingTemp','group_temperature')
        
        # lock that makes calculation atomic
        self.lock=threading.Lock()
        
        # to log some error messages only once
        self.record_ok=True
        self.db_manager_ok=True
        
        loginf("Version %s" % VERSION)
        loginf("Local mean time (LMT) UTC offset %s" % str(self.timeoffset))
        
                
    def __calc_gts(self, soy_ts, db_manager):
        """ calculate GTS and GTSdate for the year of soy_ts 
        
            soy_ts must be Jan 1st 00:00:00 of the year the values
            are to be calculated for
            
        """
        
        # We need the year from Jan 1st on to calculate something.
        if not db_manager.first_timestamp: return
        if soy_ts<db_manager.first_timestamp: return
        # If the timestamp is far in future, there is nothing to calculate.
        if soy_ts>time.time(): return
        
        #loginf("calculate GTS for the year %s" % time.strftime("%Y",time.localtime(soy_ts)))
        
        # this year or a past year
        __this_year = (-1 <= (soy_ts-startOfYearTZ(db_manager.last_timestamp,self.lmt_tz)) <= 1) or soy_ts>db_manager.last_timestamp
        
        if __this_year:
            # this year: calculate until today
            _sod_ts=startOfDayTZ(time.time(),soy_ts)
            #loginf("this year %s" % time.strftime("%Y-%m-%d",time.localtime(_sod_ts)))
            if soy_ts not in self.gts_values:
                # no value calculated for this year so far --> initialize
                self.last_gts_date=soy_ts
                self.gts_value=0
                self.gts_values[soy_ts]=[None]*151
                try:
                    loginf("GTS initialized %s" %
                       datetime.datetime.fromtimestamp(soy_ts,None).strftime("%Y-%m-%d %H:%M:%S %Z"))
                    #except (NameError,TypeError,ValueError,IndexError) as e:
                except Exception:
                    pass
            # get the last values calculated for this year
            __ts=self.last_gts_date
            __gts=self.gts_value
        else:
            # other year: calculate until end of May
            if soy_ts in self.gts_values:
                # values of the given year are already calculated
                # nothing to do
                return
            # calculate from Jan 1st to May 31st
            _sod_ts=soy_ts+13046400
            loginf("other year %s" % time.strftime("%Y-%m-%d",time.localtime(_sod_ts)))
            self.gts_values[soy_ts]=[None]*151
            __ts=soy_ts
            __gts=0
            
        # needed timestamps
        # Note: Without '+1' archiveYearSpan() returns the previous year,
        #       if _sod_ts is the beginning of a year. As _sod_ts is
        #       always the beginning of a day and the beginning of the 
        #       last day of the year is 24 hours before the new year, there 
        #       is no problem to add 1 second.
        _soy_ts=startOfYearTZ(_sod_ts+1,self.lmt_tz) # start of year
        _feb_ts=_soy_ts+2678400 # Feb 1
        _mar_ts=_feb_ts+2419200 # Mar 1 (or Feb 29 in leap year)
        _end_ts=_mar_ts+7948800 # Jun 1 (or May 31 in leap year)
        
        # debugging output
        if __ts<_sod_ts:
            logdbg("timestamps %s %s %s %s %s" % (
                        time.strftime("%Y",time.localtime(_soy_ts)),
                        time.strftime("%d.%m.",time.localtime(_soy_ts)),
                        time.strftime("%d.%m.",time.localtime(_feb_ts)),
                        time.strftime("%d.%m.",time.localtime(_mar_ts)),
                        time.strftime("%d.%m.",time.localtime(_end_ts))))
        
        # calculate
        # This runs one loop for every day since New Year at program 
        # start and after that once a day one loop, only. After May 31st
        # no loop is executed.
        _loop_ct=0
        while __ts < _sod_ts and __ts < _end_ts:
            # the day the average is calculated for
            _today = TimeSpan(__ts,__ts+86400)
            # calculate the average of the outside temperature
            _result = weewx.xtypes.get_aggregate('outTemp',_today,'avg',db_manager)
            # convert to centrigrade
            if _result is not None:
                _result = weewx.units.convert(_result,'degree_C')
            # check condition and add to sum
            if _result is not None and _result[0] is not None:
                _dayavg = _result[0]
                if _dayavg > 0:
                    if __ts < _feb_ts:
                        _dayavg *= 0.5
                    elif __ts < _mar_ts:
                        _dayavg *= 0.75
                    logdbg("loop no. %s, day value %s" % (_loop_ct,_dayavg))
                    __gts += _dayavg
                    if __gts >= 200 and soy_ts not in self.gts_date:
                        self.gts_date[soy_ts] = __ts
                # save the value for subsequent calls
                self.gts_values[soy_ts][dayOfGTSYear(__ts,_soy_ts)]=__gts
            # logging
            #__mday=_loop_ct+1 if __ts<_feb_ts else _loop_ct-30
            #__vv=_result[0] if not None and _result[0] is not None else None
            #loginf("loop no. %s, mday %2s, %.2f GTS so far %s" % (_loop_ct,__mday,__vv,__gts))
            # next day
            __ts+=86400
            _loop_ct+=1

        # loop is run at least once, so log and remember values
        # (This happens after the start of WeeWX and later on at
        # the beginning of a new day.)
        if _loop_ct>0:
            loginf("GTS %s, %s loops" % (__gts,_loop_ct))

            if __this_year:
                # remember the date and value of the last calculation
                # to continue calculation on the next day
                # Note: this value is used for $current.GTS
                self.gts_value=__gts
                self.last_gts_date=__ts

            
    def calc_gts(self, soy_ts, db_manager):
        """ lock against parallel calls to that funtion and calculate GTS """
        try:
            self.lock.acquire()
            self.__calc_gts(soy_ts,db_manager)
        finally:
            self.lock.release()
    
    
    def get_gts(self, obs_type, sod_ts, soy_ts):
        """ read GTS value out of the array """
    
        if obs_type=='GTS':
            # Gruenlandtemperatursumme GTS
            try:
                if soy_ts is None or soy_ts not in self.gts_values:
                    __x = None
                else:
                    __x = self.gts_values[soy_ts][dayOfGTSYear(sod_ts,soy_ts)]
                return weewx.units.ValueTuple(__x,'degree_C_day','group_degree_day')
            except (ValueError,TypeError,IndexError,KeyError):
                logerr("soy_ts=%s sod_ts=%s" % (soy_ts,sod_ts))
                raise weewx.CannotCalculate(obs_type)
        elif obs_type=='GTSdate':
            # date of value 200
            if soy_ts is None or soy_ts not in self.gts_date:
                return weewx.units.ValueTuple(None,'unix_epoch','group_time')
            else:
                return weewx.units.ValueTuple(self.gts_date[soy_ts],'unix_epoch','group_time')
        else:
            # unknown type (should not happen here)
            raise weewx.UnknownType(obs_type)


    def get_scalar(self, obs_type, record, db_manager, **option_dict):
        """ mandatory function to be defined for XType extensions """

        if obs_type is None:
            raise weewx.UnknownType("obs_type is None")
        
        # time offset of local mean time (LMT)
        if obs_type=='utcoffsetLMT':
            return weewx.units.ValueTuple(self.lmt_tz.utcoffset(None).total_seconds(),'second','group_deltatime')

        # dateTime as string in local mean time
        if obs_type=='LMTtime':
            if record is None: raise weewx.UnknownType("%s: no record" % obs_type)
            return weewx.units.ValueTuple(datetime.datetime.fromtimestamp(record['dateTime'],self.lmt_tz).strftime("%H:%M:%S"),
                    'unix_epoch','group_time')
        
        # equivalent temperature, equivalent potential temperature
        # https://www.dwd.de/DE/service/lexikon/begriffe/A/Aequivalenttemperatur_pdf.pdf?__blob=publicationFile&v=7
        # https://www.dwd.de/DE/service/lexikon/begriffe/P/Potentielle_Aequivalenttemperatur_pdf.pdf;jsessionid=96ACA333AE2C96198E3B0AC77300EAC9.live21073?__blob=publicationFile&v=5
                
        # saturation vapor pressure, actual vapar pressure, mixing ratio,
        # and absolute humidity
        if obs_type in ('outSVP','outVaporP','outHumAbs','outMixingRatio',
                        'outEquiTemp','outThetaE'):
            #_result = weewx.xtypes.get_scalar('outTemp',record,db_manager)
            try:
                # If record is None or `outTemp` not in record, then
                # a ValueTuple with the value of None is returned
                _result = weewx.units.as_value_tuple(record,'outTemp')
                # If _result represents a value of None, temp_C is None, too.
                temp_C = weewx.units.convert(_result,'degree_C')[0]
                method = option_dict.get('method',self.svp_method)
                if obs_type=='outSVP':
                    # saturation vapor pressure
                    svp = weewx.uwxutils.TWxUtils.SaturationVaporPressure(temp_C,method)
                else:
                    _result = weewx.units.as_value_tuple(record,'outHumidity')
                    hum = weewx.units.convert(_result,'percent')[0]
                    if obs_type in ['outVaporP','outHumAbs']:
                        # actual vapor pressure
                        svp = weewx.uwxutils.TWxUtils.ActualVaporPressure(temp_C,hum,method)
                        # absolute humidity
                        if obs_type=='outHumAbs' and svp is not None:
                            svp = svp / 4.6152 / (temp_C+273.15) * 1e9
                    else:
                        # MixingRatio
                        _result = weewx.units.as_value_tuple(record,'pressure')
                        p = weewx.units.convert(_result,'hPa')[0]
                        svp = weewx.uwxutils.TWxUtils.MixingRatio(p,temp_C,hum)
                        if obs_type!='outMixingRatio':
                            # equivalent temperature
                            r = svp*1e-3
                            L = 2500.78 - 2.325734 * temp_C
                            svp = temp_C+r*(L/(1.00482+r*4.18674))
                            if obs_type=='outThetaE':
                                # equivalent potential temperature
                                svp = (svp+273.15)*((1000/p)**(287.05/1004.82))-273.15
            except (LookupError,TypeError):
                svp = None
            if obs_type=='outHumAbs':
                __unit = 'microgram_per_meter_cubed'
                __unitgroup = 'group_concentration'
            elif obs_type=='outMixingRatio':
                __unit = 'gram_per_kilogram'
                __unitgroup = 'group_mixingratio'
            elif obs_type in ('outEquiTemp','outThetaE'):
                __unit = 'degree_C'
                __unitgroup = 'group_temperature'
            else:
                __unit = 'hPa'
                __unitgroup = 'group_pressure'
            __x = weewx.units.ValueTuple(svp,__unit,__unitgroup)
            if record is None: return __x
            # see https://github.com/weewx/weewx/issues/781
            return weewx.units.convertStd(__x,record['usUnits'])
        
        if obs_type=='boilingTemp':
            try:
                _result = weewx.units.as_value_tuple(record,'pressure')
                pressure_mbar = weewx.units.convert(_result,'hPa')[0]
                method = option_dict.get('algorithm','CC')
                btemp_C = boilingTemperatureCC(pressure_mbar)
                usunits = record['usUnits']
            except (LookupError,TypeError,ValueError,ArithmeticError):
                btemp_C = None
                usunits = 0x10
            __x = weewx.units.ValueTuple(btemp_C,'degree_C','group_temperature')
            return weewx.units.convertStd(__x,usunits)
                
        # This functions handles 'GTS' and 'GTSdate'.
        if obs_type not in ['GTS','GTSdate','dayET','ET24','yearGDD','seasonGDD']:
            raise weewx.UnknownType(obs_type)
        
        #if record is None:
        #    if self.record_ok: 
        #        logerr("%s: no record (logged only once)" % obs_type)
        #        self.record_ok=False
        #    raise weewx.CannotCalculate("%s: no record" % obs_type)
        if db_manager is None:
            if self.db_manager_ok:
                logerr("%s: db_manager is None" & obs_type)
                self.db_manager_ok=False
            raise weewx.CannotCalculate("%s: no database reference" % obs_type)

        #logdbg("obs_type=%s" % obs_type)
        
        # needed timestamps
        if record is not None and 'dateTime' in record:
            _time_ts=record['dateTime']
        else:
            # that should never happen but does due to a bug in 
            # Belchertown skin
            if self.record_ok: 
                logerr("%s: no record (logged only once)" % obs_type)
                self.record_ok=False
            # to do something we deliver the last available value
            _time_ts=time.time()

        if obs_type=='dayET':
            # dayET should be comparable to dayRain, so use the same
            # time span: not local mean time but archive time
            try:
               # startOfArchiveDay() considers midnight belonging
               # to the previous day. So the time span would be
               # always greater than 0.
               __x=weeutil.weeutil.startOfArchiveDay(_time_ts)
               __x=weeutil.weeutil.TimeSpan(__x,_time_ts)
            except (ValueError,TypeError,IndexError):
               raise weewx.CannotCalculate("dayET: invalid time")
            return weewx.xtypes.get_aggregate('ET',__x,'sum',db_manager)
        
        if obs_type=='ET24':
            try:
                __x=weeutil.weeutil.TimeSpan(_time_ts-86400,_time_ts)
            except:
                raise weewx.CannotCalculate("ET24: invalid time")
            return weewx.xtypes.get_aggregate('ET',__x,'sum',db_manager)
            
            
        _soy_ts=startOfYearTZ(_time_ts,self.lmt_tz)
        _sod_ts=startOfDayTZ(_time_ts,_soy_ts) # start of day
        
        #try:
        #    if _soy_ts>1654120800 or _sod_ts>1654120800:
        #        loginf("_soy_ts %s, _sod_ts %s, _time_ts %s" % (_soy_ts,_sod_ts,_time_ts))
        #except Exception as e:
        #    logerr(e)
        
        # If the start of the year in question is before the first
        # record in the database, no value can be calculated. The
        # same applies if the given timestamp is in future.
        #if _soy_ts<db_manager.first_timestamp or _sod_ts>db_manager.last_timestamp:
        #    raise weewx.CannotCalculate(obs_type)
        if not db_manager.first_timestamp or not db_manager.last_timestamp:
            return weewx.units.ValueTuple(None,'degree_C_day','group_degree_day')
            
        # growing degree days == Wachstumsgradtage
        # https://de.wikipedia.org/wiki/Wachstumsgradtag
        # https://en.wikipedia.org/wiki/Growing_degree-day
        if obs_type in ['yearGDD']:
            try:
                # calculate from the beginning of the year up to the
                # end of the current day
                __timespan = TimeSpan(_soy_ts,_sod_ts+86400)
                return self.get_aggregate('outTemp',__timespan,'GDD',db_manager,**option_dict)
            except (ValueError,TypeError,IndexError,KeyError):
                raise weewx.CannotCalculate("%s" % obs_type)

        # calculate GTS values for the given year 
        # (if record['dateTime'] is within the current year, the
        # value is calculated up to the current day (today))
        self.calc_gts(_soy_ts,db_manager)
        
        # growing degree days == Wachstumsgradtage
        # https://de.wikipedia.org/wiki/Wachstumsgradtag
        # https://en.wikipedia.org/wiki/Growing_degree-day
        if obs_type in ['seasonGDD']:
            try:
                # calculate from the beginning of the year up to the
                # end of the current day
                __start_ts = self.gts_date[_soy_ts]
                if __start_ts and _sod_ts>=__start_ts and _sod_ts<_soy_ts+26179200:
                    __timespan = TimeSpan(__start_ts,_sod_ts+86400)
                    return self.get_aggregate('outTemp',__timespan,'GDD',db_manager,**option_dict)
            except (ValueError,TypeError,IndexError,KeyError):
                #raise weewx.CannotCalculate("%s" % obs_type)
                pass
            return weewx.units.ValueTuple(None,'degree_C_day','group_degree_day')

        # check if the requested timestamp record['dateTime'] is within
        # the current day (today)
        # Note: After self.calc_gts() is run, self.last_gts_date
        #       points to the beginning of the current day, if 
        #       record['dateTime'] is within the current year.
        #       if record['dateTime'] is _not_ within the current
        #       year, self.last_gts_date _may_ be None. 
        if record is None:
            # record is not provided, we assume the actual time
            # Note: That should not happen but does due to a bug in
            #       Belchertown skin
            if _sod_ts!=self.last_gts_date:
                raise weewx.CannotCalculate("%s: no record" % obs_type)
            __today=True
        elif self.last_gts_date is None or self.gts_value is None:
            # The current year is not calculated so far, that means, 
            # record['dateTime'] cannot be within the current day (today).
            __today=False
        elif _time_ts<=self.last_gts_date:
            # record['dateTime'] is before self.last_gts_date.
            # As self.last_gts_date points to the beginning of
            # the current day, that means, record['dateTime'] is not 
            # the current day (today).
            __today=False
        else:
            # record['dateTime'] is after the beginning of the
            # current day. If it is additionally before
            # self.last_gts_date+86400 (1d after), it is within
            # the current day (today).
            __today=_time_ts<=self.last_gts_date+86400

        # get the result
        if __today:
            # current value
            if obs_type=='GTS':
                # current GTS value
                __x=weewx.units.ValueTuple(
                            self.gts_value,'degree_C_day','group_degree_day')
            elif obs_type=='GTSdate':
                # current GTSdate value or None, if GTS<200
                if _soy_ts in self.gts_date:
                    __x=self.gts_date[_soy_ts]
                else:
                    __x=None
                __x=weewx.units.ValueTuple(__x,'unix_epoch','group_time')
            else:
                # should not occure
                raise weewx.CannotCalculate(obs_type)
        else:
            # value from memory
            __x=self.get_gts(obs_type,_sod_ts,_soy_ts)
        """
        try:
          a=str(__x[0])
        except:
          logerr("get_scalar 0")
          a=""
        try:
          b=str(__x[1])
        except:
          logerr("get_scalar 1")
          b=""
        try:
          c=str(__x[2])
        except:
          logerr("get_scalar 2")
          c=""
        loginf("get_scalar %s,%s,%s" % (a,b,c))
        """
        if record is None: return __x
        return weewx.units.convertStd(__x,record['usUnits'])

        
    def calc_radiation_integral(self,obs_type,timespan,db_manager):
        """calculate radiation integral over time
        
        radiation: actual radiation in Watt per square meter
        interval:  registration interval as per database record in minutes
        
        Note: 'interval' needs to be included in backticks '`' in
              order to work with MySQL
        """

        try:
            _result = db_manager.getSql(
                    "SELECT SUM(%s*`interval`)/60.0, "
                    "MIN(usUnits),MAX(usUnits) FROM %s "
                    "WHERE dateTime>? AND dateTime<=?"
                    % (obs_type,db_manager.table_name),timespan)
            if _result is None:
                raise weewx.CannotCalculate("calculate energy: no %s data in database" % obs_type)
            # get the unit system
            if _result[0] is not None:
                # There are records within the time span, so there is a
                # result
                if not _result[1] == _result[2]:
                    raise weewx.CannotCalculate("calculate energy: inconsistent units")
                if weewx.debug >= 2:
                    logdbg("radiation integral %s %.1f" % (obs_type,_result[0]))
                #loginf("radiation integral %.1f" % _result[0])
                _usUnits = _result[1]
            else:
                # There are no records within the time span --> try to
                # determine the unit system otherwise.
                _usUnits = db_manager.std_unit_system
            # find the unit and unit group for the integrated value
            if _usUnits is not None:
                # The unit system could be determined, so get the actual
                # unit and add 'hour' to it.
                _unit,_group = weewx.units.getStandardUnitType(_usUnits,obs_type)
                #loginf("unit %s" % _unit[0])
                #loginf("unit %s" % _unit[1])
                if not _unit:
                    raise weewx.CannotCalculate("calculate energy: invalid unit")
                elif _unit=='watt_per_meter_squared':
                    _unit='watt_hour_per_meter_squared'
                elif _unit=='watt':
                    _unit = 'watt_hour'
                elif _unit=='kilowatt':
                    _unit = 'kilowatt_hour'
                # find the unit group for the integrated value
                if not _group:
                    raise weewx.CannotCalculate("calculate energy: invalid unit group")
                elif _group=='group_radiation':
                    _group = 'group_radiation_energy'
                elif _group=='group_power':
                    _group = 'group_energy'
                #loginf("unit %s" % _unit)
            else:
                _unit='watt_hour_per_meter_squared'
                _group='group_radiation_energy'
            return weewx.units.ValueTuple(_result[0],_unit,_group)
        except weedb.OperationalError as e:
            raise weewx.CannotCalculate("calculate energy: Database OperationalError '%s'" % e)
        except (ValueError, TypeError) as e:
            raise weewx.CannotCalculate("calculate energy: %s" % e)
        return None


    def calc_GDD_integral(self,obs_type,timespan,db_manager,base_t,limit_t,stop_t):
        """ calculate growing degree days as integral over time"""
        try:
            # make sure limit_t and stop_t are not None
            if not limit_t: limit_t = 1000.0
            if not stop_t: stop_t = 1000.0
            logdbg("GDD integral base=%s limit=%s stop=%s" % (base_t,limit_t,stop_t))
            # maximum growing degree value
            __gdlimit = limit_t - base_t
            # query data base and calculate integral
            _result = db_manager.getSql(
                           'SELECT sum('
                           '  CASE'
                           '    WHEN `%s`>%.1f THEN 0.0'
                           '    WHEN `%s`>%.1f THEN %.1f'
                           '    WHEN `%s`<%.1f THEN 0.0'
                           '    ELSE `%s`-%.1f'
                           '  END*`interval`/1440.0),'
                           '  MIN(usUnits),MAX(usUnits) '
                           'FROM %s '
                           'WHERE dateTime>? AND dateTime<=?'
                    % (obs_type,stop_t,
                       obs_type,limit_t,__gdlimit,
                       obs_type,base_t,
                       obs_type,base_t,
                       db_manager.table_name),timespan)
            if _result is None:
                raise weewx.CannotCalculate("calculate GDD: no temperature data in database")
            if _result[0] is not None:
                if not _result[1] == _result[2]:
                    raise weewx.CannotCalculate("calculate GDD: inconsistent units")
            _unit,_ugroup=weewx.units.getStandardUnitType(_result[1],obs_type,'GDD')
            logdbg("GDD integral unit=%s unitgroup=%s" % (_unit,_ugroup))
            return weewx.units.ValueTuple(_result[0],_unit,_ugroup)
        except weedb.OperationalError as e:
            raise weewx.CannotCalculate("calculate GDD integral: Database OperationalError '%s'" % e)
        except (ValueError, TypeError) as e:
            raise weewx.CannotCalculate("calculate GDD integral: %s" % e)
        return None


    def __genDaySpans(self, withoutdst, start_ts, stop_ts):
        if withoutdst:
            # return day spans in Local Mean Time
            return genDaySpansWithoutDST(start_ts, stop_ts)
        # otherwise return day spans in local timezone time
        return weeutil.weeutil.genDaySpans(start_ts, stop_ts)


    def gen_GDD_avg(self,obs_type,timespan,db_manager,method,base_t,limit_t,stop_t,islmt):
        """ calculate growing degree days based on the average of
            minimum and maximum temperature of the day or based of
            the average temperature of the day"""
        if not limit_t: limit_t = 1000.0
        if not stop_t: stop_t = 1000.0
        count = 0
        try:
          for daySpan in self.__genDaySpans(islmt, timespan.start, timespan.stop):
            #loginf(daySpan)
            if method=='dayavg':
                # method 'dayavg'
                # Get avg temperature for the day as a value tuple
                Tavg_t = weewx.xtypes.get_aggregate(obs_type, daySpan, 'avg', db_manager)
                # Make sure it's valid before including it in the aggregation:
                if Tavg_t is not None and Tavg_t[0] is not None:
                    avg_t = Tavg_t[0]
                else:
                    avg_t = None
            else:
                # method 'hiloavgA' and 'hiloavgB'
                # Get min and max temperature for the day as a value tuple
                #loginf("a")
                Tmax_t = weewx.xtypes.get_aggregate(obs_type, daySpan, 'max', db_manager)
                #loginf("b")
                Tmin_t = weewx.xtypes.get_aggregate(obs_type, daySpan, 'min', db_manager)
                #loginf("c")
                # Make sure it's valid before including it in the aggregation:
                if Tmax_t is not None and Tmax_t[0] is not None and Tmin_t is not None and Tmin_t[0] is not None:
                    if method=='hiloavgB'  and Tmin_t[0]<base_t:
                        Tmin_t = weewx.units.ValueTuple(base_t, Tmin_t[1], Tmin_t[2])
                    # average of daily max and min temperature
                    avg_t = (Tmax_t[0]+Tmin_t[0])/2
                else:
                    avg_t = None
            if avg_t is not None:
                # if the average is above upper limit set it to upper limit
                if limit_t is not None and avg_t>limit_t: avg_t = limit_t
                yield daySpan, weewx.wxformulas.cooling_degrees(avg_t,base_t)
                count += 1
        except Exception as e:
          logerr(e)

    def calc_GDD_avg(self,obs_type,timespan,db_manager,method,base_t,limit_t,stop_t,islmt):
        """ calculate growing degree days based on the average of
            minimum and maximum temperature of the day or based of
            the average temperature of the day"""
        total = 0.0
        count = 0
        try:
            for _, day_val in self.gen_GDD_avg(obs_type,timespan,db_manager,method,base_t,limit_t,stop_t,islmt):
                total += day_val
                count += 1
        except Exception as e:
          logerr(e)
        if count>0:
            value = total
        else:
            value = None
        # Look up the unit type and group of the result:
        t, g = weewx.units.getStandardUnitType(db_manager.std_unit_system, 
                                               obs_type, 'GDD')
        # Return as a value tuple
        return weewx.units.ValueTuple(value, t, g)
    
    
    def calc_derived(self, obs_type, timespan, aggregate_type, db_manager, **option_dict):
        """ calculate aggreation of derived observation types """
        try:
            if aggregate_type in ('min','mintime'):
                val = 1e10
            elif aggregate_type in ('max','maxtime'):
                val = -1e10
            else:
                val = 0.0
            n = 0
            valtime = None
            _x = (None,None,None)
            for _result in db_manager.genSql(
                    "SELECT `dateTime`,`usUnits`,"
                    "`outTemp`,`outHumidity`,`pressure` "
                    "from %s WHERE dateTime>? AND dateTime<=? "
                    "ORDER BY `dateTime`"
                    % db_manager.table_name,timespan):
                if _result is None:
                    raise weewx.CannotCalculate("%s.%s: no data in database" % (obs_type,aggregate_type))
                _rec = {
                    'dateTime':_result[0],
                    'usUnits':_result[1],
                    'outTemp':_result[2],
                    'outHumidity':_result[3],
                    'pressure':_result[4]}
                _x = self.get_scalar(obs_type, _rec, db_manager, **option_dict)
                if _x[0] is not None: 
                    n += 1
                    if aggregate_type in ('count','not_null'):
                        pass
                    elif aggregate_type in ('avg','sum'):
                        val += _x[0]
                    elif aggregate_type in ('min','mintime'):
                        if _x[0]<val: 
                            val = _x[0]
                            valtime = _result[0]
                    elif aggregate_type in ('max','maxtime'):
                        if _x[0]>val: 
                            val = _x[0]
                            valtime = _result[0]
                    elif aggregate_type=='last':
                        val = _x[0]
                        valtime = _result[0]
                    else:
                        raise weewx.UnknownType("%s.%s: unknown aggregation type" % (obs_type,aggregate_type))
            if aggregate_type in ('not_null'):
                return weewx.units.ValueTuple(n>0,'boolean','group_boolean')
            if aggregate_type=='count':
                return weewx.units.ValueTuple(n,'count','group_count')
            if 'time' in aggregate_type:
                return weewx.units.ValueTuple(valtime,'unix_epoch','group_time')
            if n==0:
                _x = self.get_scalar(obs_type, None, None, **option_dict)
                val = _x[0]
            elif aggregate_type=='avg': 
                val /= n
            return weewx.units.ValueTuple(val,_x[1],_x[2])
        except weedb.OperationalError as e:
            raise weewx.CannotCalculate("%s.%s: Database OperationalError '%s'" % (obs_type,aggregate_type,e))
        except (ValueError, TypeError, ArithmeticError, LookupError) as e:
            raise weewx.CannotCalculate("%s.%s: %s" % (obs_type,aggregate_type,e))
        return None
        
        
    def get_aggregate(self, obs_type, timespan, aggregate_type, db_manager, **option_dict):

        if obs_type is None:
            raise weewx.UnknownType("obs_type is None")
            
        # time offset of local mean time (LMT)
        if obs_type=='utcoffsetLMT':
            return weewx.units.ValueTuple(self.lmt_tz.utcoffset(None).total_seconds(),'second','group_deltatime')
        
        # energy_integral can be calculated for group_radiation observation 
        # types like 'radiation' and 'maxSolarRad'
        if aggregate_type=='energy_integral':
            if weewx.units.obs_group_dict.get(obs_type) in ('group_radiation','group_power'):
                return self.calc_radiation_integral(obs_type,timespan,db_manager)
        
        # growing degree days == Wachstumsgradtage
        # https://de.wikipedia.org/wiki/Wachstumsgradtag
        # https://en.wikipedia.org/wiki/Growing_degree-day
        if aggregate_type in ['growdeg','GDD']:
            # growing degree day can only be calculated for a temperature
            if weewx.units.obs_group_dict.get(obs_type,'')!='group_temperature':
                raise weewx.CannotCalculate("%s is not temperature for aggregation %s" % (obs_type,aggregate_type))
            # if the base value is defined in skin.conf or weewx.conf, get
            # it for default
            units_dict = option_dict.get('skin_dict', {}).get('Units', {})
            dd_dict = units_dict.get('DegreeDays', {})
            base_vt = dd_dict.get('growing_base', weewx.xtypes.AggregateHeatCool.default_growbase)
            # if parameters are specified get them
            val = option_dict.get('val')
            #loginf("%s" % type(val))
            #loginf(val)
            if val:
                # GDD with parameters
                try:
                    # dict
                    method = val.get('method','integral')
                    base_vt = val.get('base',base_vt)
                    limit_vt = val.get('limit',self.GDD_LIMIT_VT)
                    stop_vt = val.get('stop')
                except TypeError:
                    # tuple used as base temperature
                    base_vt = weewx.units.ValueTuple(float(val[0]),val[1],'group_temperature')
                    limit_vt = None
                    stop_vt = None
                    method = 'integral'
            else:
                # GDD alone: use defaults
                # Note: base_vt is set before.
                method = 'integral'
                limit_vt = self.GDD_LIMIT_VT
                stop_vt = None
            # Convert to a ValueTuple in the same unit system as the database
            __base = weewx.units.convertStd(
                         (float(base_vt[0]),base_vt[1],'group_temperature'),
                         db_manager.std_unit_system)[0]
            if limit_vt:
                try:
                    __limit = weewx.units.convertStd(
                         (float(limit_vt[0]),limit_vt[1],'group_temperature'),
                         db_manager.std_unit_system)[0]
                except IndexError:
                    if limit_vt.lower()=='none': __limit = None
            else:
                __limit = None
            if stop_vt:
                try:
                    __stop = weewx.units.convertStd(
                         (float(stop_vt[0]),stop_vt[1],'group_temperature'),
                         db_manager.std_unit_system)[0]
                except IndexError:
                    if stop_vt.lower()=='none': __stop = None
            else:
                __stop = None
            #loginf("method %s" % method)
            #loginf(base_vt)
            #loginf(limit_vt)
            # calculate GDD sum
            if method=='integral':
                # integral over timespan
                return self.calc_GDD_integral(obs_type,timespan,db_manager,__base,__limit,__stop)
            if method in ['hiloavgA','hiloavgB','dayavg']:
                # based on daily average or average of high and low.
                # Check if day border should be based on Local Mean Time
                # or local timezone time
                __lmt_tz = option_dict.get('LMT',{}).get('timezone')
                if __lmt_tz is None:
                    __lmt_tz = option_dict.get('dayboundary',{}).get('timezone')
                return self.calc_GDD_avg(obs_type,timespan,db_manager,method,__base,__limit,__stop,__lmt_tz)
            if method=='weewx' and obs_type=='outTemp':
                # call builtin method of WeeWX for outTemp
                return weewx.xtypes.get_aggregate('growdeg',timespan,'sum',db_manager,**option_dict)
            raise weewx.CannotCalculate("GDD %s: unknown method" % method)
        
        # accumulated growing degree days
        if obs_type=='yearGDD' or obs_type=='seasonGDD':
            #loginf("GDD %s" % option_dict)
            #loginf("GDD %s.%s" % (obs_type,aggregate_type))
            if aggregate_type.lower()=='mintime':
                return weewx.units.ValueTuple(timespan.start,'unix_epoch','group_time')
            if aggregate_type.lower()=='maxtime':
                return weewx.units.ValueTuple(timespan.stop,'unix_epoch','group_time')
            if aggregate_type.lower()=='sum':
                raise weewx.CannotCalculate("sum aggregation makes no sense for %s" % obs_type)
            if aggregate_type.lower()=='avg':
                if timespan.start>time.time() or (timespan.start/2+timespan.stop/2)>time.time()+90000:
                    return weewx.units.ValueTuple(None,'degree_C_day','group_degree_days')
                return self.get_scalar(obs_type,{'dateTime':(timespan.start/2+timespan.stop/2)},db_manager,**option_dict)
            if aggregate_type.lower()=='min':
                return self.get_scalar(obs_type,{'dateTime':timespan.start},db_manager,**option_dict)
            if aggregate_type.lower()=='max':
                return self.get_scalar(obs_type,{'dateTime':timespan.stop},db_manager,**option_dict)
            if aggregate_type.lower()=='last':
                return self.get_scalar(obs_type,{'dateTime':timespan.stop},db_manager,**option_dict)
            if aggregate_type.lower() in ('count','not_null'):
                # year of the timespan start
                year_timespan = weeutil.weeutil.archiveYearSpan(timespan.start)
                # If timespan.start is already the start of the year, archiveYearSpan()
                # returns the previous year. So add one year.
                if year_timespan.stop==timespan.start:
                    year_timespan = weeutil.weeutil.archiveYearSpan(timespan.start,years_ago=-1)
                # If `outTemp` is present from the beginning of the year up to the beginning
                # of the timespan in question, at least one reading could be returned. This
                # is the condition to return True
                _, _, val = weewx.xtypes.get_series(
                    'outTemp',
                    TimeSpan(year_timespan.start,timespan.start+86400),
                    db_manager,
                    aggregate_type,
                    86400,
                    **option_dict
                )
                try:
                    if aggregate_type=='count':
                        val = sum(val[0])
                    else:
                        val = min(val[0])
                except (TypeError,ValueError,LookupError):
                    val = False
                # If the timespan covers more than one year and the result is False
                # for the first year, try the next year(s).
                while not val and timespan.stop>year_timespan.stop:
                    year_timespan = weeutil.weeutil.archiveYearSpan(year_timespan.stop,years_ago=-1)
                    val = weewx.xtypes.get_aggregate(
                        'outTemp',
                        TimeSpan(year_timespan.start,year_timespan.start+86400),
                        aggregate_type,
                        db_manager,
                        **option_dict
                    )[0]
                # return result
                if aggregate_type=='count':
                    return weewx.units.ValueTuple(val,'count','group_count')
                else:
                    return weewx.units.ValueTuple(val,'boolean','group_boolean')
            raise weewx.UnknownAggregation("%s undefinded aggregation %s" % (obs_type,aggregate_type))

        # derived meteorological readings
        if obs_type in ('outSVP','outVaporP','outMixingRatio',
                        'outHumAbs','outEquiTemp','outThetaE'):
            return self.calc_derived(obs_type,timespan,aggregate_type,db_manager)

        # This function handles 'GTS' and 'GTSdate'.
        if obs_type!='GTS' and obs_type!='GTSdate':
            raise weewx.UnknownType(obs_type)
        
        # aggregation types that are defined for those values
        if aggregate_type not in ['sum','count','avg','max','min','last','maxtime','mintime','lasttime','not_null']:
            raise weewx.UnknownAggregation("%s undefinded aggregation %s" % (obs_type,aggregate_type))

        if timespan is None:
            raise weewx.CannotCalculate("%s %s no timespan" % (obs_type,aggregate_type))
        if aggregate_type=='sum':
            raise weewx.CannotCalculate("sum aggregation makes no sense for %s" % obs_type)
        if db_manager is None:
            if self.db_manager_ok:
                logerr("%s: no database reference" % obs_type)
                self.db_manager_ok=False
            raise weewx.CannotCalculate("%s: no database reference" % obs_type)

        # needed timestamps
        _soya_ts=startOfYearTZ(timespan.start+1,self.lmt_tz)
        _soye_ts=startOfYearTZ(timespan.stop,self.lmt_tz)

        # calculate GTS values for the years included in timespan 
        # (if time span is within the current year, the
        # value is calculated up to the current day (today))
        __max = 0
        __maxtime = None
        __min = 10000000
        __mintime = None
        __count = 0
        __ts = _soya_ts
        # Even if the time span starts after May 31st, the end value
        # is needed for some aggregations. So we have to calculate 
        # that year, too.
        while __ts<=_soye_ts:
            # calculate GTS values for the year
            self.calc_gts(__ts,db_manager)
            # update minimum and maximum
            if __ts in self.gts_values:
                for __i,__val in enumerate(self.gts_values[__ts]):
                    if __val is not None and (__ts+__i*86400)>startOfDayTZ(timespan.start,__ts) and (__ts+__i*86400)<=timespan.stop:
                        if __val>__max:
                            __max = __val
                            __maxtime = __ts+__i*86400
                        if __val<__min:
                            __min = __val
                            __mintime = __ts+__i*86400
                        if __val is not None:
                            __count += 1
            # next year
            __ts=startOfYearTZ(__ts+31708800,self.lmt_tz)
        
        if obs_type=='GTS':
            if aggregate_type=='avg':
                # 1 day is 86400s, but once a year it is 90000s or 82800s
                # when the daylight savings time is switched on or off.
                if timespan.stop-timespan.start<=90000:
                    __a=startOfDayTZ(timespan.start,_soya_ts)
                    __b=startOfDayTZ(timespan.stop,_soye_ts)
                    if -1 <= (__a-__b) <= 1:
                        # begin and end of timespan are different days
                        # according to timezone self.lmt_tz
                        # timespan.start <= __b <= timespan.stop
                        if __b-timespan.start>timespan.stop-__b:
                            __b=__a
                            _soye_ts = _soya_ts
                    if __b>=_soye_ts+13046400:
                        __x = weewx.units.ValueTuple(None,'degree_C_day','group_degree_day')
                    else:
                        __x=self.get_gts(obs_type,__b,_soye_ts)
                elif _soya_ts==_soye_ts and _soya_ts in self.gts_values:
                    # timespan within the same year but more than one day
                    # (not much use, but calculated anyway)
                    __a=dayOfGTSYear(timespan.start,_soya_ts)
                    __b=dayOfGTSYear(timespan.stop,_soye_ts)
                    if __a==__b:
                        __x=self.gts_values[_soya_ts][__a]
                    else:
                        __x=0
                        for __i in xrange(__a,__b):
                            if self.gts_values[_soya_ts][__i] is not None:
                                __x+=self.gts_values[_soya_ts][__i]
                        __x/=__b-__a
                else:
                    raise weewx.CannotCalculate("%s %s invalid timespan %s %s" % (obs_type,aggregate_type,timespan.stop-timespan.start,time.strftime("%Y-%m-%d %H:%M:%S",time.localtime(timespan.start))))
            elif aggregate_type=='lasttime':
                if timespan.stop>=self.last_gts_date:
                    # today or in future
                    __ts=self.last_gts_date
                else:
                    # before today
                    if _soye_ts not in self.gts_values:
                        raise weewx.CannotCalculate("%s %s" % (obs_type,aggregate_type))
                    __ts=dayOfGTSYear(timespan.stop,_soye_ts)
                    for __i,__v in reversed(enumerate(self.gts_values[_soye_ts])):
                        if __v is not None and __i<=__ts:
                            __ts=_soye_ts+86400*__i
                            break
                    else:
                        __ts=_soye_ts
                __x=weewx.units.ValueTuple(__ts,'unix_epoch','group_time')
            elif aggregate_type=='last':
                if timespan.stop>=_soye_ts+13046400:
                    # after May 31st
                    __ts=_soye_ts+13046400-86400
                else:
                    # between Jan 1st and May 31st
                    __ts=startOfDayTZ(timespan.stop,_soye_ts)
                    # startOfDay() returns for 24:00 the start of the
                    # next day. So we need to look for the day before.
                    if __ts==timespan.stop:
                        __ts-=86400
                    # for today there is no value so far
                    if -1 <= (__ts-startOfDayTZ(time.time(),_soye_ts)) <= 1:
                        __ts-=86400
                __x=self.get_gts(obs_type,__ts,_soye_ts)
            elif aggregate_type=='max':
                __x=weewx.units.ValueTuple(__max,'degree_C_day','group_degree_day')
            elif aggregate_type=='maxtime':
                __x=weewx.units.ValueTuple(__maxtime,'unix_epoch','group_time')
            elif aggregate_type=='min':
                __x=weewx.units.ValueTuple(__min,'degree_C_day','group_degree_day')
            elif aggregate_type=='mintime':
                __x=weewx.units.ValueTuple(__mintime,'unix_epoch','group_time')
            elif aggregate_type=='not_null':
                __x = (__mintime is not None or __maxtime is not None,'boolean','group_boolean')
            elif aggregate_type=='count':
                __x = (__count,'count','group_count')
            else:
                raise weewx.CannotCalculate("%s %s" % (obs_type,aggregate_type))
            """
            try:
              a=str(__x[0])
            except:
              logerr("get_aggregate 0")
              a=""
            try:
              b=str(__x[1])
            except:
              logerr("get_aggregate 1")
              b=""
            try:
              c=str(__x[2])
            except:
              logerr("get_aggregate 2")
              c=""
            loginf("get_aggregate %s,%s,%s" % (a,b,c))
            """
            return __x

        if obs_type=='GTSdate':
            if aggregate_type=='last' or aggregate_type=='max':
                if _soye_ts in self.gts_date and self.gts_date[_soye_ts] is not None and timespan.stop>=self.gts_date[_soye_ts]:
                    __x=self.gts_date[_soye_ts]
                else:
                    __x=None
                return weewx.units.ValueTuple(__x,'unix_epoch','group_time')
                    
        raise weewx.CannotCalculate("%s %s" % (obs_type,aggregate_type))
    

try:
    import user.barometer
    has_baro = True
except ImportError:
    has_baro = False

# This is a WeeWX service, whose only job is to register and unregister the extension
class GTSService(StdService):

    def __init__(self, engine, config_dict):
        super(GTSService,self).__init__(engine,config_dict)
        
        # the station's location
        # (needed for calculation of the local mean time (LMT))
        __lat = engine.stn_info.latitude_f
        __lon = engine.stn_info.longitude_f
        __alt_vt = engine.stn_info.altitude_vt

        # saturation vapor pressure calculation method
        __svp_method = config_dict.get('StdWXCalculate',{}).get('WXXTypes',{}).get('VaporPressure',{})
        
        # Instantiate an instance of the class GTSType, using the options
        self.GTSextension=GTSType(__lat,__lon,__svp_method)
        
        # Register the class
        weewx.xtypes.xtypes.insert(0,self.GTSextension)
        
        # Register the tags 
        # Note: This can be overwritten by the 'search_list' entry in skin_dict
        weewx.cheetahgenerator.default_search_list.append('user.dayboundarystats.DayboundaryStats')
        
        # Register barometer workaround
        loginf('PressureCooker %s' % has_baro)
        if has_baro:
            pc_dict =  config_dict.get('StdWXCalculate',{}).get('PressureCooker',{})
            self.barometer = user.barometer.PressureCooker(__alt_vt,
                max_delta_12h=weeutil.weeutil.to_float(pc_dict.get('max_delta_12h',1800)),
                altimeter_algorithm=pc_dict.get('altimeter',{}).get('algorithm','aaASOS'),
                barometer_algorithm=pc_dict.get('barometer',{}).get('algorithm','paWView'))
            loginf('PressureCooker %s ' % self.barometer)
            weewx.xtypes.xtypes.append(self.barometer)
        
    def shutDown(self):
    
        # Engine is shutting down. Remove the registration
        weewx.xtypes.xtypes.remove(self.GTSextension)
        
        # Remove tag registration
        weewx.cheetahgenerator.default_search_list.remove('user.dayboundarystats.DayboundaryStats')
        
        # Remove barometer workaround
        if has_baro:
            weewx.xtypes.xtypes.remove(self.barometer)
