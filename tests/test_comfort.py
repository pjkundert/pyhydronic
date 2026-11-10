"""Fanger's comfort equation: PMV, PPD, and helpers."""

from __future__ import absolute_import, division, print_function

import math

import pytest

from hydronic import Error, fanger
from hydronic.misc import near


def test_humidity():
    f                           = fanger( mit=False )
    P_w                         = f.P_w( t_a=20., hum=.5 )
    assert near( P_w, 1168.6 )
    assert near( f.t_d( e=P_w ), 9.271 )                        # dewpoint
    assert near( f.p_sat( t_a=20. ) * .5, 1168.6 )


def test_fanger_terms():
    f                           = fanger( mit=False )

    # The simplified Fanger equation based on desired/perceived temperatures
    des, per                    = f.t_sub( M=f.M( met=1.2 ), I_cl=f.I_cl( clo=.8 ), t_a=20, t_r=15, v=0 )
    assert near( des, 27.128 )
    assert near( per, 17.8 )

    I_cl                        = f.I_cl( clo=.8 )
    assert near( I_cl, 0.124 )
    f_cl                        = f.f_cl( I_cl=I_cl )
    assert near( f_cl, 1.130 )
    M                           = f.M( met=1.2 )
    t_cl, h_c                   = f.t_cl_h_c( M=M, W=0, I_cl=I_cl, f_cl=f_cl, v=0, t_a=20., t_r=15. )
    assert near( t_cl, 25.2323 )
    assert near( h_c,   3.5993 )


@pytest.mark.parametrize( "xn, t_a, t_r, t_cl_expect", [
    ( 2.9194505366000816, 18.79444544017561,  14.251083402047804, 18.79413349 ),
    ( 2.9814100885428747, 24.989128226382643, 22.458774905050937, 24.99079679 ),
] )
def test_t_cl_convergence( xn, t_a, t_r, t_cl_expect ):
    """Corner cases which failed to refine at high levels of precision, due to exceeding the precision
    capabilities of the underlying floating-point representation.  To ensure we begin with the
    offending xn value, we pre-charge fanger._t_cl:  xn * 100 - 273.15 = self._t_cl

    """
    f                           = fanger( mit=False )
    error                       = 1e-3
    while error > 1e-10:
        try:
            f._t_cl             = xn * 100 - 273.15
            t_cl, h_c           = f.t_cl_h_c( M=46.4, W=0.0, I_cl=0.465, f_cl=1.9, v=0.0,
                                              t_a=t_a, t_r=t_r, error=error )
            assert near( t_cl, t_cl_expect, significance=error * 10 )
        except Error as exc:
            assert error <= 1e-5, "Should NOT have raised exception; should have refined: %s" % exc
        error                  /= 10


#     t_a,  t_r,   v, rh, met, clo,   PMV (mit=False), PMV (mit=True)  # suggested
PMV_CASES                       = [
    # From ISO 7730
    ( 19.0, 18.0, 0.1, 40, 1.2, 1.0,   -0.677, -0.827  ),  #   0: -0.7
    ( 22.0, 22.0, 0.1, 60, 1.2, 0.5,   -0.712, -0.799  ),  #   1: -0.75
    ( 27.0, 27.0, 0.1, 60, 1.2, 0.5,    0.807,  0.752  ),  #   2: +0.77
    ( 27.0, 27.0, 0.3, 60, 1.2, 0.5,    0.475,  0.426  ),  #   3: +0.44
    ( 23.5, 25.5, 0.1, 60, 1.2, 0.5,    0.0203,-0.0457 ),  #   4: -0.01
    ( 23.5, 25.5, 0.3, 60, 1.2, 0.5,   -0.516, -0.586  ),  #   5: -0.55
    ( 19.0, 19.0, 0.1, 40, 1.2, 1.0,   -0.579, -0.724  ),  #   6: -0.60
    ( 23.5, 23.5, 0.1, 40, 1.2, 1.0,    0.386,  0.286  ),  #   7:  0.5
    ( 23.5, 23.5, 0.3, 40, 1.2, 1.0,    0.147,  0.0542 ),  #   8:  0.12
    ( 23.0, 21.0, 0.1, 40, 1.2, 1.0,    0.0751,-0.0401 ),  #   9:  0.05
    ( 23.0, 21.0, 0.3, 40, 1.2, 1.0,   -0.142, -0.246  ),  #  10: -0.16
    ( 22.0, 22.0, 0.1, 60, 1.6, 0.5,    0.0699, 0.0118 ),  #  11:  0.05
    ( 27.0, 27.0, 0.1, 60, 1.6, 0.5,    1.20,   1.17   ),  #  12:  1.17
    ( 27.0, 27.0, 0.3, 60, 1.6, 0.5,    0.989,  0.95   ),  #  13:  0.95
    # From a 2007 greenbuilding listserv discussion (repp.org; since gone)
    ( 19.6, 19.6, 0.1, 86, 1.1, 1.0,   -0.452, -0.608  ),  #     -0.477
    ( 23.9, 23.9, 0.1, 66, 1.1, 1.0,    0.502,  0.394  ),  #      0.473
    ( 25.7, 25.7, 0.1, 15, 1.1, 1.0,    0.554,  0.465  ),  #      0.523
    ( 21.2, 21.2, 0.1, 20, 1.1, 1.0,   -0.451, -0.589  ),  #     -0.478
    ( 23.6, 23.6, 0.1, 67, 1.1, 0.5,   -0.436, -0.519  ),  #     -0.475
    ( 26.8, 26.8, 0.1, 56, 1.1, 0.5,    0.556,  0.500  ),  #      0.514
    ( 27.9, 27.9, 0.1, 13, 1.1, 0.5,    0.540,  0.492  ),  #      0.500
    ( 24.7, 24.7, 0.1, 16, 1.1, 0.5,   -0.450, -0.519  ),  #     -0.488
]


