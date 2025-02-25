# timespans with different day boundaries
# Copyright (C) 2021, 2022 Johanna Roedenbeck

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

  Provides:

  $offsethour(data_binding=None, hours_ago=0, dayboundary=None)
  $offsetday(data_binding=None, days_ago=0, dayboundary=None)
  $offsetyesterday(data_binding=None, dayboundary=None)
  $offsetmonth(data_binding=None, months_ago=0, dayboundary=None)
  $offsetyear(data_binding=None, years_ago=0, dayboundary=None)
  $LMThour(data_binding=None, hours_ago=0)
  $LMTday(data_binding=None, days_ago=0)
  $LMTyesterday(data_binding=None)
  $LMTmonth(data_binding=None, months_ago=0)
  $LMTyear(data_binding=None, years_ago=0)
  $daylight(timestamp=None, data_binding=None, days_ago=0, horizon=None, use_center=None)
  
  "dayboundary" is an offset to UTC in seconds, that gives the 
  time of day that is used as day boundary for the given
  aggregation. In case of Python <3.7 the value is rounded
  to whole minutes.
  
  "LMT" means Local Mean Time of the station location.
  
  source: examples/stats.py
  
  The functions defining time spans are similar to those from
  weeutil.weeutil, but honour an arbitrary timezone offset.

