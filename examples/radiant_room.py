#!/usr/bin/env python
"""Two rooms on a hydronic radiant slab, under an air-temperature or a comfort (PMV) thermostat.

Generalized from a residential hydronic control system.  The thermal model estimates the temperature
of every wall, window, ceiling and floor, giving each room's mean radiant temperature and hence its
Fanger PMV -- what occupants actually feel.  A "sunroom" with lots of glass feels cool at an air
temperature that is comfortable in the snug "den"; a comfort thermostat compensates.

    python examples/radiant_room.py --mode air      # hold the sunroom air at 21C
    python examples/radiant_room.py --mode comfort  # hold the sunroom at PMV 0 (neutral)

The structure (US units; F, ft, BTU), as in the original system:

             world (outdoors)     attic roofs, walls, windows
         +-----------+---------+
         |  sunroom  |   den   |  <-- interior wall between
         +-----------+---------+
         | tile      | tile    |  <-- each room's floor surface (R0, film = floor covering)
         +-----------+---------+
         |    slab (concrete)  |
         |    zone (water)     |  <-- heat delivered here, by the boiler
         +---------------------+  <-- under-slab insulation
               ground
"""

from __future__ import absolute_import, division, print_function

import argparse
import math
import sys

from hydronic import (
    C_to_F, F_to_C, ft, resize, merge, area, environment, portal, space, fanger,
)

R                               = {         # Insulation (F.ft^2.h/BTU)
    'wall':         20,                     # 2x6 batt
    'interior':     10,
    'window':        2,                     # double glazed
    'attic':        50,
    'slab':          1,                     # concrete R1/in; tubes ~1/2 down a 4" slab
    'insulation':   10,                     # under-slab foam
    'tile':           .25,                  # tile and thinset, over the slab
    'film':           .5,                   # floor surface air film (heat flowing up)
}
CEILING                         = ft( 9 )

ROOMS                           = {         # name: (size, wall-to-world length, windows (w, h))
    'sunroom':      ( ( ft( 14 ), ft( 20 ), CEILING ), ft( 34 ), [ ( ft( 0, 36 ), ft( 0, 72 )) ] * 8 ),
    'den':          ( ( ft( 12 ), ft( 14 ), CEILING ), ft( 26 ), [ ( ft( 0, 30 ), ft( 0, 48 )) ] * 1 ),
}


def house( outside, now=0. ):
    """Build the world; returns (world, spaces) with all temperatures in F"""
    world                       = space( 'world', ( 1e4, 1e4, 1e4 ), environment( outside ), now=now )
    ground                      = space( 'ground', ( 1e4, 1e4, 1e4 ), environment( C_to_F( 5. ), 'soil' ), now=now )
    world.contains( ground )
    spaces                      = dict( world=world, ground=ground )

    zs                          = None
    for name, ( size, wall, windows ) in ROOMS.items():
        room = spaces[name]     = space( name, size, environment( C_to_F( 20. )), now=now )
        world.contains( room )
        glass                   = sum( area( w ) for w in windows )
        room.connects( portal( name + ' walls', 'world', ( wall, CEILING - glass / wall ), R['wall'] ))
        for i, w in enumerate( windows ):
            room.connects( portal( "%s window %d" % ( name, i ), 'world', w, R['window'] ))
        room.connects( portal( name + ' ceiling', 'world', size, R['attic'] ))

        # Each room's floor surface radiates at the tile temperature (R0); only its air film
        # resists heat flow into the room.
        floor = spaces[name + ' floor'] = space(
            name + ' floor', resize( size, h=ft( 0, .5 )), environment( C_to_F( 20. ), 'tile' ), now=now )
        room.contains( floor )
        room.connects( portal( name + ' floor', floor.name, size, R=0, film=R['film'] ))
        zs                      = merge( zs, size )
    spaces['sunroom'].connects( portal( 'interior wall', 'den', ( ft( 14 ), CEILING ), R['interior'] ))

    # The zone's water: 1/2" PEX on 12" centers holds ~.92 US gal/100ft, spread over the zone area.
    inches                      = area( zs ) * .92 / 100 * 231 / ( area( zs ) * 144 )
    zone = spaces['zone']       = space( 'zone', resize( zs, h=ft( 0, inches )),
                                         environment( C_to_F( 25. ), 'water' ), now=now )
    slab = spaces['slab']       = space( 'slab', resize( zs, h=ft( 0, 4 )),
                                         environment( C_to_F( 25. ), 'concrete' ), now=now )
    world.contains( zone )
    world.contains( slab )
    slab.connects( portal( 'fluid', 'zone', zs, R['slab'], film=0 ))
    for name in ROOMS:
        slab.connects( portal( name + ' flooring', name + ' floor', ROOMS[name][0], R['tile'], film=0 ))
    slab.connects( portal( 'insulation', 'ground', zs, R['insulation'], film=0 ))
    return world, spaces


