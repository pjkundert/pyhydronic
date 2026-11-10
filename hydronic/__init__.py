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

"""Hydronic: rudimentary heat flow through structures, and Fanger's thermal comfort equation.

    hydronic.heat       space, portal, environment: heat flow (US units: F, ft, BTU)
    hydronic.comfort    fanger: PMV / PPD thermal comfort (SI units: C, m/s, Pa)
"""

from __future__ import absolute_import, division, print_function

from .version import __version__, __version_info__              # noqa: F401
from .misc import Error                                         # noqa: F401
from .heat import (                                             # noqa: F401
    F_per_C, ft_per_m, C_to_F, F_to_C, ft,
    WI, LN, HI,
    daytime, dimension, resize, area, volume, merge,
    BTU_ft3_F,
    environment, portal, space,
)
from .comfort import fanger                                     # noqa: F401

__author__                      = "Perry Kundert"
__email__                       = "perry@dominionrnd.com"
__copyright__                   = "Copyright (c) 2006-2026 Perry Kundert"
__license__                     = "Dual License: GPLv3 (or later) and Commercial (see LICENSE)"

__all__                         = (
    'Error',                                                      # Exceptions
    'F_per_C', 'ft_per_m', 'C_to_F', 'F_to_C', 'ft',              # conversion
    'WI', 'LN', 'HI',                                             # spatial dimensions
    'daytime', 'dimension', 'resize', 'area', 'volume', 'merge',  # converter functions
    'BTU_ft3_F',                                                  # Materials
    'environment', 'portal', 'space', 'fanger' )                  # Classes
