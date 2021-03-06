from __future__ import division
from scipy.sparse.linalg import lsqr
from collections import OrderedDict
from ..utils import *
import astropy.units as u
from ..noise import gaussian
from ..trace import Trace, fetch
from ..recoverymap import RecoveryMap
import numpy as np
from scipy.sparse.linalg import lsqr
from gwpy.frequencyseries import FrequencySeries
from .station import homestake

class Seismometer(OrderedDict):
    """
    Station data
    """
    @classmethod
    def fetch_data(cls, station_name, st, et, framedir='./', chans_type='useful',
        location=[0,0,0]):
        """
        fetch data for this seismometer

        Parameters
        ----------
        st : `int`
            start time
        et : `int`
            end time
        framedir : TODO, optional

        Returns
        -------
        TODO

        """
        seismometer = cls()
        chans = get_homestake_channels(chans_type)
        for chan in chans:
            seismometer[chan] = fetch(st, et, station_name+':'+chan, framedir=framedir)
        return seismometer

    @classmethod
    def initialize_all_good(cls, duration, chans_type='useful', start_time=0,
            name='seismometer', location=[0,0,0]):
        """
        Initialize a seismometer with all good
        information in all channels and zeros in
        the data channels.
        channel | srate
        HHN 100
        HHE 100
        LCE 1
        HHZ 100
        LCQ 1
        VKI 0.1000000
        VEP 0.1000000
        VM1 0.1000000
        VM3 0.1000000
        VM2 0.1000000
        """
        name = str(name)
        seismometer = Seismometer()
        chans = get_homestake_channels(chans_type)
        seismometer['HHE'] = Trace(np.zeros(int(duration*100)),
                sample_rate=100*u.Hz, epoch=start_time, name=name+' East',
                unit=u.m)
        seismometer['HHN'] = Trace(np.zeros(int(duration*100)),
                sample_rate=100*u.Hz, epoch=start_time, name=name+' North',
                unit=u.m)
        seismometer['HHZ'] = Trace(np.zeros(int(duration*100)),
                sample_rate=100*u.Hz, epoch=start_time, name=name+' Vertical',
                unit=u.m)
        if chans_type=='fast_chans':
            for chan in seismometer.keys():
                seismometer[chan].location = location
            return seismometer
        else:
            seismometer['LCQ'] = Trace(100 * np.ones(int(duration*1)),
                    sample_rate=1*u.Hz, epoch=start_time, name=name+' Clock Quality')
            seismometer['LCE'] = Trace(np.zeros(int(duration*1)),
                    sample_rate=1*u.Hz, epoch=start_time, name=name+' Clock Phase\
                    Error')
            seismometer['VM1'] = Trace(np.zeros(int(duration*0.1)),
                    sample_rate=0.1*u.Hz, epoch=start_time, name=name+' Mass\
                    Position Channel 1')
            seismometer['VM2'] = Trace(np.zeros(int(duration*0.1)),
                    sample_rate=0.1*u.Hz, epoch=start_time, name=name+' Mass\
                    Position Channel 2')
            seismometer['VM3'] = Trace(np.zeros(int(duration*0.1)),
                    sample_rate=0.1*u.Hz, epoch=start_time, name=name+' Mass\
                    Position Channel 3')
            seismometer['VEP'] = Trace(13 * np.ones(int(duration*0.1)),
                    sample_rate=0.1*u.Hz, epoch=start_time, name=name+' System\
                    Voltage')
            seismometer['VKI'] = Trace(np.zeros(int(duration*0.1)),
                    sample_rate=0.1*u.Hz, epoch=start_time, name=name+' System\
                    temperature')
        # set location
            for chan in seismometer.keys():
                seismometer[chan].location = location
        return seismometer