"""

VERSION = "1.1.1"

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

#import weedb
import weewx
import weewx.units
from weeutil.weeutil import TimeSpan, to_int, getDayNightTransitions
from weewx.cheetahgenerator import SearchList
from weewx.tags import TimeBinder, TimespanBinder
from weewx.almanac import Almanac

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
        syslog.syslog(level, 'DBS: %s' % msg)

    def logdbg(msg):
        logmsg(syslog.LOG_DEBUG, msg)

    def loginf(msg):
        logmsg(syslog.LOG_INFO, msg)

    def logerr(msg):
        logmsg(syslog.LOG_ERR, msg)


# The following functions are similar to that in weeutil/weeutil.py,
# but honour the timezone tz and do _not_ honour daylight savings time.

def startOfDayTZ(time_ts, soy_ts):
    """ get the start of the day time_ts is in 
    
        Don't use weeutil.weeutil.startOfDay() here. It handles daylight
        saving time different. 
        
    """
    return int(time_ts - (time_ts-soy_ts) % 86400)


def startOfYearTZ(time_ts,tz,years_ago=0):
    """ get the start of the GTS year time_ts is in """
    if time_ts is None:
        # the year of today
        dt=datetime.datetime.now(tz)
    else:
        # convert timestamp to local time according to timezone tz
        dt=datetime.datetime.fromtimestamp(time_ts,tz)
    # Jan 1st 00:00:00 according to timezone tz
    dt=datetime.datetime(dt.year-years_ago,1,1,0,0,0,0,tz)
    # convert back to timestamp
    return dt.timestamp()
    #return int(dt.timestamp())


def hourSpanTZ(tz, time_ts, grace=1, hours_ago=0):
    """ Returns a TimeSpan for x hours ago  """
    if time_ts is None: return None
    time_ts -= grace
    dt = datetime.datetime.fromtimestamp(time_ts,tz)
    hour_start_dt = dt.replace(minute=0, second=0, microsecond=0)
    start_span_dt = hour_start_dt - datetime.timedelta(hours=hours_ago)
    stop_span_dt = start_span_dt + datetime.timedelta(hours=1)
    return TimeSpan(start_span_dt.timestamp(),stop_span_dt.timestamp())
    

def daySpanTZ(tz, time_ts, grace=1, days_ago=0):
    """ Returns a TimeSpan representing a day in timezone tz
        that includes the given time."""
    time_ts -= grace
    soy_ts = startOfYearTZ(time_ts,tz)
    sod_ts = startOfDayTZ(time_ts,soy_ts)-days_ago*86400
    return TimeSpan(sod_ts,sod_ts+86400)


def weekSpanTZ(tz, time_ts, startOfWeek=6, grace=1, weeks_ago=0):
    """Returns a TimeSpan representing a week that includes a given time. """
    if time_ts is None: return None
    time_ts -= grace
    _day_date = datetime.datetime.fromtimestamp(time_ts,tz)
    _day_of_week = _day_date.weekday()
    _delta = _day_of_week - startOfWeek
    if _delta < 0: _delta += 7
    _sunday_date = _day_date - datetime.timedelta(days=(_delta + 7 * weeks_ago))
    _sunday_date = _sunday_date.replace(hour=0,minute=0,second=0,microsecond=0)
    _next_sunday_date = _sunday_date + datetime.timedelta(days=7)
    return TimeSpan(_sunday_date.timestamp(),_next_sunday_date.timestamp())
    
    
def monthSpanTZ(tz, time_ts, grace=1, months_ago=0):
    """ get the start of the GTS month time_ts is in """
    if time_ts is None:
        # the year of today
        dt=datetime.datetime.now(tz)
    else:
        # convert timestamp to local time according to timezone tz
        dt=datetime.datetime.fromtimestamp(time_ts,tz)
    time_ts -= grace
    __year = dt.year
    __month = dt.month
    if months_ago>=12:
        __year -= months_ago//12
        months_ago = months_ago%12
    if months_ago<__month:
        __month -= months_ago
    else:
        __year -= 1
        __month += 12 - months_ago
    # month 1st 00:00:00 according to timezone tz
    dta=datetime.datetime(__year,__month,1,0,0,0,0,tz)
    if __month==12:
        dte=datetime.datetime(__year+1,1,1,0,0,0,0,tz)
    else:
        dte=datetime.datetime(__year,__month+1,1,0,0,0,0,tz)
    # convert back to timestamp
    return TimeSpan(dta.timestamp(),dte.timestamp())


def yearSpanTZ(tz, time_ts, grace=1, years_ago=0):
    """ Returns a TimeSpan representing a year in timezone tz
        that includes a given time."""
    if time_ts is None: time_ts = time.time()
    time_ts -= grace
    soya_ts = startOfYearTZ(time_ts,tz,years_ago)
    soye_ts = startOfYearTZ(soya_ts+31968000,tz)
    return TimeSpan(soya_ts,soye_ts)
    #return TimeSpan(int(soya_ts),int(soye_ts))


def genDaySpansWithoutDST(start_ts, stop_ts):
    """Generator function that generates start/stop of days
       according to timezone tz"""
    if None in (start_ts, stop_ts): return
    for time_ts in range(int(start_ts),int(stop_ts),86400):
        yield TimeSpan(time_ts,time_ts+86400)
    
def genWeekSpansWithoutDST(start_ts, stop_ts):
    """Generator function that generates start/stop of days
       according to timezone tz"""
    if None in (start_ts, stop_ts): return
    for time_ts in range(int(start_ts),int(stop_ts),604800):
        yield TimeSpan(time_ts,time_ts+604800)

def get_sunrise_sunset(ts, latlon, horizon, use_center, db_lookup, report_time, formatter, converter, **option_dict):
    # (derived from cheetahgenerator.py, Copyright Tom Keffer)
    try:
        # get the middle of the timespan ts
        ts = ts.start//2 + ts.stop//2
    except (LookupError,AttributeError):
        # ts is already a timestamp, do nothing
        pass
    # ICAO standard athmosphere
    temperature_C = 15.0
    pressure_mbar = 1013.25
    try:
        # get timestamp of sunrise and sunset out of pyephem
        alm = Almanac(ts, 
                      latlon[0], 
                      latlon[1], 
                      altitude=latlon[2],
                      temperature=temperature_C,
                      pressure=pressure_mbar,
                      horizon=horizon,
                      formatter=formatter,
                      converter=converter)
        sunrise = alm.sun(use_center=use_center).rise.raw
        sunset = alm.sun(use_center=use_center).set.raw
        # See if we can get more accurate values by looking them up in the
        # weather database. The database might not exist, so be prepared for
        # a KeyError exception.
        temp1=temperature_C
        press1=pressure_mbar
        temp2=temperature_C
        press2=pressure_mbar
        try:
            binding = option_dict.get('skin_dict',{}).get('data_binding', 'wx_binding')
            archive = db_lookup(binding)
        except (KeyError, weewx.UnknownBinding, weedb.NoDatabaseError):
            logerr("daylight")
            pass
        else:
            rec = archive.getRecord(sunrise, max_delta=3600)
            if rec is not None:
                if 'outTemp' in rec:
                    x = weewx.units.convert(weewx.units.as_value_tuple(rec, 'outTemp'), "degree_C")[0]
                    if x is not None: temp1 = x
                if 'barometer' in rec:
                    x = weewx.units.convert(weewx.units.as_value_tuple(rec, 'barometer'), "mbar")[0]
                    if x is not None: press1 = x
            rec = archive.getRecord(sunset, max_delta=3600)
            if rec is not None:
                if 'outTemp' in rec:
                    x = weewx.units.convert(weewx.units.as_value_tuple(rec, 'outTemp'), "degree_C")[0]
                    if x is not None: temp2 = x
                if 'barometer' in rec:
                    x = weewx.units.convert(weewx.units.as_value_tuple(rec, 'barometer'), "mbar")[0]
                    if x is not None: press2 = x
        try:
            # get timestamp of sunrise and sunset out of pyephem
            sunrise = alm(temperature=temp1,pressure=press1).sun(use_center=use_center).rise.raw
            sunset = alm(temperature=temp2,pressure=press2).sun(use_center=use_center).set.raw
        except Exception as e:
            logerr("pyephem error %s %s" % (e.__class__.__name__,e))
            logerr("pyephem error temp1 %s temp2 %s press1 %s press2 %s" % (temp1,temp2,press1,press2))
            pass
    except Exception:
        # If pyephem is not installed or another error occurs, use
        # the built-in function of WeeWX instead.
        first,values = getDayNightTransitions(ts.start, ts.stop, latlon[0], latlon[1])
        sunrise = values[0]
        sunset = values[1]
    return TimeSpan(sunrise, sunset)


class DayboundaryTimeBinder(TimeBinder):

    def __init__(self, tz_dict, latlon, db_lookup, report_time,
                 formatter=weewx.units.Formatter(), converter=weewx.units.Converter(),
                 **option_dict):
        super(DayboundaryTimeBinder,self).__init__(db_lookup, report_time,
                 formatter=formatter,converter=converter,**option_dict)
        self.lmt = tz_dict
        self.lmt_tz = tz_dict.get('timezone')
        self.latlon = latlon

    def _get_timezone(self, offset=None):
        """ get the offset to UTC for the required day boundary """
        if offset is not None:
            offset_f = float(offset)
            try:
                timeoffset = datetime.timedelta(seconds=offset_f)
                timetz = datetime.timezone(timeoffset,"")
            except ValueError:
                # Python before 3.7 requires timedelta to be whole minutes
                timeoffset = datetime.timedelta(minutes=offset_f//60)
                timetz = datetime.timezone(timeoffset,"")
            return {'timeoffset':timeoffset,'timezone':timetz},timetz
        # if offset is None return Local Mean Time
        return self.lmt,self.lmt_tz
    
    def offsethour(self, data_binding=None, hours_ago=0, dayboundary=None):
        time_dict,time_tz = self._get_timezone(dayboundary)
        return DayboundaryTimespanBinder(hourSpanTZ(time_tz,
                              self.report_time, hours_ago=hours_ago),
                              self.lmt, self.latlon, self.db_lookup, data_binding=data_binding,
                              context='day', formatter=self.formatter, converter=self.converter,
                              dayboundary=time_dict,
                              **self.option_dict)
                              
    def offsetday(self, data_binding=None, days_ago=0, dayboundary=None):
        time_dict,time_tz = self._get_timezone(dayboundary)
        return DayboundaryTimespanBinder(daySpanTZ(time_tz, 
                              self.report_time, days_ago=days_ago),
                              self.lmt, self.latlon, self.db_lookup, data_binding=data_binding,
                              context='day', formatter=self.formatter, converter=self.converter,
                              dayboundary=time_dict,
                              **self.option_dict)

    def offsetyesterday(self, data_binding=None, dayboundary=None):
        return self.offsetday(data_binding, days_ago=1,dayboundary=dayboundary)

    def offsetweek(self, data_binding=None, weeks_ago=0, dayboundary=None):
        week_start = to_int(self.option_dict.get('week_start', 6))
        time_dict,time_tz = self._get_timezone(dayboundary)
        return DayboundaryTimespanBinder(
            weekSpanTZ(self.time_tz,
            self.report_time, week_start, weeks_ago=weeks_ago),
            self.lmt, self.latlon, self.db_lookup, data_binding=data_binding,
            context='week', formatter=self.formatter, converter=self.converter,
            dayboundary=time_dict,
            **self.option_dict)

    def offsetmonth(self, data_binding=None, months_ago=0, dayboundary=None):
        time_dict,time_tz = self._get_timezone(dayboundary)
        return DayboundaryTimespanBinder(
            monthSpanTZ(time_tz, 
            self.report_time, months_ago=months_ago),
            self.lmt, self.latlon, self.db_lookup, data_binding=data_binding,
            context='month', formatter=self.formatter, converter=self.converter,
            dayboundary=time_dict,
            **self.option_dict)

    def offsetyear(self, data_binding=None, years_ago=0, dayboundary=None):
        time_dict,time_tz = self._get_timezone(dayboundary)
        return DayboundaryTimespanBinder(
            yearSpanTZ(time_tz, self.report_time, years_ago=years_ago),
            self.lmt, self.latlon, self.db_lookup, data_binding=data_binding,
            context='year', formatter=self.formatter, converter=self.converter,
            dayboundary=time_dict,
            **self.option_dict)

    def LMThour(self, data_binding=None, hours_ago=0):
        return DayboundaryTimespanBinder(hourSpanTZ(self.lmt_tz,
                              self.report_time, hours_ago=hours_ago),
                              self.lmt, self.latlon, self.db_lookup, data_binding=data_binding,
                              context='day', formatter=self.formatter, converter=self.converter,
                              LMT=self.lmt,
                              **self.option_dict)

    def LMTday(self, data_binding=None, days_ago=0):
        return DayboundaryTimespanBinder(daySpanTZ(self.lmt_tz, 
                              self.report_time, days_ago=days_ago),
                              self.lmt, self.latlon, self.db_lookup, data_binding=data_binding,
                              context='day', formatter=self.formatter, converter=self.converter,
                              LMT=self.lmt,
                              **self.option_dict)

    def LMTyesterday(self, data_binding=None):
        return self.LMTday(data_binding, days_ago=1)

    def LMTweek(self, data_binding=None, weeks_ago=0, dayboundary=None):
        week_start = to_int(self.option_dict.get('week_start', 6))
        return DayboundaryTimespanBinder(
            weekSpanTZ(self.lmt_tz,
            self.report_time, week_start, weeks_ago=weeks_ago),
            self.lmt, self.latlon, self.db_lookup, data_binding=data_binding,
            context='week', formatter=self.formatter, converter=self.converter,
            LMT=self.lmt,
            **self.option_dict)

    def LMTmonth(self, data_binding=None, months_ago=0):
        return DayboundaryTimespanBinder(
            monthSpanTZ(self.lmt_tz, 
            self.report_time, months_ago=months_ago),
            self.lmt, self.latlon, self.db_lookup, data_binding=data_binding,
            context='month', formatter=self.formatter, converter=self.converter,
            LMT=self.lmt,
            **self.option_dict)

    """
    def LMTyear(self, data_binding=None, years_ago=0):
        return DayboundaryTimespanBinder(
            yearSpanTZ(self.lmt_tz, self.report_time, years_ago=years_ago),
            self.lmt, self.db_lookup, data_binding=data_binding,
            context='year', formatter=self.formatter, converter=self.converter,
            LMT=self.lmt,
            **self.option_dict)
    """

    def LMTyear(self, data_binding=None, years_ago=0, month_span=None):
        ts = yearSpanTZ(self.lmt_tz, self.report_time, years_ago=years_ago)
        if month_span is not None:
            try:
                _from = to_int(month_span[0])
                _to = to_int(month_span[1])
            except (ValueError,IndexError):
                _from = to_int(month_span)
                _to = _from
            #loginf("%s %s" % (_from,_to))
            try:
                dt_from = datetime.datetime.fromtimestamp(ts.start,self.lmt_tz)
                #loginf("1 %s %s %s" % (dt_from.year,dt_from.month,dt_from.day))
                dt_from = dt_from.replace(month=_from)
                #loginf(dt_from)
                if _to>=_from:
                    # within one year
                    if _to<12:
                        dt_to = datetime.datetime.fromtimestamp(ts.start,self.lmt_tz)
                        dt_to = dt_to.replace(month=_to+1)
                        #loginf(dt_to)
                        ts = TimeSpan(dt_from.timestamp(),dt_to.timestamp())
                    else:
                        ts = TimeSpan(dt_from.timestamp(),ts.end)
                else:
                    # includes year change
                    dt_to = datetime.datetime.fromtimestamp(ts.stop,self.lmt_tz)
                    dt_to = dt_to.replace(month=_to+1)
                    ts = TimeSpan(dt_from.timestamp(),dt_to.timestamp())
                    pass
            except (ValueError,IndexError) as e:
                #logerr("3 %s" % e)
                pass
        return DayboundaryTimespanBinder(ts,
            self.lmt, self.latlon, self.db_lookup, data_binding=data_binding,
            context='year', formatter=self.formatter, converter=self.converter,
            LMT=self.lmt,
            **self.option_dict)
            
    def daylight(self, timestamp=None, data_binding=None, days_ago=0, horizon=None, use_center=False):
        dbin = data_binding
        if timestamp:
            # timestamp or timespan
            try:
                ts = timestamp.timespan
                self.db_lookup = timestamp.db_lookup
                dbin = timestamp.data_binding if timestamp.data_binding else data_binding
            except (LookupError,AttributeError):
                try:
                    ts = TimeSpan(to_int(timestamp[0]),to_int(timestamp[1]))
                except LookupError:
                    ts = daySpanTZ(self.lmt_tz, timestamp, days_ago=days_ago)
        else:
            # day timespan (from antitransit to antitransit)
            ts = daySpanTZ(self.lmt_tz, self.report_time, days_ago=days_ago)

        ts = get_sunrise_sunset(ts,
                                self.latlon,
                                horizon,
                                use_center,
                                self.db_lookup, 
                                self.report_time, 
                                self.formatter, 
                                self.converter,
                                **self.option_dict)

        return DayboundaryTimespanBinder(ts,
                              self.lmt, self.latlon, self.db_lookup, data_binding=dbin,
                              context='day', formatter=self.formatter, converter=self.converter,
                              LMT=self.lmt,
                              **self.option_dict)

    
class DayboundaryTimespanBinder(TimespanBinder):

    def __init__(self, timespan, lmt, latlon, db_lookup, data_binding=None, context='current',
                 formatter=weewx.units.Formatter(),
                 converter=weewx.units.Converter(), **option_dict):
        super(DayboundaryTimespanBinder,self).__init__(
                 timespan, db_lookup, data_binding, context,
                 formatter=formatter, converter=converter, **option_dict)
        self.lmt = lmt
        self.lmt_tz = lmt.get('timezone')
        self.latlon = latlon

    # Iterate over days in the time period:
    def days(self):
        return DayboundaryTimespanBinder._seqGenerator(genDaySpansWithoutDST, self.timespan,
                                            self.lmt, self.latlon,
                                            self.db_lookup, self.data_binding,
                                            'day', self.formatter, self.converter,
                                            **self.option_dict)

    # Iterate over weeks in the time period:
    def weeks(self):
        return DayboundaryTimespanBinder._seqGenerator(genWeekSpansWithoutDST, self.timespan,
                                            self.lmt, self.latlon,
                                            self.db_lookup, self.data_binding,
                                            'week', self.formatter, self.converter,
                                            **self.option_dict)
                                            
    # Iterate over days in the time period and return daylight timespan:
    def daylights(self, horizon=None, use_center=False):
        """ generator function that returns DayboundaryTimespanBinder """
        # Note: span.start//2+span.stop//2 is used instead of 
        #       (span.start+span.stop)//2 to prevent overflow
        for span in genDaySpansWithoutDST(self.timespan.start,self.timespan.stop):
            ts = get_sunrise_sunset(span,
                                self.latlon,
                                horizon,
                                use_center,
                                self.db_lookup, 
                                int(span.start)//2+int(span.stop)//2, 
                                self.formatter, 
                                self.converter,
                                **self.option_dict)
            yield DayboundaryTimespanBinder(ts, 
                                           self.lmt,
                                           self.latlon, 
                                           self.db_lookup, 
                                           self.data_binding,
                                           'day',
                                           self.formatter,
                                           self.converter,
                                           **self.option_dict)

    # Static method used to implement the iteration:
    @staticmethod
    def _seqGenerator(genSpanFunc, timespan, *args, **option_dict):
        """Generator function that returns TimespanBinder for the appropriate timespans"""
        for span in genSpanFunc(timespan.start, timespan.stop):
            yield DayboundaryTimespanBinder(span, *args, **option_dict)
            
    @property
    def length(self):
        val = weewx.units.ValueTuple(self.timespan.stop-self.timespan.start, 'second', 'group_deltatime')
        if val[0]<=5400:
            context = 'brief_delta'
        elif val[0]<=86400:
            context = 'short_delta'
        else:
            context = 'long_delta'
        return weewx.units.ValueHelper(val, context, self.formatter, self.converter)


class DayboundaryStats(SearchList):

    def __init__(self, generator):
        super(DayboundaryStats, self).__init__(generator)
        # get timezone for local mean time
        try:
            self.timeoffset=datetime.timedelta(seconds=self.generator.stn_info.longitude_f*240)
            self.lmt_tz=datetime.timezone(self.timeoffset,"LMT")
        except ValueError:
            # Python before 3.7 requires timedelta to be whole minutes
            self.timeoffset = datetime.timedelta(minutes=(self.generator.stn_info.longitude_f*240)//60)
            self.lmt_tz = datetime.timezone(self.timeoffset,"LMT")

    def get_extension_list(self, timespan, db_lookup):
        """Returns a search list extension with two additions.
        
        Parameters:
          timespan: An instance of weeutil.weeutil.TimeSpan. This will
                    hold the start and stop times of the domain of 
                    valid times.
          db_lookup: This is a function that, given a data binding
                     as its only parameter, will return a database manager
                     object.
        """
        try:
            trend_dict = self.generator.skin_dict['Units']['Trend']
        except KeyError:
            trend_dict = {'time_delta': 10800,
                          'time_grace': 300}

        # station altitude
        try:
            altitude_m = weewx.units.convert(self.generator.stn_info.altitude_vt,'meter')[0]
        except (ValueError,TypeError,IndexError):
            altitude_m = None

        stats = DayboundaryTimeBinder(
            {'timeoffset':self.timeoffset,'timezone':self.lmt_tz},
            (self.generator.stn_info.latitude_f,self.generator.stn_info.longitude_f,altitude_m),
            db_lookup,
            timespan.stop,
            formatter=self.generator.formatter,
            converter=self.generator.converter,
            week_start=self.generator.stn_info.week_start,
            rain_year_start=self.generator.stn_info.rain_year_start,
            trend=trend_dict,
            skin_dict=self.generator.skin_dict)

        return [stats]