def comfort( room, world, f ):
    """Returns (air C, mean radiant C, PMV, PPD) for a room"""
    t_a, t_r                    = F_to_C( room.conditions.temperature ), F_to_C( room.radiant( world ))
    pmv                         = f.PMV( t_a=t_a, t_r=t_r )
    return t_a, t_r, pmv, f.PPD( pmv=pmv )


def main( argv=None ):
    ap                          = argparse.ArgumentParser( description=__doc__.split( '\n' )[0] )
    ap.add_argument( '--mode', choices=( 'air', 'comfort' ), default='comfort' )
    ap.add_argument( '--room', choices=sorted( ROOMS ), default='sunroom', help="Thermostat location" )
    ap.add_argument( '--setpoint', type=float, default=21., help="Air temperature (C), in air mode" )
    ap.add_argument( '--outside', type=float, default=-20., help="Mean outdoor temperature (C)" )
    ap.add_argument( '--boiler', type=float, default=15000., help="Boiler capacity (BTU/h)" )
    ap.add_argument( '--hours', type=int, default=48 )
    ap.add_argument( '--step', type=float, default=60., help="Simulation time step (s)" )
    args                        = ap.parse_args( argv )

    world, spaces               = house( C_to_F( args.outside ))
    f                           = fanger( clo=1.0, met=1.2, hum=.4 )   # indoor winter clothes, sitting/standing
    on, burned, now, rows       = False, 0., 0., []
    print( "%5s %7s %7s | %s" % ( "hour", "outside", "zone", " | ".join(
        "%-7s air    MRT    PMV   PPD" % name for name in sorted( ROOMS ))))
    while now < args.hours * 3600:
        # Outdoors swings +/-5C around the mean, coldest at 6am
        world.conditions.temperature = C_to_F( args.outside - 5 * math.cos( 2 * math.pi * ( now / 3600 - 6 ) / 24 ))
        results                 = world.compute( now=now + args.step )

        # The thermostat: on/off with a little hysteresis, on air temperature or PMV
        t_a, t_r, pmv, ppd      = comfort( spaces[args.room], world, f )
        error                   = t_a - args.setpoint if args.mode == 'air' else pmv
        on                      = error < ( +.1 if on else -.1 )
        if on:
            results[('zone', 'boiler', 'supply')] = args.boiler * args.step / 3600
            burned             += args.boiler * args.step / 3600
        world.absorb( results )
        now                     = world.now

        if now % 3600 < args.step:
            row                 = [ now // 3600, F_to_C( world.conditions.temperature ),
                                    F_to_C( spaces['zone'].conditions.temperature ) ] \
                                  + [ comfort( spaces[name], world, f ) for name in sorted( ROOMS ) ]
            rows.append( row )
            print( "%5d %6.1fC %6.1fC | %s" % ( row[0], row[1], row[2], " | ".join(
                "%-7s %5.1fC %5.1fC %+5.2f %4.0f%%" % (( name, ) + c ) for name, c in zip( sorted( ROOMS ), row[3:] ))))
    print( "Boiler: %.0f BTU (%.1f kWh) over %d hours" % ( burned, burned / 3412.14, args.hours ))
    return rows, burned


if __name__ == "__main__":
    sys.exit( main() and 0 )