@pytest.mark.parametrize( "t_a, t_r, v, rh, met, clo, pmv, pmv_mit", PMV_CASES )
def test_pmv( t_a, t_r, v, rh, met, clo, pmv, pmv_mit ):
    """PMV to within 1 part in 100, via L(), PMV(), or construction-time terms."""
    kwds                        = dict( met=met, clo=clo, W=0., v=v, t_r=t_r, t_a=t_a, hum=rh / 100. )
    assert near( fanger( mit=False ).L( **kwds ), pmv, significance=1. / 100 )
    assert near( fanger( mit=True ).L( **kwds ), pmv_mit, significance=1. / 100 )
    assert near( fanger( mit=True ).PMV( **kwds ), pmv_mit, significance=1. / 100 )
    assert near( fanger( mit=True, **kwds ).PMV(), pmv_mit, significance=1. / 100 )


def test_ppd():
    f                           = fanger( t_r=22, hum=.5 )
    pmv                         = f.PMV( t_a=22 )
    assert 5. <= f.PPD( t_a=22 ) <= 100.
    # ISO 7730 Figure 1: PPD is 5% at neutral, ~10% at +/-0.5, ~26% at +/-1
    for t_a in ( 18, 22, 26 ):
        p                       = f.PMV( t_a=t_a )
        assert abs( f.PPD( t_a=t_a ) - ( 100 - 95 * math.exp( -0.03353 * p**4 - 0.2179 * p**2 ))) < 1e-3
    neutral                     = f.setpoint()
    assert near( f.PPD( t_a=neutral ), 5., significance=1e-3 )
    assert pmv < 0                                              # 22C is slightly cool, at 0.8 clo
    # PPD is symmetric in PMV; at PMV +/-1 it is ~26.1%
    assert near( f.PPD( t_a=f.setpoint( pmv=+1 )), 26.1, significance=1e-2 )
    assert near( f.PPD( t_a=f.setpoint( pmv=-1 )), 26.1, significance=1e-2 )


def test_setpoint():
    f                           = fanger( clo=1.0, met=1.2, hum=.5 )
    # A cold radiant environment (eg. big windows) needs warmer air; a warm radiant floor, cooler air
    cold, warm                  = f.setpoint( t_r=16. ), f.setpoint( t_r=26. )
    assert cold > warm + 5
    for t_r, t_a in ( ( 16., cold ), ( 26., warm )):
        assert abs( f.PMV( t_a=t_a, t_r=t_r )) < 1e-3
    with pytest.raises( Error ):
        f.setpoint( t_r=20., t_a=20. )
    with pytest.raises( Error ):
        f.setpoint( t_r=20., pmv=+3, hi=25. )                   # Not attainable


def test_humidity_tracks_t_a():
    """A relative humidity tracks the air temperature of each computation; a vapour pressure does not."""
    rh                          = fanger( t_a=20., t_r=20., hum=.5 )
    vp                          = fanger( t_a=20., t_r=20., P_w=rh.P_w( t_a=20., hum=.5 ))
    assert near( rh.PMV(), vp.PMV() )
    # (t_cl is refined iteratively from the last estimate, so PMV is reproducible to ~1e-4)
    assert abs( rh.PMV( t_a=26. ) - fanger( t_a=26., t_r=20., hum=.5 ).PMV() ) < 1e-3
    assert abs( rh.PMV( t_a=26. ) - vp.PMV( t_a=26. )) > 1e-2
    assert fanger( t_a=20., t_r=20., hum=0. ).PMV() < rh.PMV()  # Dry air is computable, and cooler


def test_construction():
    assert near( fanger( M=70. ).M(), 70. )                     # M without met, I_cl without clo
    assert near( fanger( I_cl=.155 ).I_cl(), .155 )
    assert near( fanger().M(), 1.2 * fanger.MET ) and near( fanger().I_cl(), 0.8 * fanger.CLO )
    for kwds in ( dict( met=1, M=58 ), dict( clo=1, I_cl=.155 ), dict( hum=.5, P_w=1000 ),
                  dict( met=10 ), dict( clo=4 )):
        with pytest.raises( Error ):
            fanger( **kwds )
    with pytest.raises( Error ):
        fanger( t_a=20 ).PMV()                                  # No t_r
    with pytest.raises( Error ):
        fanger( t_a=20, t_r=20 ).PMV()                          # No humidity


def test_descriptions():
    f                           = fanger( t_r=22., hum=.5 )
    feels                       = [ f.feels( t_a=f.setpoint( pmv=pmv, hi=60. )) for pmv in
                                    ( -3.5, -2.5, -1.5, -.5, .5, 1.5, 2.5 ) ]
    assert feels == [ "cold", "cool", "coolish", "ok", "ok", "warmish", "warm" ]
    assert fanger( t_r=40., t_a=40., hum=.5, clo=1.5, met=2 ).feels() == "hot"

    assert fanger( clo=.8 ).clothing()[2] == "casual"
    amount, clo, desc           = fanger().clothing( amount=.5 )
    assert near( clo, 1.5 ) and desc == "winter"
    assert fanger( met=1.2 ).metabolism()[2] == "standing"
    rate, met, desc             = fanger().metabolism( rate=1. )
    assert near( met, 3.0 ) and desc == "hard"
    # Adjusting clothing or metabolism is remembered
    f                           = fanger()
    f.clothing( amount=0. )
    assert f.clothing()[2] == "naked"