class SeismometerArray(OrderedDict):
    """
    Data object for storing data for a station"""
    @classmethod
    def fetch_data(cls, st, et, framedir='./', chans_type='useful'):
        """TODO: Docstring for fetch_data.

        Parameters
        ----------
        st : `int`
            start time
        et : `int`
            end time
        framedir : `string`, optional
            top level frame directory
        chans_type : `type of chans to load`, optional

        Returns
        -------
        seismometer_array : :class:`seispy.station.stationdata.SeismometerArray`
            seismometer array
        """
        arr = cls.initialize_all_good(homestake(), et-st,
                chans_type=chans_type, start_time=st)
        for station in arr.keys():
            arr[station] = Seismometer.fetch_data(station, st, et,
                    framedir=framedir, chans_type=chans_type)
        return arr

    @classmethod
    def _gen_pwave(cls, stations, amplitude, phi, theta, frequency, duration, Fs=100, c=3000,
        noise_amp=0, phase=0, segdur=None):
        """
        simulate p-wave in a certain direction

        Parameters
        ----------
        direction : TODO
        frequency : TODO
        time : TODO
        Fs : TODO

        Returns
        -------
        E : TODO
        N : TODO
        Z : TODO
        """
        cphi = np.cos(phi)
        sphi = np.sin(phi)
        ctheta = np.cos(theta)
        stheta = np.sin(theta)
        src_dir = np.array([cphi*stheta, sphi*stheta, ctheta])
        # get time delays
        taus = np.array([-np.dot(src_dir, stations[key])/c for key in
            stations.keys()])
        tau_round = np.round(taus*Fs)/Fs
        ts = min(-tau_round)
        te = max(-tau_round)
        times = np.arange(0, np.abs(ts) + duration + te, 1/Fs)
        Nsamps = duration * Fs
        # shift backward in time
        times += ts
        data = SeismometerArray()
        ct = 0
        final_times = np.arange(0, duration, 1/Fs)
        for key in stations.keys():
            data[key]={}
            station = stations[key]
            delay = -np.dot(src_dir, station)/c
            delaySamps = int(ts*Fs+np.round(delay*Fs))
            signal = np.zeros(times.size)
            if frequency == 0:
                signal = amplitude*np.random.randn(times.size)
            else:
                # most of our noise spectra will be one-sided, but this is a real
                # signal, so we multiply this by two.
                signal = amplitude * np.sin(2*np.pi*frequency*times + phase)
            # impose time delay
            amp = np.roll(signal,delaySamps)[:Nsamps]
            data[key]['HHE'] = Trace(src_dir[0]*amp, sample_rate=Fs,
                    times=final_times, unit=u.m)
            data[key]['HHN'] = Trace(src_dir[1]*amp, sample_rate=Fs,
                    times=final_times,unit=u.m)
            data[key]['HHZ'] = Trace(src_dir[2]*amp, sample_rate=Fs,
                    times=final_times,unit=u.m)
            for key2 in data[key].keys():
                data[key][key2].location = station
        return data

    @classmethod
    def _gen_swave(cls, stations, amplitude, phi, theta, psi, frequency, duration,
            phase=0, Fs=100, c=3000):
        """
        simulate s-wave in a certain direction

        Parameters
        ----------
        stations : `dict`
            dictionary of station locations
        A : `float`
            amplitude of input wave
        phi : `float`
            azimuth in radians
        theta : `float`
            polar angle from north pole in radians
        psi : `float`
            s-wave polarization angle from horizontal
            E-N plane in radians
        frequency : `float`
            frequency of source
        duration : `float`
            duration of signal to simulate
        Fs : `float`, optional, default=100 Hz
            sample rate (int preferred)
        c : `float`, optional, default=3000 m/s
            speed of wave
        phase : `float`, optional, default=0
            phase delay of wave in radians

        Returns
        -------
        data : `dict`
            2-layer dict with first keys as stations,
            second keys as channels for each station.
            Each entry is the data for that channel
            for that station for a simulated wave.
        """
        cphi = np.cos(phi)
        sphi = np.sin(phi)
        ctheta = np.cos(theta)
        stheta = np.sin(theta)
        cpsi = np.cos(psi)
        spsi = np.sin(psi)
        src_dir = np.array([cphi*stheta, sphi*stheta, ctheta])
        # Get relative amplitudes in E,N,Z directions
        # based on polarizations. See internal method below.
        dx, dy, dz = get_polarization_coeffs(phi, theta, psi)

        # get time delays
        taus = np.array([-np.dot(src_dir, stations[key])/c for key in
            stations.keys()])
        tau_round = np.round(taus*Fs)/Fs
        ts = min(-tau_round)
        te = max(-tau_round)
        Nsamps = duration * Fs
        final_times = np.arange(0, duration, 1/Fs)
        times = np.arange(0, np.abs(ts) + duration + te, 1/Fs)
        # shift backward in time
        times += ts
        data = SeismometerArray()
        ct = 0
        for key in stations.keys():
            data[key]={}
            station = stations[key]
            delay = -np.dot(src_dir, station)/c
            delaySamps = int(ts*Fs+np.round(delay*Fs))
            signal = np.zeros(times.size)
            if frequency == 0:
                signal = amplitude*np.random.randn(times.size)
            else:
                signal = amplitude * np.sin(2*np.pi*frequency*times + phase)
            # impose time delay
            amp = np.roll(signal,delaySamps)[:Nsamps]
            data[key]['HHE'] = Trace(dx*amp, sample_rate=Fs, times=final_times,
                    unit=u.m, name=key)
            data[key]['HHN'] = Trace(dy*amp, sample_rate=Fs, times=final_times,
                    unit=u.m, name=key)
            data[key]['HHZ'] = Trace(dz*amp, sample_rate=Fs, times=final_times,
                    unit=u.m, name=key)
            for key2 in data[key].keys():
                data[key][key2].location = station
        return data

    @classmethod
    def _gen_rwave(cls, stations, amplitude, phi, theta, epsilon, alpha, frequency, duration, Fs=100, c=3000, noise_amp=0, phase=0, segdur=None):
        """
        simulate p-wave in a certain direction

        Parameters
        ----------
        direction : TODO
        frequency : TODO
        time : TODO
        Fs : TODO

        Returns
        -------
        E : TODO
        N : TODO
        Z : TODO
        """
        cphi = np.cos(phi)
        sphi = np.sin(phi)
        ctheta = np.cos(theta)
        stheta = np.sin(theta)
        src_dir = np.array([cphi*stheta, sphi*stheta, ctheta])
        # get time delays
        taus = np.array([-np.dot(src_dir, stations[key])/c for key in
            stations.keys()])
        tau_round = np.round(taus*Fs)/Fs
        ts = min(-tau_round)
        te = max(-tau_round)
        times = np.arange(0, np.abs(ts) + duration + te, 1/Fs)
        Nsamps = duration * Fs
        # shift backward in time
        times += ts
        data = SeismometerArray()
        ct = 0
        final_times = np.arange(0, duration, 1/Fs)
        for key in stations.keys():
            data[key]={}
            station = stations[key]
            delay = -np.dot(src_dir, station)/c
            delaySamps = int(ts*Fs+np.round(delay*Fs))
            signal = np.zeros(times.size)
            if frequency == 0:
                signal = amplitude*np.random.randn(times.size)
            else:
                # most of our noise spectra will be one-sided, but this is a real
                # signal, so we multiply this by two.
                signal = amplitude * np.cos(2*np.pi*frequency*times + phase)
                signal_phaseoff = -amplitude * np.sin(2*np.pi*frequency * times + phase)
            # impose time delay
            amp = np.roll(signal,delaySamps)[:Nsamps]* np.exp(-station[2]/alpha)
            amp2 = np.roll(signal_phaseoff, delaySamps)[:Nsamps]*\
                np.exp(station[2]/alpha)
            data[key]['HHE'] = cphi * Trace(amp, sample_rate=Fs,
                    times=final_times, unit=u.m)
            data[key]['HHN'] = sphi * Trace(amp, sample_rate=Fs,
                    times=final_times,unit=u.m)
            data[key]['HHZ'] = epsilon * Trace(amp2, sample_rate=Fs,
                    times=final_times,unit=u.m)
            for key2 in data[key].keys():
                data[key][key2].location = station
        return data

    def add_p_wave(self, amplitude, phi, theta, frequency,
            duration, phase=0, Fs=100, c=5700):
        """
        add a p wave to this data
        """
        locations = self.get_locations()
        p_data = SeismometerArray._gen_pwave(locations, amplitude, phi, theta,
                frequency, duration, phase=phase, Fs=Fs, c=c
                )
        self._add_another_seismometer_array(p_data)

    def add_s_wave(self, amplitude, phi, theta, psi, frequency,
            duration, phase=0, Fs=100, c=3000):
        """
        simulate s-wave in a certain direction

        Parameters
        ----------
        stations : `dict`
            dictionary of station locations
        A : `float`
            amplitude of input wave
        phi : `float`
            azimuth in radians
        theta : `float`
            polar angle from north pole in radians
        psi : `float`
            s-wave polarization angle from horizontal
            E-N plane in radians
        frequency : `float`
            frequency of source
        duration : `float`
            duration of signal to simulate
        Fs : `float`, optional, default=100 Hz
            sample rate (int preferred)
        c : `float`, optional, default=3000 m/s
            speed of wave
        phase : `float`, optional, default=0
            phase delay of wave in radians

        Returns
        -------
        data : `dict`
            2-layer dict with first keys as stations,
            second keys as channels for each station.
            Each entry is the data for that channel
            for that station for a simulated wave.
        """
        locations = self.get_locations()
        s_data = SeismometerArray._gen_swave(locations, amplitude, phi,
                theta,psi,frequency, duration, phase=phase, Fs=Fs, c=c
                )
        self._add_another_seismometer_array(s_data)

    def add_r_wave(self, amplitude, phi, theta, epsilon, alpha, frequency,
            duration, phase=0, Fs=100, c=200):
        """
        add an r-wave to this data
        """
        locations = self.get_locations()
        r_data = SeismometerArray._gen_rwave(locations, amplitude, phi,
                theta, epsilon, alpha,frequency, duration, phase=phase, Fs=Fs, c=c
                )
        self._add_another_seismometer_array(r_data)

    @classmethod
    def initialize_all_good(cls, location_dict, duration, chans_type='useful',
            start_time=0):
        data = cls()
        for name in location_dict.keys():
            data[name] = Seismometer.initialize_all_good(duration,
            chans_type=chans_type, start_time=start_time,
            location=location_dict[name], name=name)
        return data

    @classmethod
    def _gen_white_gaussian_noise(cls, station_names, psd_amp, sample_rate,
            duration, segdur=None, seed=None):
        if segdur is None:
            segdur=duration
        data = SeismometerArray()
        psd = FrequencySeries(psd_amp * np.ones(100000), df=1./(segdur))
        psd[0]=0
        for station in station_names:
            data[station] = Seismometer.initialize_all_good(duration=segdur)
            # set data channels to white noise
            data[station]['HHE'] = gaussian.noise_from_psd(duration,
                    sample_rate, psd, seed=seed, name=station, unit=u.m)
            data[station]['HHN'] = gaussian.noise_from_psd(duration,
                    sample_rate, psd, seed=seed, name=station, unit=u.m)
            data[station]['HHZ'] = gaussian.noise_from_psd(duration,
                    sample_rate, psd, seed=seed, name=station, unit=u.m)
        return data

    def get_locations(self):
        location_dir = OrderedDict()
        for seismometer in self.keys():
            location_dir[seismometer] =\
                    self[seismometer]['HHE'].location
        return location_dir

    def add_white_noise(self, psd_amp, segdur=None, seed=0):
        """
        Add some white noise to your seismometer array.
        Each channel with have a different noise realization
        but the same white noise amplitude.
        This done in place.
        """
        sensors = self.keys()
        # get duration
        Fs = self[sensors[0]]['HHE'].sample_rate.value
        duration = self[sensors[0]]['HHE'].size / Fs
        WN_array = SeismometerArray._gen_white_gaussian_noise(sensors, psd_amp,
                Fs, duration, segdur=segdur, seed=seed)
        self._add_another_seismometer_array(WN_array)

    def _add_another_seismometer_array(self, other):
        """
        Internal method for adding two arrays
        that have all of the same station names.
        This shoudl only be used for simulation purposes.
        This is for combining noise and/or signal
        injections
        """
        for sensor in self.keys():
            # only care about HHE, HHZ, HHN for this
            # since we're simulating stuff
            self[sensor]['HHE'] += other[sensor]['HHE']
            self[sensor]['HHN'] += other[sensor]['HHN']
            self[sensor]['HHZ'] += other[sensor]['HHZ']

    def p_wave_recovery_matrices(self, station_locs, recovery_freq, vp=5700, autocorrelations=True,
            channels=None, phis=None, thetas=None, fftlength=2, overlap=1,
            nproc=1, iter_lim=1000, atol=1e-6, btol=1e-6):
        """
        Recover p-wave data

        Parameters
        ----------
        recovery_freq : `float`
            frequency of recovery
        autocorrelations : `bool`
            Would you like to use autocorrelations in recovery?
        channels : `list`
            list of channels of data to use

        Returns
        -------
        GG : `numpy.ndarray`
            :math:`\gamma^T * \gamma`
        GY : `numpy.ndarray`
            :math:`\gamma \hat Y`
        gamma_shape : `tuple`
            final shape to use to reshape matrices
            after solutions
        """
        stations = self.keys()
        if channels is None:
            channels = ['HHE','HHN','HHZ']
        First = True
        for ii,station1 in enumerate(stations):
            for jj,station2 in enumerate(stations):
                for kk,chan1 in enumerate(channels):
                    for ll,chan2 in enumerate(channels):
                        if jj<ii:
                            # we don't double count stations
                            continue
                        elif ll < kk:
                            # don't double count channels
                            continue
                        elif autocorrelations is False and ll==kk and jj==ii:
                            continue
                        else:
                            P12 =\
                            self[station1][channels[kk]].csd_spectrogram(self[station2][channels[ll]],
                                    stride=fftlength,
                                    window='hann',overlap=overlap, nproc=nproc)
                            cp = (P12).mean(0)
                            idx = np.where(cp.frequencies.value==recovery_freq)
                            p12 = cp[idx]
                            #print np.sqrt(np.abs(p12) * 1/3600 * u.Hz)
                            gamma, phis, thetas =\
                                orf_p_directional(set_channel_vector(channels[kk]),
                                        set_channel_vector(channels[ll]),station_locs[station1],
                                        station_locs[station2], vp, recovery_freq, thetas=thetas, phis=phis)
                            gamma_shape = gamma.shape
                            gamma = gamma.reshape((gamma.size,1))
                            if First:
                                GG = np.dot(np.conj(gamma), np.transpose(gamma))
                                GY = np.conj(gamma)*p12
                                First = 0
                            else:
                                GG += np.dot(np.conj(gamma), np.transpose(gamma))
                                GY += np.conj(gamma)*p12
        S = lsqr(np.real(GG), np.real(GY.value), iter_lim=iter_lim, atol=atol,
                btol=btol)
        print 'Stopped at iteration number ' + str(S[2])
        if S[1]==1:
            print "We've found an exact solution"
        if S[1]==2:
            print "We found an approximate solution"
        print 'Converged to a relative residual of '+str(S[3] /
                np.sqrt((np.abs(GY.value)**2).sum()))
        final_map_p = np.copy(S[0].reshape(gamma_shape))
        return final_map_p, phis, thetas

    def r_wave_recovery_matrices(self, station_locs, epsilon, alpha,
            recovery_freq, vr=200, autocorrelations=True,
            channels=None, phis=None, thetas=None, fftlength=2, overlap=1,
            nproc=1, iter_lim=1000, atol=1e-6, btol=1e-6):
        """
        Recover p-wave data

        Parameters
        ----------
        recovery_freq : `float`
            frequency of recovery
        autocorrelations : `bool`
            Would you like to use autocorrelations in recovery?
        channels : `list`
            list of channels of data to use

        Returns
        -------
        GG : `numpy.ndarray`
            :math:`\gamma^T * \gamma`
        GY : `numpy.ndarray`
            :math:`\gamma \hat Y`
        gamma_shape : `tuple`
            final shape to use to reshape matrices
            after solutions
        """
        stations = self.keys()
        if channels is None:
            channels = ['HHE','HHN','HHZ']
        First = True
        for ii,station1 in enumerate(stations):
            for jj,station2 in enumerate(stations):
                for kk,chan1 in enumerate(channels):
                    for ll,chan2 in enumerate(channels):
                        if jj<ii:
                            # we don't double count stations
                            continue
                        elif ll < kk:
                            # don't double count channels
                            continue
                        else:
                            P12 =\
                            self[station1][channels[kk]].csd_spectrogram(self[station2][channels[ll]],
                                    stride=fftlength,
                                    window='hann',overlap=overlap, nproc=nproc)
                            cp = (P12).mean(0)
                            idx = np.where(cp.frequencies.value==recovery_freq)
                            p12 = cp[idx]
                            gamma, phis, thetas =\
                                orf_r_directional(set_channel_vector(channels[kk]),
                                        set_channel_vector(channels[ll]),station_locs[station1],
                                        station_locs[station2], epsilon,
                                        alpha, vr, recovery_freq, thetas=thetas, phis=phis)
                            gamma_shape = gamma.shape
                            gamma = gamma.reshape((gamma.size,1))
                            if First:
                                GG = np.dot(np.conj(gamma), np.transpose(gamma))
                                GY = np.conj(gamma)*p12
                                First = 0
                            else:
                                GG += np.dot(np.conj(gamma), np.transpose(gamma))
                                GY += np.conj(gamma)*p12
        S = lsqr(np.real(GG), np.real(GY.value), iter_lim=iter_lim, atol=atol,
                btol=btol)
        print 'Stopped at iteration number ' + str(S[2])
        if S[1]==1:
            print "We've found an exact solution"
        if S[1]==2:
            print "We found an approximate solution"
        print 'Converged to a relative residual of '+str(S[3] /
                np.sqrt((np.abs(GY.value)**2).sum()))
        final_map_p = np.copy(S[0].reshape(gamma_shape))
        return final_map_p, phis, thetas

    def p_and_s_wave_recovery_matrices(self, station_locs, recovery_freq,
            vs=3000, vp=5700, autocorrelations=True,
            channels=None, phis=None, thetas=None, fftlength=2, overlap=1,
            nproc=1,iter_lim=1000, atol=1e-6, btol=1e-6):
        """
        Recover s-wave data

        Parameters
        ----------
        recovery_freq : `float`
            frequency of recovery
        autocorrelations : `bool`
            Would you like to use autocorrelations in recovery?
        channels : `list`
            list of channels of data to use

        Returns
        -------
        GG : `numpy.ndarray`
            :math:`\gamma^T * \gamma`
        GY : `numpy.ndarray`
            :math:`\gamma \hat Y`
        gamma_shape : `tuple`
            final shape to use to reshape matrices
            after solutions
        gamma1_shape : `tuple`
            final shape to use to reshape matrices
            after solutions
        gamma2_shape : `tuple`
            final shape to use to reshape matrices
            after solutions
        """
        stations = self.keys()
        if channels is None:
            channels = ['HHE','HHN','HHZ']
        First = True
        for ii,station1 in enumerate(stations):
            for jj,station2 in enumerate(stations):
                for kk,chan1 in enumerate(channels):
                    for ll,chan2 in enumerate(channels):
                        if jj<ii:
                            # we don't double count stations
                            continue
                        if ll < kk:
                            # don't double count channels
                            continue
                        else:
                            P12 =\
                            self[ii][channels[kk]].csd_spectrogram(self[jj][channels[ll]],
                                    stride=fftlength,
                                    window='hann',overlap=overlap, nproc=nproc)
                            cp = (P12).mean(0)
                            idx = np.where(cp.frequencies.value==recovery_freq)
                            p12 = cp[idx]
                            gamma1, gamma2, phis, thetas =\
                                orf_s_directional(set_channel_vector(channels[kk]),
                                        set_channel_vector(channels[ll]),station_locs[station1],
                                        station_locs[station2], vs, recovery_freq, thetas=thetas, phis=phis)
                            gammap, phis, thetas =\
                                orf_p_directional(set_channel_vector(channels[kk]),
                                        set_channel_vector(channels[ll]),station_locs[station1],
                                        station_locs[station2], vp, recovery_freq, thetas=thetas, phis=phis)

                            gamma1_shape = gamma1.shape
                            gamma2_shape = gamma2.shape
                            gammap_shape = gammap.shape
                            gamma1 = gamma1.reshape((gamma1.size,1))
                            gamma2 = gamma2.reshape((gamma2.size,1))
                            gammap = gammap.reshape((gammap.size,1))
                            gamma = np.vstack((gamma1,gamma2,gammap))
                            gamma_shape = gamma.shape
                            if First:
                                GG = np.dot(np.conj(gamma), np.transpose(gamma))
                                GY = np.conj(gamma)*p12
                                First = 0
                            else:
                                GG += np.dot(np.conj(gamma), np.transpose(gamma))
                                GY += np.conj(gamma)*p12
        S = lsqr(np.real(GG), np.real(GY.value), iter_lim=iter_lim, atol=atol,
                btol=btol)
        print 'Stopped at iteration number ' + str(S[2])
        if S[1]==1:
            print "We've found an exact solution"
        if S[1]==2:
            print "We found an approximate solution"
        print 'Converged to a relative residual of '+str(S[3] /
                np.sqrt((np.abs(GY.value)**2).sum()))
        final_map = np.copy(S[0].reshape(gamma.shape))
        final_map_pol1 = final_map[:gamma1.size]
        final_map_pol2 = final_map[gamma1.size:(gamma1.size+gamma2.size)]
        final_map_p = final_map[(gamma1.size+gamma2.size):]
        return final_map_pol1, final_map_pol2, final_map_p, phis, thetas

    def s_wave_recovery_matrices(self, station_locs, recovery_freq, vs=3000, autocorrelations=True,
            channels=None, phis=None, thetas=None, fftlength=2, overlap=1,
            nproc=1,iter_lim=1000, atol=1e-6, btol=1e-6):
        """
        Recover p and s-wave data at the same time

        Parameters
        ----------
        recovery_freq : `float`
            frequency of recovery
        autocorrelations : `bool`
            Would you like to use autocorrelations in recovery?
        channels : `list`
            list of channels of data to use

        Returns
        -------
        GG : `numpy.ndarray`
            :math:`\gamma^T * \gamma`
        GY : `numpy.ndarray`
            :math:`\gamma \hat Y`
        gamma_shape : `tuple`
            final shape to use to reshape matrices
            after solutions
        gammap_shape : `tuple`
            final shape to use to reshape matrices
            after solutions
        gamma1_shape : `tuple`
            final shape to use to reshape matrices
            after solutions
        gamma2_shape : `tuple`
            final shape to use to reshape matrices
            after solutions
        """
        stations = self.keys()
        if channels is None:
            channels = ['HHE','HHN','HHZ']
        First = True
        for ii,station1 in enumerate(stations):
            for jj,station2 in enumerate(stations):
                for kk,chan1 in enumerate(channels):
                    for ll,chan2 in enumerate(channels):
                        if jj<ii:
                            # we don't double count stations
                            continue
                        if ll < kk:
                            # don't double count channels
                            continue
                        else:
                            P12 =\
                            self[ii][channels[kk]].csd_spectrogram(self[jj][channels[ll]],
                                    stride=fftlength,
                                    window='hann',overlap=overlap, nproc=nproc)
                            cp = (P12).mean(0)
                            idx = np.where(cp.frequencies.value==recovery_freq)
                            p12 = cp[idx]
                            gamma1, gamma2, phis, thetas =\
                                orf_s_directional(set_channel_vector(channels[kk]),
                                        set_channel_vector(channels[ll]),station_locs[station1],
                                        station_locs[station2], vs, recovery_freq, thetas=thetas, phis=phis)
                            gamma1_shape = gamma1.shape
                            gamma2_shape = gamma2.shape
                            gamma1 = gamma1.reshape((gamma1.size,1))
                            gamma2 = gamma2.reshape((gamma2.size,1))
                            gamma = np.vstack((gamma1,gamma2))
                            gamma_shape = gamma.shape
                            if First:
                                GG = np.dot(np.conj(gamma), np.transpose(gamma))
                                GY = np.conj(gamma)*p12
                                First = 0
                            else:
                                GG += np.dot(np.conj(gamma), np.transpose(gamma))
                                GY += np.conj(gamma)*p12
        S = lsqr(np.real(GG), np.real(GY.value), iter_lim=iter_lim, atol=atol,
                btol=btol)
        print 'Stopped at iteration number ' + str(S[2])
        if S[1]==1:
            print "We've found an exact solution"
        if S[1]==2:
            print "We found an approximate solution"
        print 'Converged to a relative residual of '+str(S[3] /
                np.sqrt((np.abs(GY.value)**2).sum()))
        final_map = np.copy(S[0].reshape(gamma.shape))
        final_map_pol1 = final_map[:gamma1.size]
        final_map_pol2 = final_map[gamma1.size:]
        return final_map_pol1, final_map_pol2, phis, thetas

    def recovery_matrices(self, rec_str, station_locs, recovery_freq,
            v_list, autocorrelations=True, epsilon=0.1, alpha=1000,
            channels=None, phis=None, thetas=None, fftlength=2, overlap=1,
            nproc=1,iter_lim=1000, atol=1e-6, btol=1e-6):
        """
        Recover everything or anything

        Parameters
        ----------
        recovery_freq : `float`
            frequency of recovery
        autocorrelations : `bool`
            Would you like to use autocorrelations in recovery?
        channels : `list`
            list of channels of data to use

        Returns
        -------
        GG : `numpy.ndarray`
            :math:`\gamma^T * \gamma`
        GY : `numpy.ndarray`
            :math:`\gamma \hat Y`
        gamma_shape : `tuple`
            final shape to use to reshape matrices
            after solutions
        gamma1_shape : `tuple`
            final shape to use to reshape matrices
            after solutions
        gamma2_shape : `tuple`
            final shape to use to reshape matrices
            after solutions
        """
        stations = self.keys()
        if channels is None:
            channels = ['HHE','HHN','HHZ']
        First = True
        for ii,station1 in enumerate(stations):
            for jj,station2 in enumerate(stations):
                for kk,chan1 in enumerate(channels):
                    for ll,chan2 in enumerate(channels):
                        if jj<ii:
                            # we don't double count stations
                            continue
                        if ll < kk:
                            # don't double count channels
                            continue
                        else:
                            P12 =\
                            self[station1][channels[kk]].csd_spectrogram(self[station2][channels[ll]],
                                    stride=fftlength,
                                    window='hann',overlap=overlap, nproc=nproc)
                            cp = (P12).mean(0)
                            idx =\
                                np.where(cp.frequencies.value==float(recovery_freq))
                            p12 = cp[idx[0]-1:idx[0]+2].sum()
                            g = []
                            shapes = []
                            for rec, v in zip(rec_str, v_list):
                                if rec is 's':
                                    g1, g2, g1_s, g2_s = orf_picker(rec, set_channel_vector(channels[kk]),
                                        set_channel_vector(channels[ll]),station_locs[station1],
                                        station_locs[station2], v,
                                        float(recovery_freq), thetas=thetas, phis=phis,
                                                 epsilon=epsilon, alpha=alpha)
                                    shapes.append(g1_s)
                                    shapes.append(g2_s)
                                    if len(g) > 0:
                                        g = np.vstack((g, g1, g2))
                                    else:
                                        g = np.vstack((g1, g2))
                                else:
                                    g1, g_s = orf_picker(rec, set_channel_vector(channels[kk]),
                                        set_channel_vector(channels[ll]),station_locs[station1],
                                        station_locs[station2],
                                        v,float(recovery_freq), thetas=thetas, phis=phis,
                                        epsilon=epsilon, alpha=alpha)
                                    try:
                                        g = np.vstack((g, g1))
                                    except ValueError:
                                        g = g1
                                    shapes.append(g_s)
                            if First:
                                GG = np.dot(np.conj(g), np.transpose(g))
                                GY = np.conj(g)*p12
                                First = 0
                            else:
                                GG += np.dot(np.conj(g), np.transpose(g))
                                GY += np.conj(g)*p12
        S = lsqr(np.real(GG), np.real(GY.value), iter_lim=iter_lim, atol=atol,
                btol=btol)
        maps = {}
        idx_low = 0
        if thetas is None:
            thetas = np.arange(3,180,6) * np.pi / 180
        if phis is None:
            phis = np.arange(3,360,6) * np.pi / 180
        for ii, rec in enumerate(rec_str):
            if rec is 's':
                length = shapes[ii][0] * shapes[ii][1]
                maps['s1'] =\
                        RecoveryMap(S[0].reshape(g.shape)[idx_low:idx_low+length].reshape(shapes[ii]),
                                thetas, phis, 's1')
                idx_low += length
                maps['s2'] =\
                        RecoveryMap(S[0].reshape(g.shape)[idx_low:idx_low+length].reshape(shapes[ii]),
                                thetas, phis, 's2')
            else:
                length = shapes[ii][0] * shapes[ii][1]
                maps[rec] =\
                    RecoveryMap(S[0].reshape(g.shape)[idx_low:idx_low+length].reshape(shapes[ii]),
                            thetas, phis, rec)
                idx_low += length

        #print 'Stopped at iteration number ' + str(S[2])
        #if S[1]==1:
        #    print "We've found an exact solution"
        #if S[1]==2:
        #    print "We found an approximate solution"
        #print 'Converged to a relative residual of '+str(S[3] /
        #        np.sqrt((np.abs(GY.value)**2).sum()))
        return maps, phis, thetas
