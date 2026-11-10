#!/usr/bin/env python
"""Comfort lines: the air temperature giving neutral comfort (PMV 0), for each mean radiant temperature.

Replicates the "Comfort Lines" graph of Bruel & Kjaer Technical Review No. 2, 1982 "Thermal Comfort"
(p. 24; see docs/), for several clothing and activity levels.  Each degree C of radiant temperature
lost (eg. to cold windows) must be made up by roughly a degree of air temperature; a warm radiant
floor allows cooler air for the same comfort.  Emits CSV:

    python examples/comfort_lines.py > comfort.csv
"""

from __future__ import absolute_import, division, print_function

import argparse
import sys

from hydronic import Error, fanger

CASES                           = [     # (clo, met): indoor winter clothes or light summer, seated or standing
    ( 1.0, 1.0 ), ( 1.0, 1.2 ), ( 0.5, 1.0 ), ( 0.5, 1.2 ),
]


def main( argv=None ):
    ap                          = argparse.ArgumentParser( description=__doc__.split( '\n' )[0] )
    ap.add_argument( '--hum', type=float, default=0.5, help="Relative humidity (0,1)" )
    ap.add_argument( '--v', type=float, default=0.0, help="Air velocity (m/s)" )
    ap.add_argument( '--step', type=float, default=2.0, help="Mean radiant temperature step (C)" )
    ap.add_argument( '--classic', action='store_true', help="Use Fanger's original clothing area factor" )
    args                        = ap.parse_args( argv )

    comfort                     = [ fanger( clo=clo, met=met, hum=args.hum, v=args.v, mit=not args.classic )
                                    for clo, met in CASES ]
    print( ", ".join( [ "t_r" ] + [ "t_a(clo=%.1f;met=%.1f)" % c for c in CASES ] ))
    lines, t_r                  = [], 10.0
    while t_r <= 40.0:
        row                     = [ t_r ]
        for f in comfort:
            try:
                row.append( f.setpoint( t_r=t_r, lo=0.0, hi=45.0 ))
            except Error:
                row.append( float( 'nan' ))                     # Not attainable with air temperature
        print( ", ".join( "%6.2f" % v for v in row ))
        lines.append( row )
        t_r                    += args.step
    return lines


if __name__ == "__main__":
    sys.exit( main() and 0 )
