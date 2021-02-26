# Copyright 2021 Johanna Roedenbeck
# calculating Gruenlandtemperatursumme

"""

  That extension calculates the "Gruenlandtemperatursumme" (GTS) and
  the date when it exceedes 200, which is considered the start of
  growing of plants in Europe.
  
  It supplies 2 values:
  
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

  There are auxillary values:
  
  utcoffsetLMT:
  
    time offset of the local mean time (LMT)
    
  LMTtime
  
    user $current.LMTtime.raw to geht LMT of the last record
      
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

VERSION = "0.2"

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

import weedb
import weewx
import weewx.manager
import weewx.units
import weewx.xtypes
from weeutil.weeutil import TimeSpan
from weewx.engine import StdService

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


def startOfDayTZ(time_ts,soy_ts):
    """ get the start of the day time_ts is in 
    
        Don't use weeutil.weeutil.startOfDay() here. It handles daylight
        saving time different. 
        
    """
    return int(time_ts - (time_ts-soy_ts) % 86400)


def startOfYearTZ(time_ts,tz):
    """ get the start of the GTS year time_ts is in """
    if time_ts is None:
        # the year of today
        dt=datetime.datetime.now(tz)
    else:
        # convert timestamp to local time according to timezone tz
        dt=datetime.datetime.fromtimestamp(time_ts,tz)
    # Jan 1st 00:00:00 according to timezone tz
    dt=datetime.datetime(dt.year,1,1,0,0,0,0,tz)
    # convert back to timestamp
    return int(dt.timestamp())


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


class GTSType(weewx.xtypes.XType):

    def __init__(self,lat,lon):

        # class XType has no constructor
        #super(GTSType,self).__init()
        
        # remember the station's location and determine the timezone
        # data for local mean time (LMT)
        self.latlon=(lat,lon)
        self.timeoffset=datetime.timedelta(seconds=lon*240)
        self.lmt_tz=datetime.timezone(self.timeoffset,"LMT")

        # attributes to save calculted values
        self.last_gts_date=None # last date GTS is calculated for
        self.gts_date={}        # the date when GTS exceeds 200
        self.gts_value=None     # last GTS value calculated
        self.gts_values={}      # calculated GTS values
        
        # register the values with WeeWX
        weewx.units.obs_group_dict.setdefault('GTS','group_degree_day')
        weewx.units.obs_group_dict.setdefault('GTSdate','group_time')
        weewx.units.obs_group_dict.setdefault('LMTtime','group_time')
        weewx.units.obs_group_dict.setdefault('utcoffsetLMT','group_deltatime')
        
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

        #logdbg("calculate GTS for the year %s" % time.strftime("%Y",time.localtime(soy_ts)))
        
        # this year or a past year
        __this_year=soy_ts==startOfYearTZ(None,self.lmt_tz)
        
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
                except:
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
                __x=self.gts_values[soy_ts][dayOfGTSYear(sod_ts,soy_ts)]
                return weewx.units.ValueTuple(__x,'degree_C_day','group_degree_day')
            except (ValueError,TypeError,IndexError):
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


    def get_scalar(self, obs_type, record, db_manager):
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
        
        # This functions handles 'GTS' and 'GTSdate'.
        if obs_type!='GTS' and obs_type!='GTSdate':
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
        _soy_ts=startOfYearTZ(_time_ts,self.lmt_tz)
        _sod_ts=startOfDayTZ(_time_ts,_soy_ts) # start of day

        # If the start of the year in question is before the first
        # record in the database, no value can be calculated. The
        # same applies if the given timestamp is in future.
        if _soy_ts<db_manager.first_timestamp or _sod_ts>db_manager.last_timestamp:
            raise weewx.CannotCalculate(obs_type)
            
        # calculate GTS values for the given year 
        # (if record['dateTime'] is within the current year, the
        # value is calculated up to the current day (today))
        self.calc_gts(_soy_ts,db_manager)
        
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


    def get_aggregate(self, obs_type, timespan, aggregate_type, db_manager, **option_dict):

        if obs_type is None:
            raise weewx.UnknownType("obs_type is None")
            
        # time offset of local mean time (LMT)
        if obs_type=='utcoffsetLMT':
            return weewx.units.ValueTuple(self.lmt_tz.utcoffset(None).total_seconds(),'second','group_deltatime')

        # This function handles 'GTS' and 'GTSdate'.
        if obs_type!='GTS' and obs_type!='GTSdate':
            raise weewx.UnknownType(obs_type)
        
        # aggregation types that are defined for those values
        if aggregate_type not in ['avg','max','min','last','maxtime','mintime','lasttime']:
            raise weewx.UnknownAggregation("%s undefinded aggregation %s" % (obs_type,aggregation_type))

        if timespan is None:
            raise weewx.CannotCalculate("%s %s no timespan" % (obs_type,aggregate_type))
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
        __max=0
        __ts=_soya_ts
        if timespan.start>=_soya_ts+13046400:
            # time span starts after May 31st, so ignore that year
            __ts=startOfYearTZ(__ts+31708800,self.lmt_tz)
        while __ts<=_soye_ts:
            # calculate GTS values for the year
            self.calc_gts(__ts,db_manager)
            # update maximum
            if aggregate_type=='max' and __ts in self.gts_values:
                for __i in self.gts_values[__ts]:
                    if __i is not None and __i>__max:
                        __max=__i
            # next year
            __ts=startOfYearTZ(__ts+31708800,self.lmt_tz)
        
        if obs_type=='GTS':
            if aggregate_type=='avg':
                # 1 day is 86400s, but once a year it is 90000s or 82800s
                # when the daylight savings time is switched on or off.
                if timespan.stop-timespan.start<=90000:
                    __a=startOfDayTZ(timespan.start,_soya_ts)
                    __b=startOfDayTZ(timespan.stop,_soye_ts)
                    if __a!=__b:
                        # begin end end of timespan are different days
                        # according to timezone self.lmt_tz
                        # timespan.start <= __b <= timespan.stop
                        if __b-timespan.start>timespan.stop-__b:
                            __b=__a
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
                    if __ts==startOfDayTZ(time.time(),_soye_ts):
                        __ts-=86400
                __x=self.get_gts(obs_type,__ts,_soye_ts)
            elif aggregate_type=='max':
                __x=__max
            elif aggregate_type=='maxtime':
                if _soya_ts==_soye_ts:
                    __x=weewx.units.ValueTuple(timespan.stop,'unix_epoch','group_time')
                else:
                    raise weewx.CannotCalculate(aggregate_type)
            elif aggregate_type=='min':
                __x=weewx.units.ValueTuple(0,'degree_C_day','group_degree_day')
            elif aggregate_type=='mintime':
                __x=weewx.units.ValueTuple(_soya_ts,'unix_epoch','group_time')
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

        raise weewx.CannotCalculate("%s %s" % (obs_type,aggregate_type))

# This is a WeeWX service, whose only job is to register and unregister the extension
class GTSService(StdService):

    def __init__(self, engine, config_dict):
        super(GTSService,self).__init__(engine,config_dict)
        
        # the station's location
        # (needed for calculation of the local mean time (LMT))
        __lat=float(config_dict['Station']['latitude'])
        __lon=float(config_dict['Station']['longitude'])

        # Instantiate an instance of the class GTSType, using the options
        self.GTSextension=GTSType(__lat,__lon)
        
        # Register the class
        weewx.xtypes.xtypes.append(self.GTSextension)
        
    def shutDown(self):
    
        # Engine is shutting down. Remove the registration
        weewx.xtypes.xtypes.remove(self.GTSextension)

