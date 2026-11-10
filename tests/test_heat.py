"""Heat flow: dimensions, environments, portals and spaces."""

from __future__ import absolute_import, division, print_function

import pytest

from hydronic import (
    Error, C_to_F, F_to_C, ft, WI, LN, HI, daytime, dimension, resize, area, volume, merge,
    environment, portal, space,
)
from hydronic.misc import near, clamp, scale


def test_misc():
    assert near( 1.0, 1.00009 ) and not near( 1.0, 1.0002 )
    assert clamp( 5, ( 0, 3 )) == 3 and clamp( -1, ( 0, 3 )) == 0 and clamp( 2, ( 0, float( 'nan' ))) == 2
    assert scale( 5, ( 0, 10 ), ( 100, 0 )) == 50
    assert scale( 20, ( 0, 10 ), ( 0, 1 ), clamped=True ) == 1
    with pytest.raises( Error ):
        scale( 1, ( 2, 2 ), ( 0, 1 ))
    assert near( C_to_F( 20. ), 68. ) and near( F_to_C( -40. ), -40. )


def test_dimensions():
    for a, b, how, expect in [
            ( ( 10., 20., 8. ), ( 50., 20.,  8. ), LN,   ( 30.,     40.,  8.     )),
            ( ( 10., 20., 8. ), ( 50., 40.,  8. ), LN,   ( 36.666,  60.,  8.     )),
            ( ( 10., 20., 8. ), ( 50., 20., 12. ), WI,   ( 60.,     20., 11.333  )),
            ( ( 10., 20., 8. ), ( 50., 20., 12. ), None, ( 60.,     20., 11.333  )),  # automatically chosen
            ( ( 20., 10., 8. ), ( 20., 30.,  8. ), None, ( 20.,     40.,  8.     )),
    ]:
        c                       = merge( a, b, how )
        assert all( near( c[d], expect[d] ) for d in ( WI, LN, HI )), "%r != %r" % ( c, expect )
        assert near( area( c ), area( a ) + area( b ))
        assert near( volume( c ), volume( a ) + volume( b ))

    assert merge( None, ( 1, 2, 3 )) == ( 1, 2, 3 ) == merge( ( 1, 2, 3 ), None )
    with pytest.raises( Error ):
        merge( ( 1., 2., 3. ), ( 4., 5., 6. ), WI )

    assert dimension( ( ft(3,2), ft(9,6) ) ) == ' 3\' 2"x 9\' 6"'
    assert dimension( ( ft(0,80), ft(3,2), ft(9,10) ) ) == ' 6\' 8"x 3\' 2"x 9\'10"'
    assert resize( ( 0, 1, 2 ), h=5 ) == ( 0, 1, 5 )            # A zero dimension is retained
    assert daytime( 2 * 86400 + 3 * 3600 + 4 * 60 + 5.9 ) == "02d 03:04:05"


def test_environment():
    house                       = environment( 72., "air" )
    # 1000 BTUs into a 2000 ft^2 house with 8 ft ceilings ==> 290 BTU / 1F
    house.absorb( 1000., 5 * 20 * 20 * 8 )
    assert near( house.temperature, 75.45 )


def test_portal():
    # 100 F difference, 15 ft^2 window at R2 plus an R1 air film
    w1                          = portal( "Window 1 W", "outside", ( ft(0,30), ft(0,72) ), R=2., film=1.0 )
    outside                     = environment( C_to_F( -35 ))
    inside                      = environment( C_to_F( 20.555 ))

    assert near( w1.area(),  15.0 )
    assert near( w1.transfer( inside, outside, 60 * 60 ), -500.0 )
    assert near( w1.transfer( inside, outside,  1 * 60 ),   -8.333 )

    # The temperature of a surface with R value 2.0, plus an R-1.0 air film would be 2/3 of the
    # total temperature differential between the inside and outside temperatures.
    assert near( w1.temperature( inside, outside ), C_to_F( 20.555 - ( 20.555 - -35.0 ) * 1 / 3 ))

    # An R 6.8 portal (including an R.68 air film) with a 100F temperature drop would have an inside
    # surface temperature (the default) 10 degrees (10%) cooler than the inside air.
    world                       = environment( -30 )
    room                        = environment(  70 )
    window                      = portal( "world", "room", ( 4, 6 ), R=6.8-.68, film=.68 )
    assert near( window.temperature( inside=room, outside=world ), 60 )

    # And ensure the inverse is true (compute inside air from inside surface temperature)
    assert near( window.temperature( inside=60, outside=world, what=portal.INSIDE_AIR ),
                 room.temperature )

    # Integer temperatures and R values use true division, under Python 2 too
    assert near( portal( "p", "q", ( 1, 1 ), R=3, film=0 ).transfer( 0, 1, 3600 ), 1/3 )


