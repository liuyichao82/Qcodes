import pytest
import numpy as np
from collections import Counter

from qcodes.instrument_drivers.tektronix.Keithley_2600_channels import \
    Keithley_2600

import qcodes.instrument.sims as sims
visalib = sims.__file__.replace('__init__.py', 'Keithley_2600.yaml@sim')


@pytest.fixture(scope='function')
def driver():
    driver = Keithley_2600('Keithley_2600',
                           address='GPIB::1::INSTR',
                           visalib=visalib)

    yield driver
    driver.close()


def test_idn(driver):
    assert {'firmware': '3.0.0',
            'model': '2601B',
            'serial': '1398687',
            'vendor': 'Keithley Instruments Inc.'} == driver.IDN()


def test_smu_channels_and_their_parameters(driver):
    assert {'smua', 'smub'} == set(list(driver.submodules.keys()))

    for smu_name in {'smua', 'smub'}:
        smu = getattr(driver, smu_name)

        smu.volt(1.0)
        assert 1.0 == smu.volt()

        smu.curr(1.0)
        assert 1.0 == smu.curr()

        assert 0.0 == smu.res()

        assert 'current' == smu.mode()
        smu.mode('voltage')
        assert smu.mode() == 'voltage'

        assert smu.output() is False
        smu.output(True)
        assert smu.output() is True

        assert 0.0 == smu.nplc()
        smu.nplc(2.3)
        assert smu.nplc() == 2.3

        assert 0.0 == smu.sourcerange_v()
        some_valid_sourcerange_v = driver._vranges[smu.model][2]
        smu.sourcerange_v(some_valid_sourcerange_v)
        assert smu.sourcerange_v() == some_valid_sourcerange_v

        assert smu.source_autorange_v_enabled() is False
        smu.source_autorange_v_enabled(True)
        assert smu.source_autorange_v_enabled() is True

        assert 0.0 == smu.measurerange_v()
        some_valid_measurerange_v = driver._vranges[smu.model][2]
        smu.measurerange_v(some_valid_measurerange_v)
        assert smu.measurerange_v() == some_valid_measurerange_v

        assert smu.measure_autorange_v_enabled() is False
        smu.measure_autorange_v_enabled(True)
        assert smu.measure_autorange_v_enabled() is True

        assert 0.0 == smu.sourcerange_i()
        some_valid_sourcerange_i = driver._iranges[smu.model][2]
        smu.sourcerange_i(some_valid_sourcerange_i)
        assert smu.sourcerange_i() == some_valid_sourcerange_i

        assert smu.source_autorange_i_enabled() is False
        smu.source_autorange_i_enabled(True)
        assert smu.source_autorange_i_enabled() is True

        assert 0.0 == smu.measurerange_i()
        some_valid_measurerange_i = driver._iranges[smu.model][2]
        smu.measurerange_i(some_valid_measurerange_i)
        assert smu.measurerange_i() == some_valid_measurerange_i

        assert smu.measure_autorange_i_enabled() is False
        smu.measure_autorange_i_enabled(True)
        assert smu.measure_autorange_i_enabled() is True

        assert 0.0 == smu.limitv()
        smu.limitv(2.3)
        assert smu.limitv() == 2.3

        assert 0.0 == smu.limiti()
        smu.limiti(2.3)
        assert smu.limiti() == 2.3

        assert 'current' == smu.timetrace_mode()
        smu.timetrace_mode('voltage')
        assert smu.timetrace_mode() == 'voltage'

        assert 500 == smu.timetrace_npts()
        smu.timetrace_npts(600)
        assert smu.timetrace_npts() == 600

        assert 0.001 == smu.timetrace_dt()
        smu.timetrace_dt(0.002)
        assert smu.timetrace_dt() == 0.002

        dt = smu.timetrace_dt()
        npts = smu.timetrace_npts()
        expected_time_axis = np.linspace(0, dt*npts, npts, endpoint=False)
        assert len(expected_time_axis) == len(smu.time_axis())
        assert Counter(expected_time_axis) == Counter(smu.time_axis())
        assert set(expected_time_axis) == set(smu.time_axis())

        smu.timetrace_mode('current')
        assert 'A' == smu.timetrace.unit
        assert 'Current' == smu.timetrace.label
        assert smu.time_axis == smu.timetrace.setpoints[0]

        smu.timetrace_mode('voltage')
        assert 'V' == smu.timetrace.unit
        assert 'Voltage' == smu.timetrace.label
        assert smu.time_axis == smu.timetrace.setpoints[0]
