# Copyright 2021 Johanna Roedenbeck
# timespans with different day boundaries

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
  
  "dayboundary" is an offset to UTC in seconds, that gives the 
  time of day that is used as day boundary for the given
  aggregation. In case of Python <3.7 the value is rounded
  to whole minutes.
  
  "LMT" means Local Mean Time of the station location.
  
  source: examples/stats.py
  
  The functions defining time spans are similar to those from
  weeutil.weeutil, but honour an arbitrary timezone offset.

"""

VERSION = "0.6b1"

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
from weeutil.weeutil import TimeSpan, to_int
from weewx.cheetahgenerator import SearchList
from weewx.tags import TimeBinder, TimespanBinder


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

# define tzinfo class for Local Mean Time

"""
class LMTtzinfo(datetime.timezone):

    def __init__(longitude):
        try:
            timeoffset=datetime.timedelta(seconds=self.generator.stn_info.longitude*240)
        except ValueError:
            # Python before 3.7 requires timedelta to be whole minutes
            timeoffset = datetime.timedelta(minutes=(self.generator.stn_info.longitude*240)//60)
        super(LMTtzinfo,self).__init__(timeoffset,"LMT")
"""

# The following functions are similar to that in weeutil/weeutil.py,
# but honour the timezone tz and do _not_ honour daylight savings time.

def startOfDayTZ(time_ts, soy_ts):
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


def hourSpanTZ(tz, time_ts, grace=1, hours_ago=0):
    """ Returns a TimeSpan for x hours ago  """
    if time_ts is None: return None
    time_ts -= grace
    dt = datetime.datetime.fromtimestamp(time_ts,tz)
    hour_start_dt = dt.replace(minute=0, second=0, microsecond=0)
    start_span_dt = hour_start_dt - datetime.timedelta(hours=hours_ago)
    stop_span_dt = start_span_dt + datetime.timedelta(hours=1)
    return TimeSpan(int(start_span_dt.timestamp()),int(stop_span_dt.timestamp()))
    

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
    return TimeSpan(int(_sunday_date.timestamp()),int(_next_sunday_date.timestamp()))
    
    
def monthSpanTZ(tz, time_ts, grace=1, months_ago=0):
    """ get the start of the GTS month time_ts is in """
    if time_ts is None:
        # the year of today
        dt=datetime.datetime.now(tz)
    else:
        # convert timestamp to local time according to timezone tz
        dt=datetime.datetime.fromtimestamp(time_ts,tz)
    time_ts -= grace
    # month 1st 00:00:00 according to timezone tz
    dta=datetime.datetime(dt.year,dt.month,1,0,0,0,0,tz)
    if dt.month==12:
        dte=datetime.datetime(dt.year+1,1,1,0,0,0,0,tz)
    else:
        dte=datetime.datetime(dt.year,dt.month+1,1,0,0,0,0,tz)
    # convert back to timestamp
    return TimeSpan(int(dta.timestamp()),int(dte.timestamp()))


def yearSpanTZ(tz, time_ts, grace=1, years_ago=0):
    """ Returns a TimeSpan representing a year in timezone tz
        that includes a given time."""
    if time_ts is None: time_ts = time.time()
    time_ts -= grace
    soya_ts = startOfYearTZ(time_ts,tz)
    soye_ts = startOfYearTZ(soya_ts+31968000,tz)
    return TimeSpan(int(soya_ts),int(soye_ts))


def genDaySpansWithoutDST(start_ts, stop_ts):
    """Generator function that generates start/stop of days
       according to timezone tz"""
    if None in (start_ts, stop_ts): return
    for time_ts in range(int(start_ts),int(stop_ts),86400):
        yield TimeSpan(int(time_ts),int(time_ts+86400))
    


class DayboundaryTimeBinder(TimeBinder):

    def __init__(self, lmt, db_lookup, report_time,
                 formatter=weewx.units.Formatter(), converter=weewx.units.Converter(),
                 **option_dict):
        super(DayboundaryTimeBinder,self).__init__(db_lookup, report_time,
                 formatter=formatter,converter=converter,**option_dict)
        self.lmt = lmt
        self.lmt_tz = lmt.get('timezone')

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
                              self.lmt, self.db_lookup, data_binding=data_binding,
                              context='day', formatter=self.formatter, converter=self.converter,
                              dayboundary=time_dict,
                              **self.option_dict)
                              
    def offsetday(self, data_binding=None, days_ago=0, dayboundary=None):
        time_dict,time_tz = self._get_timezone(dayboundary)
        return DayboundaryTimespanBinder(daySpanTZ(time_tz, 
                              self.report_time, days_ago=days_ago),
                              self.lmt, self.db_lookup, data_binding=data_binding,
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
            self.lmt, self.db_lookup, data_binding=data_binding,
            context='week', formatter=self.formatter, converter=self.converter,
            dayboundary=time_dict,
            **self.option_dict)

    def offsetmonth(self, data_binding=None, months_ago=0, dayboundary=None):
        time_dict,time_tz = self._get_timezone(dayboundary)
        return DayboundaryTimespanBinder(
            monthSpanTZ(time_tz, 
            self.report_time, months_ago=months_ago),
            self.lmt, self.db_lookup, data_binding=data_binding,
            context='month', formatter=self.formatter, converter=self.converter,
            dayboundary=time_dict,
            **self.option_dict)

    def offsetyear(self, data_binding=None, years_ago=0, dayboundary=None):
        time_dict,time_tz = self._get_timezone(dayboundary)
        return DayboundaryTimespanBinder(
            yearSpanTZ(time_tz, self.report_time, years_ago=years_ago),
            self.lmt, self.db_lookup, data_binding=data_binding,
            context='year', formatter=self.formatter, converter=self.converter,
            dayboundary=time_dict,
            **self.option_dict)

    def LMThour(self, data_binding=None, hours_ago=0):
        return DayboundaryTimespanBinder(hourSpanTZ(self.lmt_tz,
                              self.report_time, hours_ago=hours_ago),
                              self.lmt, self.db_lookup, data_binding=data_binding,
                              context='day', formatter=self.formatter, converter=self.converter,
                              LMT=self.lmt,
                              **self.option_dict)

    def LMTday(self, data_binding=None, days_ago=0):
        return DayboundaryTimespanBinder(daySpanTZ(self.lmt_tz, 
                              self.report_time, days_ago=days_ago),
                              self.lmt, self.db_lookup, data_binding=data_binding,
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
            self.lmt, self.db_lookup, data_binding=data_binding,
            context='week', formatter=self.formatter, converter=self.converter,
            LMT=self.lmt,
            **self.option_dict)

    def LMTmonth(self, data_binding=None, months_ago=0):
        return DayboundaryTimespanBinder(
            monthSpanTZ(self.lmt_tz, 
            self.report_time, months_ago=months_ago),
            self.lmt, self.db_lookup, data_binding=data_binding,
            context='month', formatter=self.formatter, converter=self.converter,
            LMT=self.lmt,
            **self.option_dict)

    def LMTyear(self, data_binding=None, years_ago=0):
        return DayboundaryTimespanBinder(
            yearSpanTZ(self.lmt_tz, self.report_time, years_ago=years_ago),
            self.lmt, self.db_lookup, data_binding=data_binding,
            context='year', formatter=self.formatter, converter=self.converter,
            LMT=self.lmt,
            **self.option_dict)

    
    
class DayboundaryTimespanBinder(TimespanBinder):

    def __init__(self, timespan, lmt, db_lookup, data_binding=None, context='current',
                 formatter=weewx.units.Formatter(),
                 converter=weewx.units.Converter(), **option_dict):
        super(DayboundaryTimespanBinder,self).__init__(
                 timespan, db_lookup, data_binding, context,
                 formatter=formatter, converter=converter, **option_dict)
        self.lmt = lmt
        self.lmt_tz = lmt.get('timezone')

    # Iterate over days in the time period:
    def days(self):
        return DayboundaryTimespanBinder._seqGenerator(genDaySpansWithoutDST, self.timespan,
                                            self.db_lookup, self.data_binding,
                                            'day', self.formatter, self.converter,
                                            **self.option_dict)

    # Static method used to implement the iteration:
    @staticmethod
    def _seqGenerator(genSpanFunc, timespan, *args, **option_dict):
        """Generator function that returns TimespanBinder for the appropriate timespans"""
        for span in genSpanFunc(timespan.start, timespan.stop):
            yield DayboundaryTimespanBinder(span, *args, **option_dict)


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
        """
        self.lmt_tz = LMTtzinfo(self.generator.stn_info.longitude_f)
        self.timeoffset = self.lmt_tz.utcoffset(None)
        """

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

        stats = DayboundaryTimeBinder(
            {'timeoffset':self.timeoffset,'timezone':self.lmt_tz},
            db_lookup,
            timespan.stop,
            formatter=self.generator.formatter,
            converter=self.generator.converter,
            week_start=self.generator.stn_info.week_start,
            rain_year_start=self.generator.stn_info.rain_year_start,
            trend=trend_dict,
            skin_dict=self.generator.skin_dict)

        return [stats]



