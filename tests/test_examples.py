"""The examples run, and demonstrate what they claim."""

from __future__ import absolute_import, division, print_function

import math
import os
import sys

sys.path.insert( 0, os.path.join( os.path.dirname( os.path.dirname( os.path.abspath( __file__ ))), 'examples' ))

import comfort_lines    # noqa: E402
import radiant_room     # noqa: E402


def test_comfort_lines( capsys ):
    lines                       = comfort_lines.main( [ '--step', '5' ] )
    assert capsys.readouterr().out.startswith( "t_r, t_a(clo=1.0;met=1.0)" )
    for col in range( 1, len( comfort_lines.CASES ) + 1 ):
        t_a                     = [ row[col] for row in lines if not math.isnan( row[col] ) ]
        assert all( a > b for a, b in zip( t_a, t_a[1:] ))      # Warmer radiant ==> cooler air
    # More clothing or activity ==> cooler air for neutral comfort
    assert all( row[1] < row[3] and row[2] < row[1] for row in lines )


def test_radiant_room( capsys ):
    common                      = [ '--hours', '24', '--room', 'sunroom' ]
    air, air_btu                = radiant_room.main( common + [ '--mode', 'air', '--setpoint', '21' ] )
    pmv, pmv_btu                = radiant_room.main( common + [ '--mode', 'comfort' ] )
    assert "Boiler:" in capsys.readouterr().out
    sun                         = sorted( radiant_room.ROOMS ).index( 'sunroom' ) + 3
    # After warming up, the air thermostat holds the air temperature, but the sunroom feels cool;
    # the comfort thermostat holds PMV ~0 with warmer air, burning a little more fuel.
    for row in air[12:]:
        t_a, t_r, p, ppd        = row[sun]
        assert abs( t_a - 21 ) < 1 and t_r < t_a and p < -.1
    for row in pmv[12:]:
        t_a, t_r, p, ppd        = row[sun]
        assert abs( p ) < .25 and t_a > 21 and ppd < 7
    assert air_btu < pmv_btu
