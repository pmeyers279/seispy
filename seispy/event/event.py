"""
Class for seismic event metadata. Includes latitude, longitude, and time of
event, along with an ID number. A user can also define a time window
(relative to the event time) and taper lengths for data processing.

Includes a built in table from gwpy.table.Table

(Originally written by Tanner Prestegard)
"""

# Imports
import datetime
from gwpy.table import Table
import numpy as np
# Check if obspy is available.
try:
    # Import stuff from obspy.
    from obspy.core.utcdatetime import UTCDateTime
except ImportError:
    raise ImportError('Error: can\'t find obspy.  Please install it or add it to your $PYTHONPATH.')
from ..station import Seismometer
from astropy import units
from scipy.optimize import curve_fit

analyzed_names = ['latitude', 'longitude', 'time', 'evID',
                  'magnitude', 'win_start', 'win_end', 'taper_start',
                  'taper_end', 'filter_frequency','peak amplitude','peak time','peak time minimum',
                  'peak time maximum','estimated velocity','bearing','distance', 'channel']

# TODO we need some unittests for these classes
# chanObj class.
class Event(dict):
    """Class for seismic events from an IRIS database or our own database.
    """

    def __init__(self, latitude, longitude, time, evID=None, magnitude=None, win_start=0, win_end=-1, taper_start=10,
                 taper_end=10, analyzed=False, **kwargs):
        # Defining and processing class members.
        super(Event, self).__init__(**kwargs)
        self['latitude'] = float(latitude) # Latitude of event. (numeric)
        self['longitude'] = float(longitude) # Longitude of event. (numeric)
        self['time'] = time # time of event (will convert to UTCDateTime if not already)
        self['evID'] = evID # event ID number.
        self['magnitude'] = magnitude # event magnitude (for earthquakes)
        self['win_start'] = win_start # start of data we want to look at (relative to event time).
        self['win_end'] = win_end # end of data we want to look at (relative to event time).
        self['taper_start'] = taper_start # length of starting taper (s)
        self['taper_end'] = taper_end # length of ending taper (s)
        self['analyzed'] = analyzed

        # Make time a UTCDateTime object.
        if isinstance(time, str):
            self['time'] = UTCDateTime(datetime.datetime.strptime(time, '%m/%d/%Y %H:%M:%S'))
        elif isinstance(time, UTCDateTime):
            self['time'] = time
        else:
            raise TypeError('time should be a string formatted like MM/DD/YYYY ' +
                            'HH:MM:SS or a UTCDateTime object.')


    def __repr__(self):
        string =\
        """
        Event ID: {evID}
        Latitude: {latitude}
        Longitude: {longitude}
        Event Time: {time}
        Window: {win_start}-{win_end}
        Taper: {taper_start} sec. start, {taper_end} sec. end.
        Magnitude: {magnitude}
        """.format(**self)
        return string

    @property
    def latitude(self):
        return self['latitude']

    @property
    def longitude(self):
        return self['longitude']

    @property
    def analyzed(self):
        return self['analyzed']

    @property
    def time(self):
        return self['time']

    @property
    def win_start(self):
        return self['win_start']

    @property
    def win_end(self):
        return self['win_end']

    @property
    def taper_start(self):
        return self['taper_start']

    @property
    def taper_end(self):
        return self['taper_end']

    @property
    def magnitude(self):
        return self['magnitude']

    def createLog(self, filename):
        """Generate log file with event information, used for web interface."""
        # Set up lines for writing to file.
        date_line = "Date " + self['time'].strftime('%m/%d/%Y') + "\n"
        time_line = "Time " + self['time'].strftime('%H:%M:%S.%f') + "\n"
        lat_line = "Latitude " + str(self['latitude']) + "\n"
        long_line = "Longitude " + str(self['longitude']) + "\n"
        mag_line = "Magnitude " + (str(self['magnitude']) if self['magnitude'] is not None else "N/A") + "\n"

        # write to file.
        f = open(filename,'w')
        f.write(date_line)
        f.write(time_line)
        f.write(lat_line)
        f.write(long_line)
        f.write(mag_line)
        f.close()

    def analyze(self, station, frequencies, framedir='./', return_envelopes=False):
        data = Seismometer.fetch_data(station, self.time+self.win_start, self.time+self.win_end,
                                      framedir=framedir, chans_type='fast_chans')
        analyzed_event = self.copy()
        analyzed_event['station'] = station
        # detrend the data
        for key in data.keys():
            data[key] = data[key].detrend()
        # get bearing and distance
        dist, bearing = data['HHZ'].get_wave_path(self)
        analyzed_event['distance'] = dist * units.m
        analyzed_event['bearing'] = bearing * units.degrees
        # add transverse and radial channels to this seismometer
        data.rotate_RT(bearing)
        # taper around the rayleigh-wave part
        for key in data.keys():
            data[key] = data[key].taper(self)
        final_table = Table(names=analyzed_names)
        if return_envelopes:
            env_dict = {}
        for frequency in frequencies:
            for key in data.keys():
                analyzed_event['channel'] = key
                filtered = data[key].gaussian_filter(frequency)
                env = filtered.hilbert()
                env_dict[key] = env
                analyzed_event['peak amplitude'] = np.max(env) * units.m
                conf, pt = getEstimateAndConfLevel(env.times.value, env.value, 0.68)
                analyzed_event['peak time minimum'] = np.min(conf)
                analyzed_event['peak time maximum'] = np.max(conf)
                analyzed_event['peak time'] = pt
                # get standard deviation assuming gaussian
                analyzed_event['velocity'] = ((pt - self.time) / dist) * units.m * units.s**-1
                final_table.add_row(analyzed_event)
        if return_envelopes:
            return final_table, env_dict
        else:
            return final_table


def getEstimateAndConfLevel(times, envelope, conf):
    """
    Get our estimated value and confidence interval given a distribution.
    In this case we're estimating the peak time in this region.

    Parameters
    ----------
    times : `numpy.ndarray`
        possible peak times
    envelope : `numpy.ndarray`
        ampltiude of wave train
    conf : `float`
        confidence level
    Returns
    -------
    conf : `numpy.ndarray`
        All of the values from `times` in our confidence
        interval (or less than our upper limit)
    estimate : `float`
       Our measured estimate of the value of :math:`h_0` from the posterior.
       Nominally hardcoded to be the median of the returned interval.
    """
    # get indices to sort descending
    sort_idxs = np.argsort(envelope)[::-1]
    envelope_sort = envelope[sort_idxs]
    times_sort = times[sort_idxs]
    conf = times_sort[np.where(np.cumsum(envelope_sort) < conf)]
    return conf, np.median(conf)

class EventTable(Table):
    """
    Create an event table
    """
    def __init__(self, **kwargs):
        # Let's add column names to begin with
        super(EventTable, self).__init__(names=['latitude', 'longitude', 'time', 'evID',
                                                'magnitude', 'win_start', 'win_end', 'taper_start',
                                                'taper_end'], **kwargs)