#
# Hydronic -- calculations for modeling heated structures
#
# Copyright (c) 2006-2026, Perry Kundert
#
# Hydronic is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.  See the LICENSE file at the top of the source tree.
#
# Hydronic is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU General Public License for more details.
#

"""Rudimentary heat flow between interconnected spaces.

A structure is a tree of 'space's (each with an 'environment' of some substance at some
temperature), connected by 'portal's (walls, windows, floors, ...) with an area and R value.  Each
time step, 'compute' the BTUs flowing through every portal, then 'absorb' them to update each
space's temperature.

All units are US/Imperial, as used in the R values of North American building materials:
temperatures in degrees F, dimensions in ft, heat in BTU, R in F.ft^2.h/BTU.

"""

from __future__ import absolute_import, division, print_function

import copy
import time

from .misc import Error, near, scale


# Conversion constants
ft_per_m                        = 3.2808399
F_per_C                         = ( 212. - 32. ) / 100.


def C_to_F( C ):
    return scale( C, (  0., 100. ), ( 32., 212. ))


def F_to_C( F ):
    return scale( F, ( 32., 212. ), (  0., 100. ))


def ft( f=0, i=0 ):
    """Convert feet and inches to fractional feet"""
    return f + i / 12.


def daytime( t ):
    """Convert a time span in seconds, into: ##d hh:mm:ss"""
    t                           = int( t )
    return "%02dd %02d:%02d:%02d" % (
          t // 3600 // 24,
        ( t // 3600 ) % 24,
        ( t % 3600 ) // 60,
          t %   60 )


def dimension( s ):
    """Convert a (x,y) or (x,y,z) dimension into ft'in"x..."""
    return 'x'.join( "%2d'%2d\"" % ( i // 12, i % 12 )
                     for i in ( int( round( f * 12 + .0001 )) for f in s ))


# Spatial dimension indices
WI                              = 0
LN                              = 1
HI                              = 2


def resize( size, w=None, l=None, h=None ):
    """Return a copy of (w,l,h) 'size', with any of w, l or h replaced"""
    return ( size[WI] if w is None else w,
             size[LN] if l is None else l,
             size[HI] if h is None else h )


def area( s ):
    return s[WI] * s[LN]


def volume( s ):
    return s[WI] * s[LN] * s[HI]


def merge( a, b, how=None ):
    """Merges two spaces in the 'how' dimension.  At least 1 of the other 2 must be identical.  If not
    specified, chooses the first non-equal dimension to merge.  If either is None, the other is
    returned.  The remaining dimension is averaged, weighted to conserve total area and volume.

    """
    if a is None or b is None:
        return b if a is None else a

    if how is None:
        for how in ( WI, LN, HI ):
            if not near( a[how], b[how] ):
                break

    ok                          = False
    r                           = list( a )
    r[how]                      = a[how] + b[how]
    for dim in ( ( how + 1 ) % 3, ( how + 2 ) % 3 ):
        if near( a[dim], b[dim] ):
            ok                  = True
        else:
            r[dim]              = ( a[dim] * a[how] + b[dim] * b[how] ) / ( a[how] + b[how] )
    if not ok:
        raise Error( "No common dimension found merging %r and %r" % ( a, b ))
    return tuple( r )


# BTU required to raise 1 ft^3 of different compounds by 1 degree F
# Estimates are from Siegenthaler, Modern Hydronic Heating ..., pg 255.
BTU_ft3_F                       = {}
BTU_ft3_F['air']                =   290. / ( 2000 * 8 )
BTU_ft3_F['concrete']           = 20000. / ( 2000 * 4 / 12. )

# Wild guess
BTU_ft3_F['tile']               = 15000. / ( 2000 * 4 / 12. )   # ?
BTU_ft3_F['soil']               = 10000. / ( 2000 * 4 / 12. )   # ?
BTU_ft3_F['wood']               =  5000. / ( 2000 * 4 / 12. )   # ?

# 1 BTU raises 1 pound of water by 1F degree.
# 1 ft^3 is 7.4805 US gallons, and 1 US gallon is 8.3403 pounds
#BTU_ft3_F['water']             = 1. * 7.4805 * 8.3403
# 1 ft^3 is 6.2288 Imp. gallons, which is 10 pounds (by definition)
BTU_ft3_F['water']              = 1. * 6.2288 * 10.


def _temperature( e ):
    """The temperature of an environment, or of a raw number"""
    return e.temperature if isinstance( e, environment ) else float( e )


class environment( object ):
    """A description of an environment, composed of some substance with a certain thermal inertia.
    Has a temperature and a composition of substance '.what', and hence a thermal inertia, but no
    inherent volume.  An optional 'sensor' may be attached by the application (eg. to replace the
    modeled temperature with a measured one); it is not used here.

    """
    def __init__( self, temp=C_to_F( 0. ), what="air", sensor=None ):
        self.temperature        = temp                          # degrees F
        self.what               = what
        self.inertia            = BTU_ft3_F[what]               # Thermal inertia per ft^3
        self.sensor             = sensor

    def __str__( self ):
        return "%-10.10s %6.2fC" % ( self.what, F_to_C( self.temperature ))

    def absorb( self, BTU, volume ):
        """Compute temperature change.  The total BTU's absorbed, spread over the volume's thermal
        mass."""
        self.temperature       += BTU / ( self.inertia * volume )


class portal( object ):
    """Defines a connection between spaces, with an area and R value; assumes that the "inside" has
    a stationary air film of (default) R0.68.  Computes heat transfer to the adjoining space.  Also
    estimates surface temperature.

    EXAMPLES
        # A 3'x5' R3 window
        portal( "Window 1 W", "world", ( 3., 5. ), 3. )

    Assumes an air film of R.68 (default) on the inside, for purposes of estimating the surface
    temperature.  For a purely radiant surface (where inside radiant temperature equals outside
    temperature), use an R value of 0.0, and supply only a non-zero value for film.

    """
    def __init__( self, name, onto, size, R, film=0.68 ):
        self.name               = name
        self.onto               = onto                          # The name of the space connected to
        self.size               = size                          # (x,y[,z]) in ft (optional z ignored)
        self.R_film             = film
        self.R_core             = R

    @property
    def R( self ):
        return self.R_core + self.R_film

    def __str__( self ):
        return "%12.12s (%7.2fft^2) R%3d %s" % (
            dimension( self.size ), self.area(), self.R, self.name )

    def area( self ):
        return self.size[0] * self.size[1]

    def transfer( self, inside, outside, dt ):
        """Computes the BTU heat transfer from environment 'inside' to 'outside' for period 'dt'
        seconds.  Each may be an environment, or a raw temperature (F).  Heat lost from inside is -'ve.

               A
        Q  =  --- x (delta-T)
               R

        Q       = BTU/h rate of heat transfer
        A       = area (ft^2)
        R       = R value (degrees-F x ft^2 * hr./BTU)
        delta-T = temperature surface differential
        """
        BTUh                    = ( _temperature( outside ) - _temperature( inside )) * self.area() / self.R
        return BTUh * dt / 60 / 60                              # BTUh is in hours

    INSIDE_SURFACE              = 1
    INSIDE_AIR                  = 2

    def temperature( self, inside, outside, what=INSIDE_SURFACE ):
        """Compute approximate interior surface temperature, given the total R value of the portal, and
        the R value of the inside surface air film(s), and the inside and outside air temperatures.

        The temperature drop across the wall section is proportional to the R value of each section.
        Therefore, if the total R value (including interior air film) is (say) R6.8, then an air
        film of R.68 would represent 10% of the temperature drop.  If the interior air temperature
        is 70F and exterior is -30F, then the wall will be 10F cooler than the interior temperature.

        See www.irtalk.com/forums/storage/9/2105/Effective%20R-value%201.pdf

        It is invalid to define a portal with a total R value equal to zero, but we'll default to
        the outside temperature if so.

        """
        ti                      = _temperature( inside )
        to                      = _temperature( outside )
        if self.R > 0:
            if what == self.INSIDE_SURFACE:
                # Computing the inside surface temperature, given the inside and outside air (and
                # surface) temperatures; remove the fraction of the temperature gradient through the
                # insulation that is the result of the air film.
                return ti - ( ti - to ) * self.R_film / ( self.R_core + self.R_film )
            elif what == self.INSIDE_AIR:
                # Computing the inside air temperature, given the inside surface temperature and
                # outside air (and surface) temperatures.
                return ti + ( ti - to ) / self.R_core * self.R_film
        return to


class space( object ):
    """Implements an environmental space with an inside and an outside.  Computes energy flow between
    the space and whatever portal(s) to other spaces are provided.

    In general the space will be connected to the "outside" of one or more other spaces.  For
    example, the root 'space' might typically represent the outside walls of a structure.  Its
    'loop' method would be passed the outside temperature, and would compute the gains/losses to
    the walls and roof of the house.

    A house would be composed of 1 or more rooms, which would typically be interconnected with
    each-other (sharing walls, doors, etc.).

    Each computation of heat flow to/from the space and its sub-spaces specifies a time base 'now'
    and period 'dt' for the computation, and passes a description of the weather 'outside' during
    that period.

    The sub-space then computes its own gains/losses to/from its sub-spaces for the time period
    (using its current initial conditions), and then computes its own gains/losses during the
    period to the (provided) 'outside'.  It calculates its (net) ending condition (for use in the
    next loop as the next initial condition), and returns the gains/losses to the caller.

    """
    def __init__( self, name, size, initial=None, now=None ):
        self.name               = name                          # Unique amongst spaces!
        self.size               = size                          # (x,y,z) in ft
        self.conditions         = environment() if initial is None else copy.copy( initial )
        self.now                = time.time() if now is None else now
        self.start              = self.now
        self.subspaces          = []
        self.portals            = []

    def __str__( self ):
        return "%-16.16s (%7.2fft^2) %20.20s %s" % (
            self.name, self.area(), dimension( self.size ), str( self.conditions ))

    def contains( self, something ):
        self.subspaces.append( something )

    def connects( self, onto ):
        self.portals.append( onto )

    def walk( self, depth=0 ):
        """A recursive generator that yields (space,depth) for the space and all subspaces in order"""
        yield self, depth
        for subs in self.subspaces:
            for s, d in subs.walk( depth=depth + 1 ):
                yield s, d

    def area( self ):
        return area( self.size )

    def volume( self ):
        return volume( self.size )

    def current( self, cond=None ):
        """Copy current conditions of this space (and all subspaces) into the supplied dictionary"""
        if cond is None:
            cond                = {}
        for subs in self.subspaces:
            subs.current( cond )
        cond[self.name]         = copy.copy( self.conditions )
        return cond

    def compute( self, initial=None, results=None, now=None ):
        """Takes a map of 1 or more current environment conditions, and computes a map of BTU gain/loss
        deltas from/onto each of the spaces, via each port, since our last 'now'.  The 'results' in
        +/- BTUs are keyed (space,other,portal).

        A gain/loss computed from one space onto another is also included as an inverse loss/gain
        from the other space onto the corresponding space.

        After 'compute' is finished, the 'absorb' method should be invoked with the 'results'
        dictionary.

        """
        if initial is None:
            initial             = self.current()
        if results is None:
            results             = {}
        if now is None:
            now                 = time.time()
        dt                      = now - self.now

        # Compute all subspaces, too, using same timestamp, and collect their results
        for sub in self.subspaces:
            sub.compute( initial, results, now )

        # Compute our net BTU gain/loss for period 'dt', adding the gain/loss to our results, and
        # adding the inverse to the other space's results.
        for port in self.portals:
            if port.onto not in initial:
                raise Error( "%s: Couldn't find conditions for %s, via %s" % (
                    self.name, port.onto, port.name ))
            BTU                 = port.transfer( self.conditions, initial[port.onto], dt )
            here                = ( self.name, port.onto, port.name )
            there               = ( port.onto, self.name, port.name )
            results[here]       = results.get( here, 0. ) + BTU
            results[there]      = results.get( there, 0. ) - BTU

        self.now                = now
        return results

    def absorb( self, results ):
        """Calculate the change in temperature due to the given deltas, and let all subspaces do the
        same.  Since the results is keyed by a tuple of names: (space,other,portal), we must traverse
        and pick out all that apply to this space.

        """
        for ( s, o, p ), btu in results.items():
            if s == self.name:
                self.conditions.absorb( btu, self.volume() )
        for subs in self.subspaces:
            subs.absorb( results )

    def surfaces( self, root ):
        """Yields (portal, temperature) for every surface bounding this space: its own portals, and any
        other space's portals onto it (found by walking 'root', eg. the 'world').  The temperature
        (F) is that of the surface, as seen from inside this space.

        """
        spaces                  = dict( ( s.name, s ) for s, _ in root.walk() )
        for p in self.portals:
            yield p, p.temperature( self.conditions, spaces[p.onto].conditions )
        for s in spaces.values():
            if s is not self:
                for p in s.portals:
                    if p.onto == self.name:
                        yield p, p.temperature( self.conditions, s.conditions )

    def radiant( self, root ):
        """Mean radiant temperature (F) of this space: the area-weighted mean temperature of all its
        surfaces.  This is the usual approximation to the view-factor weighted mean seen by an
        occupant, and is Fanger's t_r (once converted to C).  Defaults to the air temperature.

        """
        total = weighted        = 0.
        for p, t in self.surfaces( root ):
            total              += p.area()
            weighted           += p.area() * t
        return weighted / total if total else self.conditions.temperature
