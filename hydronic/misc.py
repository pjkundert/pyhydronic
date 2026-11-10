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

"""Small numeric helpers; formerly imported from ownercredit.misc, now dependency-free."""

from __future__ import absolute_import, division, print_function


class Error( ValueError ):
    """Invalid input, or a computation that failed to converge."""


def near( a, b, significance=1.0e-4 ):
    """True iff a and b differ by no more than the factor 'significance' of the larger magnitude.
    Default is to within 4 decimal places."""
    return abs( a - b ) <= significance * max( abs( a ), abs( b ))


def clamp( val, lim ):
    """Limit val to the (min, max) 'lim'.  A NaN limit is ignored, since no value is < or > NaN."""
    if val < lim[0]:
        return lim[0]
    if val > lim[1]:
        return lim[1]
    return val


def scale( val, dom, rng, clamped=False ):
    """Map 'val' linearly from domain 'dom' to range 'rng', optionally clamped to 'rng'.  Either may be
    in increasing or decreasing order, but neither may be zero-sized."""
    if dom[1] == dom[0]:
        raise Error( "Scaling %r requires a non-zero domain: %r" % ( val, dom ))
    result                      = rng[0] + ( val - dom[0] ) * ( rng[1] - rng[0] ) / ( dom[1] - dom[0] )
    if clamped:
        result                  = clamp( result, ( min( rng ), max( rng )))
    return result