def test_spaces():
    now                         = 1000.
    garage                      = space( "garage", ( ft(19,4), ft(39,4), ft(9,6) ), now=now )
    assert near( garage.conditions.temperature, 32. )           # Default initial conditions
    assert len( garage.current() ) == 1

    garage.connects( portal( "Car Door 1", "world", ( 9, 8 ), 3.-.68, film=.68 ))
    world                       = space( "world", ( 1000, 1000, 1000 ), environment( -40. ), now )
    world.contains( garage )

    assert [ s.name for s, depth in world.walk() ] == [ "world", "garage" ]
    assert near( world.now, 1000. )

    results                     = world.compute( now=world.now + 10. * 60 )
    assert len( results ) == 2
    assert near( world.now, 1000. + 10. * 60 )
    assert near( results[('garage','world','Car Door 1')], -288.0 )     # 288 BTUs lost over 10 minutes
    assert near( results[('world','garage','Car Door 1')], +288.0 )
    assert near( garage.conditions.temperature, 32.000 )                # Deltas not yet applied...

    world.absorb( results )
    assert near( garage.conditions.temperature, 29.800 )                # Dropped to just below freezing
    assert near( world.conditions.temperature, -40.000 )

    # OK, run again for another 10 minutes; slightly less BTUs lost this time
    results                     = world.compute( now=world.now + 10. * 60 )
    assert near( results[('garage','world','Car Door 1')], -279.2 )
    world.absorb( results )
    assert near( garage.conditions.temperature, 27.667 )

    # Now, add a hydronic slab beneath garage.  4" slab, R2/inch
    slab                        = space( "zone 1", resize( garage.size, h=ft(0,4) ),
                                         environment( what="concrete" ), now=world.now )
    assert near( garage.volume(), 7224.2 )
    assert near( slab.volume(), 253.5 )
    garage.contains( slab )
    floor                       = portal( "Floor", "zone 1", garage.size, R=0.0, film=.68 )
    garage.connects( floor )

    # The Floor portal has a core R value of 0, but a non-zero film R value (.68).  Therefore, the
    # inside (garage-side) radiant "temperature" is the same as the outside (slab-side)
    # temperature, but there is a non-zero insulation value that slows heat transfer.
    assert floor.temperature( inside=garage.conditions, outside=slab.conditions ) == 32.0000

    world.absorb( { ('zone 1','somewhere','via something'): 1000. } )
    assert near( slab.conditions.temperature,   32.1315 )
    world.absorb( world.compute( now=world.now + 1. * 60 ))
    assert near( garage.conditions.temperature, 28.096 )
    assert near( slab.conditions.temperature,   32.121 )

    # How long 'til the garage and slab reach within 2 degrees
    while slab.conditions.temperature - garage.conditions.temperature > 2:
        world.absorb( world.compute( now=world.now + 1. * 60 ))
    assert near( world.now - world.start, 1920. )
    assert near( garage.conditions.temperature, 30.120 )

    # Garage's mean radiant temperature: the Car Door and (radiant) Floor surfaces, by area
    door_t                      = garage.portals[0].temperature( garage.conditions, world.conditions )
    floor_t                     = slab.conditions.temperature
    expect                      = ( 72 * door_t + area( garage.size ) * floor_t ) / ( 72 + area( garage.size ))
    assert near( garage.radiant( world ), expect )
    assert sorted( p.name for p, t in garage.surfaces( world )) == [ "Car Door 1", "Floor" ]
    # The slab's only surface is the garage's Floor portal onto it, seen from the slab side
    assert near( slab.radiant( world ),
                 floor.temperature( inside=slab.conditions, outside=garage.conditions ))
    # The world is bounded (from outside) by the Car Door; a space with no portals radiates at its air temperature
    assert near( world.radiant( world ), garage.portals[0].temperature( world.conditions, garage.conditions ))
    lonely                      = space( "lonely", ( 1, 1, 1 ), environment( 70. ), now=0 )
    assert lonely.radiant( lonely ) == 70.

    lonely.connects( portal( "x", "nowhere", ( 1, 1 ), 1 ))
    with pytest.raises( Error ):
        lonely.compute( now=1 )
