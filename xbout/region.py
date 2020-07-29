from collections import OrderedDict

import numpy as np
import xarray as xr

from .utils import _set_attrs_on_all_vars


class Region:
    """
    Contains the global indices bounding a single topological region, i.e. a region with
    logically rectangular contiguous data.

    Also stores the names of any neighbouring regions.
    """
    def __init__(self, *, name, ds=None, xinner_ind=None, xouter_ind=None,
                 ylower_ind=None, yupper_ind=None, connection_inner_x=None,
                 connection_outer_x=None, connection_lower_y=None,
                 connection_upper_y=None):
        """
        Parameters
        ----------
        name : str
            Name of the region
        ds : BoutDataset, optional
            Dataset to get variables to calculate coordinates from
        xinner_ind : int, optional
            Global x-index of the inner points of this region
        xouter_ind : int, optional
            Global x-index of the points just beyond the outer edge of this region
        ylower_ind : int, optional
            Global y-index of the lower points of this region
        yupper_ind : int, optional
            Global y-index of the points just beyond the upper edge of this region
        connection_inner_x : str, optional
            The region inside this one in the x-direction
        connection_outer_x : str, optional
            The region outside this one in the x-direction
        connection_lower_y : str, optional
            The region below this one in the y-direction
        connection_upper_y : str, optional
            The region above this one in the y-direction
        """
        self.name = name
        self.xinner_ind = xinner_ind
        self.xouter_ind = xouter_ind
        if xouter_ind is not None and xinner_ind is not None:
            self.nx = xouter_ind - xinner_ind
        self.ylower_ind = ylower_ind
        self.yupper_ind = yupper_ind
        if yupper_ind is not None and ylower_ind is not None:
            self.ny = yupper_ind - ylower_ind
        self.connection_inner_x = connection_inner_x
        self.connection_outer_x = connection_outer_x
        self.connection_lower_y = connection_lower_y
        self.connection_upper_y = connection_upper_y

        if ds is not None:
            # calculate start and end coordinates
            #####################################
            self.xcoord = ds.metadata['bout_xdim']
            self.ycoord = ds.metadata['bout_ydim']

            # dx is constant in any particular region in the y-direction, so convert to a
            # 1d array
            dx = ds['dx'].isel(**{self.ycoord: self.ylower_ind})
            dx_cumsum = dx.cumsum()
            self.xinner = dx_cumsum[xinner_ind] - dx[xinner_ind]/2.
            self.xouter = dx_cumsum[xouter_ind - 1] + dx[xouter_ind - 1]/2.

            # dy is constant in the x-direction, so convert to a 1d array
            dy = ds['dy'].isel(**{self.xcoord: self.xinner_ind})
            dy_cumsum = dy.cumsum()
            self.ylower = dy_cumsum[ylower_ind] - dy[ylower_ind]/2.
            self.yupper = dy_cumsum[yupper_ind - 1] + dy[yupper_ind - 1]/2.

    def __repr__(self):
        result = "<xbout.region.Region>\n"
        for attr, val in vars(self).items():
            result += f"\t{attr}\t{val}\n"
        return result

    def get_slices(self, mxg=0, myg=0):
        """
        Return x- and y-dimension slices that select this region from the global
        DataArray.

        Returns
        -------
        xslice, yslice : slice, slice
        """
        xi = self.xinner_ind
        if self.connection_inner_x is not None:
            xi -= mxg

        xo = self.xouter_ind
        if self.connection_outer_x is not None:
            xi += mxg

        yl = self.ylower_ind
        if self.connection_lower_y is not None:
            yl -= myg

        yu = self.yupper_ind
        if self.connection_upper_y is not None:
            yu += myg

        return {self.xcoord: slice(xi, xo), self.ycoord: slice(yl, yu)}

    def get_inner_guards_slices(self, *, mxg, myg=0):
        """
        Return x- and y-dimension slices that select mxg guard cells on the inner-x side
        of this region from the global DataArray.

        Parameters
        ----------
        mxg : int
            Number of guard cells
        myg : int, optional
            Number of y-guard cells to include at the corners
        """
        ylower = self.ylower_ind
        if self.connection_lower_y is not None:
            ylower -= myg
        yupper = self.yupper_ind
        if self.connection_upper_y is not None:
            yupper += myg
        return {self.xcoord: slice(self.xinner_ind - mxg, self.xinner_ind),
                self.ycoord: slice(ylower, yupper)}

    def get_outer_guards_slices(self, *, mxg, myg=0):
        """
        Return x- and y-dimension slices that select mxg guard cells on the outer-x side
        of this region from the global DataArray.

        Parameters
        ----------
        mxg : int
            Number of guard cells
        myg : int, optional
            Number of y-guard cells to include at the corners
        """
        ylower = self.ylower_ind
        if self.connection_lower_y is not None:
            ylower -= myg
        yupper = self.yupper_ind
        if self.connection_upper_y is not None:
            yupper += myg
        return {self.xcoord: slice(self.xouter_ind, self.xouter_ind + mxg),
                self.ycoord: slice(ylower, yupper)}

    def get_lower_guards_slices(self, *, myg, mxg=0):
        """
        Return x- and y-dimension slices that select myg guard cells on the lower-y side
        of this region from the global DataArray.

        Parameters
        ----------
        myg : int
            Number of guard cells
        mxg : int, optional
            Number of x-guard cells to include at the corners
        """
        xinner = self.xinner_ind
        if self.connection_inner_x is not None:
            xinner -= mxg
        xouter = self.xouter_ind
        if self.connection_outer_x is not None:
            xouter += mxg
        return {self.xcoord: slice(xinner, xouter),
                self.ycoord: slice(self.ylower_ind - myg, self.ylower_ind)}

    def get_upper_guards_slices(self, *, myg, mxg=0):
        """
        Return x- and y-dimension slices that select myg guard cells on the upper-y side
        of this region from the global DataArray.

        Parameters
        ----------
        myg : int
            Number of guard cells
        mxg : int, optional
            Number of x-guard cells to include at the corners
        """
        xinner = self.xinner_ind
        if self.connection_inner_x is not None:
            xinner -= mxg
        xouter = self.xouter_ind
        if self.connection_outer_x is not None:
            xouter += mxg
        return {self.xcoord: slice(xinner, xouter),
                self.ycoord: slice(self.yupper_ind, self.yupper_ind + myg)}

    def __eq__(self, other):
        if not isinstance(other, Region):
            return NotImplemented
        return vars(self) == vars(other)


def _in_range(val, lower, upper):
    if val < lower:
        return lower
    elif val > upper:
        return upper
    else:
        return val


def _order_vars(lower, upper):
    if upper < lower:
        return upper, lower
    else:
        return lower, upper


def _get_topology(ds):
    jys11 = ds.metadata['jyseps1_1']
    jys21 = ds.metadata['jyseps2_1']
    nyinner = ds.metadata['ny_inner']
    jys12 = ds.metadata['jyseps1_2']
    jys22 = ds.metadata['jyseps2_2']
    ny = ds.metadata['ny']
    ixs1 = ds.metadata['ixseps1']
    ixs2 = ds.metadata['ixseps2']
    nx = ds.metadata['nx']
    if jys21 == jys12:
        # No upper X-point
        if jys11 <= 0 and jys22 >= ny - 1:
            ix = min(ixs1, ixs2)
            if ix >= nx - 1:
                return 'core'
            elif ix <= 0:
                return 'sol'
            else:
                return 'limiter'

        return 'single-null'

    if jys11 == jys21 and jys12 == jys22:
        if jys11 < nyinner - 1 and jys22 > nyinner:
            return 'xpoint'
        else:
            raise ValueError('Currently unsupported topology')

    if ixs1 == ixs2:
        if jys21 < nyinner - 1 and jys12 > nyinner:
            return 'connected-double-null'
        else:
            raise ValueError('Currently unsupported topology')

    return 'disconnected-double-null'


def _create_connection_x(regions, inner, outer):
    regions[inner].connection_outer_x = outer
    regions[outer].connection_inner_x = inner


def _create_connection_y(regions, lower, upper):
    regions[lower].connection_upper_y = upper
    regions[upper].connection_lower_y = lower


def _create_regions_toroidal(ds):
    topology = _get_topology(ds)

    coordinates = {'t': ds.metadata.get('bout_tdim', None),
                   'x': ds.metadata.get('bout_xdim', None),
                   'y': ds.metadata.get('bout_ydim', None),
                   'z': ds.metadata.get('bout_zdim', None)}

    ixs1 = ds.metadata['ixseps1']
    ixs2 = ds.metadata['ixseps2']
    nx = ds.metadata['nx']

    jys11 = ds.metadata['jyseps1_1']
    jys21 = ds.metadata['jyseps2_1']
    nyinner = ds.metadata['ny_inner']
    jys12 = ds.metadata['jyseps1_2']
    jys22 = ds.metadata['jyseps2_2']
    ny = ds.metadata['ny']

    mxg = ds.metadata['MXG']
    myg = ds.metadata['MYG']
    # keep_yboundaries is 1 if there are y-boundaries and 0 if there are not
    ybndry = ds.metadata['keep_yboundaries']*myg
    if jys21 == jys12:
        # No upper targets
        ybndry_upper = 0
    else:
        ybndry_upper = ybndry

    # Make sure all sizes are sensible
    ixs1 = _in_range(ixs1, 0, nx)
    ixs2 = _in_range(ixs2, 0, nx)
    ixs1, ixs2 = _order_vars(ixs1, ixs2)
    jys11 = _in_range(jys11, 0, ny - 1)
    jys21 = _in_range(jys21, 0, ny - 1)
    jys12 = _in_range(jys12, 0, ny - 1)
    jys21, jys12 = _order_vars(jys21, jys12)
    nyinner = _in_range(nyinner, jys21 + 1, jys12 + 1)
    jys22 = _in_range(jys22, 0, ny - 1)

    # Adjust for boundary cells
    # keep_xboundaries is 1 if there are x-boundaries and 0 if there are not
    if not ds.metadata['keep_xboundaries']:
        ixs1 -= mxg
        ixs2 -= mxg
        nx -= 2*mxg
    jys11 += ybndry
    jys21 += ybndry
    nyinner += ybndry + ybndry_upper
    jys12 += ybndry + 2*ybndry_upper
    jys22 += ybndry + 2*ybndry_upper
    ny += 2*ybndry + 2*ybndry_upper

    # Note, include guard cells in the created regions, fill them later
    regions = OrderedDict()
    if topology == 'disconnected-double-null':
        regions['lower_inner_PFR'] = Region(
                name='lower_inner_PFR', ds=ds, xinner_ind=0, xouter_ind=ixs1,
                ylower_ind=0, yupper_ind=jys11 + 1)
        regions['lower_inner_intersep'] = Region(
                name='lower_inner_intersep', ds=ds, xinner_ind=ixs1, xouter_ind=ixs2,
                ylower_ind=0, yupper_ind=jys11 + 1)
        regions['lower_inner_SOL'] = Region(
                name='lower_inner_SOL', ds=ds, xinner_ind=ixs2, xouter_ind=nx,
                ylower_ind=0, yupper_ind=jys11 + 1)
        regions['inner_core'] = Region(
                name='inner_core', ds=ds, xinner_ind=0, xouter_ind=ixs1,
                ylower_ind=jys11 + 1, yupper_ind=jys21 + 1)
        regions['inner_intersep'] = Region(
                name='inner_intersep', ds=ds, xinner_ind=ixs1, xouter_ind=ixs2,
                ylower_ind=jys11 + 1, yupper_ind=jys21 + 1)
        regions['inner_SOL'] = Region(
                name='inner_SOL', ds=ds, xinner_ind=ixs2, xouter_ind=nx,
                ylower_ind=jys11 + 1, yupper_ind=jys21 + 1)
        regions['upper_inner_PFR'] = Region(
                name='upper_inner_PFR', ds=ds, xinner_ind=0, xouter_ind=ixs1,
                ylower_ind=jys21 + 1, yupper_ind=nyinner)
        regions['upper_inner_intersep'] = Region(
                name='upper_inner_intersep', ds=ds, xinner_ind=ixs1, xouter_ind=ixs2,
                ylower_ind=jys21 + 1, yupper_ind=nyinner)
        regions['upper_inner_SOL'] = Region(
                name='upper_inner_SOL', ds=ds, xinner_ind=ixs2, xouter_ind=nx,
                ylower_ind=jys21 + 1, yupper_ind=nyinner)
        regions['upper_outer_PFR'] = Region(
                name='upper_outer_PFR', ds=ds, xinner_ind=0, xouter_ind=ixs1,
                ylower_ind=nyinner, yupper_ind=jys12 + 1)
        regions['upper_outer_intersep'] = Region(
                name='upper_outer_intersep', ds=ds, xinner_ind=ixs1, xouter_ind=ixs2,
                ylower_ind=nyinner, yupper_ind=jys12 + 1)
        regions['upper_outer_SOL'] = Region(
                name='upper_outer_SOL', ds=ds, xinner_ind=ixs2, xouter_ind=nx,
                ylower_ind=nyinner, yupper_ind=jys12 + 1)
        regions['outer_core'] = Region(
                name='outer_core', ds=ds, xinner_ind=0, xouter_ind=ixs1,
                ylower_ind=jys12 + 1, yupper_ind=jys22 + 1)
        regions['outer_intersep'] = Region(
                name='outer_intersep', ds=ds, xinner_ind=ixs1, xouter_ind=ixs2,
                ylower_ind=jys12 + 1, yupper_ind=jys22 + 1)
        regions['outer_SOL'] = Region(
                name='outer_SOL', ds=ds, xinner_ind=ixs2, xouter_ind=nx,
                ylower_ind=jys12 + 1, yupper_ind=jys22 + 1)
        regions['lower_outer_PFR'] = Region(
                name='lower_outer_PFR', ds=ds, xinner_ind=0, xouter_ind=ixs1,
                ylower_ind=jys22 + 1, yupper_ind=ny)
        regions['lower_outer_intersep'] = Region(
                name='lower_outer_intersep', ds=ds, xinner_ind=ixs1, xouter_ind=ixs2,
                ylower_ind=jys22 + 1, yupper_ind=ny)
        regions['lower_outer_SOL'] = Region(
                name='lower_outer_SOL', ds=ds, xinner_ind=ixs2, xouter_ind=nx,
                ylower_ind=jys22 + 1, yupper_ind=ny)
        _create_connection_x(regions, 'lower_inner_PFR', 'lower_inner_intersep')
        _create_connection_x(regions, 'lower_inner_intersep', 'lower_inner_SOL')
        _create_connection_x(regions, 'inner_core', 'inner_intersep')
        _create_connection_x(regions, 'inner_intersep', 'inner_SOL')
        _create_connection_x(regions, 'upper_inner_PFR', 'upper_inner_intersep')
        _create_connection_x(regions, 'upper_inner_intersep', 'upper_inner_SOL')
        _create_connection_x(regions, 'upper_outer_PFR', 'upper_outer_intersep')
        _create_connection_x(regions, 'upper_outer_intersep', 'upper_outer_SOL')
        _create_connection_x(regions, 'outer_core', 'outer_intersep')
        _create_connection_x(regions, 'outer_intersep', 'outer_SOL')
        _create_connection_x(regions, 'lower_outer_PFR', 'lower_outer_intersep')
        _create_connection_x(regions, 'lower_outer_intersep', 'lower_outer_SOL')
        _create_connection_y(regions, 'lower_inner_PFR', 'lower_outer_PFR')
        _create_connection_y(regions, 'lower_inner_intersep', 'inner_intersep')
        _create_connection_y(regions, 'lower_inner_SOL', 'inner_SOL')
        _create_connection_y(regions, 'inner_core', 'outer_core')
        _create_connection_y(regions, 'outer_core', 'inner_core')
        _create_connection_y(regions, 'inner_intersep', 'outer_intersep')
        _create_connection_y(regions, 'inner_SOL', 'upper_inner_SOL')
        _create_connection_y(regions, 'upper_outer_intersep', 'upper_inner_intersep')
        _create_connection_y(regions, 'upper_outer_PFR', 'upper_inner_PFR')
        _create_connection_y(regions, 'upper_outer_SOL', 'outer_SOL')
        _create_connection_y(regions, 'outer_intersep', 'lower_outer_intersep')
        _create_connection_y(regions, 'outer_SOL', 'lower_outer_SOL')
    elif topology == 'connected-double-null':
        regions['lower_inner_PFR'] = Region(
                name='lower_inner_PFR', ds=ds, xinner_ind=0, xouter_ind=ixs1,
                ylower_ind=0, yupper_ind=jys11 + 1)
        regions['lower_inner_SOL'] = Region(
                name='lower_inner_SOL', ds=ds, xinner_ind=ixs2, xouter_ind=nx,
                ylower_ind=0, yupper_ind=jys11 + 1)
        regions['inner_core'] = Region(
                name='inner_core', ds=ds, xinner_ind=0, xouter_ind=ixs1,
                ylower_ind=jys11 + 1, yupper_ind=jys21 + 1)
        regions['inner_SOL'] = Region(
                name='inner_SOL', ds=ds, xinner_ind=ixs2, xouter_ind=nx,
                ylower_ind=jys11 + 1, yupper_ind=jys21 + 1)
        regions['upper_inner_PFR'] = Region(
                name='upper_inner_PFR', ds=ds, xinner_ind=0, xouter_ind=ixs1,
                ylower_ind=jys21 + 1, yupper_ind=nyinner)
        regions['upper_inner_SOL'] = Region(
                name='upper_inner_SOL', ds=ds, xinner_ind=ixs2, xouter_ind=nx,
                ylower_ind=jys21 + 1, yupper_ind=nyinner)
        regions['upper_outer_PFR'] = Region(
                name='upper_outer_PFR', ds=ds, xinner_ind=0, xouter_ind=ixs1,
                ylower_ind=nyinner, yupper_ind=jys12 + 1)
        regions['upper_outer_SOL'] = Region(
                name='upper_outer_SOL', ds=ds, xinner_ind=ixs2, xouter_ind=nx,
                ylower_ind=nyinner, yupper_ind=jys12 + 1)
        regions['outer_core'] = Region(
                name='outer_core', ds=ds, xinner_ind=0, xouter_ind=ixs1,
                ylower_ind=jys12 + 1, yupper_ind=jys22 + 1)
        regions['outer_SOL'] = Region(
                name='outer_SOL', ds=ds, xinner_ind=ixs2, xouter_ind=nx,
                ylower_ind=jys12 + 1, yupper_ind=jys22 + 1)
        regions['lower_outer_PFR'] = Region(
                name='lower_outer_PFR', ds=ds, xinner_ind=0, xouter_ind=ixs1,
                ylower_ind=jys22 + 1, yupper_ind=ny)
        regions['lower_outer_SOL'] = Region(
                name='lower_outer_SOL', ds=ds, xinner_ind=ixs2, xouter_ind=nx,
                ylower_ind=jys22 + 1, yupper_ind=ny)
        _create_connection_x(regions, 'lower_inner_PFR', 'lower_inner_SOL')
        _create_connection_x(regions, 'inner_core', 'inner_SOL')
        _create_connection_x(regions, 'upper_inner_PFR', 'upper_inner_SOL')
        _create_connection_x(regions, 'upper_outer_PFR', 'upper_outer_SOL')
        _create_connection_x(regions, 'outer_core', 'outer_SOL')
        _create_connection_x(regions, 'lower_outer_PFR', 'lower_outer_SOL')
        _create_connection_y(regions, 'lower_inner_PFR', 'lower_outer_PFR')
        _create_connection_y(regions, 'lower_inner_SOL', 'inner_SOL')
        _create_connection_y(regions, 'inner_core', 'outer_core')
        _create_connection_y(regions, 'outer_core', 'inner_core')
        _create_connection_y(regions, 'inner_SOL', 'upper_inner_SOL')
        _create_connection_y(regions, 'upper_outer_PFR', 'upper_inner_PFR')
        _create_connection_y(regions, 'upper_outer_SOL', 'outer_SOL')
        _create_connection_y(regions, 'outer_SOL', 'lower_outer_SOL')
    elif topology == 'single-null':
        regions['inner_PFR'] = Region(
                name='inner_PFR', ds=ds, xinner_ind=0, xouter_ind=ixs1, ylower_ind=0,
                yupper_ind=jys11 + 1)
        regions['inner_SOL'] = Region(
                name='inner_SOL', ds=ds, xinner_ind=ixs1, xouter_ind=nx, ylower_ind=0,
                yupper_ind=jys11 + 1)
        regions['core'] = Region(
                name='core', ds=ds, xinner_ind=0, xouter_ind=ixs1, ylower_ind=jys11 + 1,
                yupper_ind=jys22 + 1)
        regions['SOL'] = Region(
                name='SOL', ds=ds, xinner_ind=ixs1, xouter_ind=nx, ylower_ind=jys11 + 1,
                yupper_ind=jys22 + 1)
        regions['outer_PFR'] = Region(
                name='lower_PFR', ds=ds, xinner_ind=0, xouter_ind=ixs1,
                ylower_ind=jys22 + 1, yupper_ind=ny)
        regions['outer_SOL'] = Region(
                name='lower_SOL', ds=ds, xinner_ind=ixs1, xouter_ind=nx,
                ylower_ind=jys22 + 1, yupper_ind=ny)
        _create_connection_x(regions, 'inner_PFR', 'inner_SOL')
        _create_connection_x(regions, 'core', 'SOL')
        _create_connection_x(regions, 'outer_PFR', 'outer_SOL')
        _create_connection_y(regions, 'inner_PFR', 'outer_PFR')
        _create_connection_y(regions, 'inner_SOL', 'SOL')
        _create_connection_y(regions, 'core', 'core')
        _create_connection_y(regions, 'SOL', 'outer_SOL')
    elif topology == 'limiter':
        regions['core'] = Region(
                name='core', ds=ds, xinner_ind=0, xouter_ind=ixs1, ylower_ind=ybndry,
                yupper_ind=ny - ybndry)
        regions['SOL'] = Region(
                name='SOL', ds=ds, xinner_ind=ixs1, xouter_ind=nx, ylower_ind=0,
                yupper_ind=ny)
        _create_connection_x(regions, 'core', 'SOL')
        _create_connection_y(regions, 'core', 'core')
    elif topology == 'core':
        regions['core'] = Region(
                name='core', ds=ds, xinner_ind=0, xouter_ind=nx, ylower_ind=ybndry,
                yupper_ind=ny - ybndry)
        _create_connection_y(regions, 'core', 'core')
    elif topology == 'sol':
        regions['SOL'] = Region(
                name='SOL', ds=ds, xinner_ind=0, xouter_ind=nx, ylower_ind=0,
                yupper_ind=ny)
    elif topology == 'xpoint':
        regions['lower_inner_PFR'] = Region(
                name='lower_inner_PFR', ds=ds, xinner_ind=0, xouter_ind=ixs1,
                ylower_ind=0, yupper_ind=jys11 + 1)
        regions['lower_inner_SOL'] = Region(
                name='lower_inner_SOL', ds=ds, xinner_ind=ixs1, xouter_ind=nx,
                ylower_ind=0, yupper_ind=jys11 + 1)
        regions['upper_inner_PFR'] = Region(
                name='upper_inner_PFR', ds=ds, xinner_ind=0, xouter_ind=ixs1,
                ylower_ind=jys11 + 1, yupper_ind=nyinner)
        regions['upper_inner_SOL'] = Region(
                name='upper_inner_SOL', ds=ds, xinner_ind=ixs1, xouter_ind=nx,
                ylower_ind=jys11 + 1, yupper_ind=nyinner)
        regions['upper_outer_PFR'] = Region(
                name='upper_outer_PFR', ds=ds, xinner_ind=0, xouter_ind=ixs1,
                ylower_ind=nyinner, yupper_ind=jys22 + 1)
        regions['upper_outer_SOL'] = Region(
                name='upper_outer_SOL', ds=ds, xinner_ind=ixs1, xouter_ind=nx,
                ylower_ind=nyinner, yupper_ind=jys22 + 1)
        regions['lower_outer_PFR'] = Region(
                name='lower_outer_PFR', ds=ds, xinner_ind=0, xouter_ind=ixs1,
                ylower_ind=jys22 + 1, yupper_ind=ny)
        regions['lower_outer_SOL'] = Region(
                name='lower_outer_SOL', ds=ds, xinner_ind=ixs1, xouter_ind=nx,
                ylower_ind=jys22 + 1, yupper_ind=ny)
        _create_connection_x(regions, 'lower_inner_PFR', 'lower_inner_SOL')
        _create_connection_x(regions, 'upper_inner_PFR', 'upper_inner_SOL')
        _create_connection_x(regions, 'upper_outer_PFR', 'upper_outer_SOL')
        _create_connection_x(regions, 'lower_outer_PFR', 'lower_outer_SOL')
        _create_connection_y(regions, 'lower_inner_PFR', 'lower_outer_PFR')
        _create_connection_y(regions, 'lower_inner_SOL', 'upper_inner_SOL')
        _create_connection_y(regions, 'upper_outer_PFR', 'upper_inner_PFR')
        _create_connection_y(regions, 'upper_outer_SOL', 'lower_outer_SOL')
    else:
        raise NotImplementedError("Topology '" + topology + "' is not implemented")

    ds = _set_attrs_on_all_vars(ds, 'regions', regions)

    return ds


def _concat_inner_guards(da, da_global, mxg):
    """
    Concatenate inner x-guard cells to da, which is in a single region, getting the guard
    cells from the global array
    """

    if mxg <= 0:
        return da

    myg_da = da_global.metadata['MYG']
    keep_yboundaries = da_global.metadata['keep_yboundaries']
    xcoord = da_global.metadata['bout_xdim']
    ycoord = da_global.metadata['bout_ydim']

    da_inner = da_global.bout.from_region(da.region.connection_inner_x, with_guards=0)

    if (myg_da > 0 and keep_yboundaries and da.region.connection_lower_y is not None
            and da_inner.region.connection_lower_y is None):
        # da_inner may have more points in the y-direction, because it has an actual
        # boundary, not a connection. Need to remove any extra points
        da_inner = da_inner.isel(**{ycoord: slice(myg_da, None)})
    if (myg_da > 0 and keep_yboundaries and da.region.connection_upper_y is not None
            and da_inner.region.connection_upper_y is None):
        # da_inner may have more points in the y-direction, because it has an actual
        # boundary, not a connection. Need to remove any extra points
        da_inner = da_inner.isel(**{ycoord: slice(None, -myg_da)})

    # select just the points we need to fill the guard cells of da
    da_inner = da_inner.isel(**{xcoord: slice(-mxg, None)})

    if (myg_da > 0 and keep_yboundaries and da.region.connection_lower_y is None
            and da_inner.region.connection_lower_y is not None):
        # da_inner may have fewer points in the y-direction, because it has a connection,
        # not an actual boundary. Need to get the extra points from its connection
        da_inner_lower = da_global.bout.from_region(da_inner.region.connection_lower_y,
                                                    with_guards=0)
        da_inner_lower = da_inner_lower.isel(**{xcoord: slice(-mxg, None),
                                                ycoord: slice(-myg_da, None)})
        save_region = da_inner.region
        da_inner = xr.concat((da_inner_lower, da_inner), ycoord, join='exact')
        # xr.concat takes attributes from the first variable, but we need da_inner's
        # region
        da_inner.attrs['region'] = save_region
    if (myg_da > 0 and keep_yboundaries and da.region.connection_upper_y is None
            and da_inner.region.connection_upper_y is not None):
        # da_inner may have fewer points in the y-direction, because it has a connection,
        # not an actual boundary. Need to get the extra points from its connection
        da_inner_upper = da_global.bout.from_region(da_inner.region.connection_upper_y,
                                                    with_guards=0)
        da_inner_upper = da_inner_upper.isel(**{xcoord: slice(-mxg, None),
                                                ycoord: slice(myg_da)})
        da_inner = xr.concat((da_inner, da_inner_upper), ycoord, join='exact')
        # xr.concat takes attributes from the first variable, so region is OK

    if xcoord in da.coords:
        # Some coordinates may not be single-valued, so use local coordinates for
        # neighbouring region, not communicated ones. Ensures the coordinates are
        # continuous so that interpolation works correctly near the boundaries.
        slices = da.region.get_inner_guards_slices(mxg=mxg)
        new_xcoord = da_global[xcoord].isel(**{xcoord: slices[xcoord]})
        new_ycoord = da_global[ycoord].isel(**{ycoord: slices[ycoord]})
        da_inner = da_inner.assign_coords(**{xcoord: new_xcoord, ycoord: new_ycoord})

    save_region = da.region
    da = xr.concat((da_inner, da), xcoord, join='exact')
    # xr.concat takes attributes from the first variable (for xarray>=0.15.0, keeps attrs
    # that are the same in all objects for xarray<0.15.0)
    da.attrs['region'] = save_region

    return da


def _concat_outer_guards(da, da_global, mxg):
    """
    Concatenate outer x-guard cells to da, which is in a single region, getting the guard
    cells from the global array
    """

    if mxg <= 0:
        return da

    myg_da = da_global.metadata['MYG']
    keep_yboundaries = da_global.metadata['keep_yboundaries']
    xcoord = da_global.metadata['bout_xdim']
    ycoord = da_global.metadata['bout_ydim']

    da_outer = da_global.bout.from_region(da.region.connection_outer_x, with_guards=0)

    if (myg_da > 0 and keep_yboundaries and da.region.connection_lower_y is not None
            and da_outer.region.connection_lower_y is None):
        # da_outer may have more points in the y-direction, because it has an actual
        # boundary, not a connection. Need to remove any extra points
        da_outer = da_outer.isel(**{ycoord: slice(myg_da, None)})
    if (myg_da > 0 and keep_yboundaries and da.region.connection_upper_y is not None
            and da_outer.region.connection_upper_y is None):
        # da_outer may have more points in the y-direction, because it has an actual
        # boundary, not a connection. Need to remove any extra points
        da_outer = da_outer.isel(**{ycoord: slice(None, -myg_da)})

    # select just the points we need to fill the guard cells of da
    da_outer = da_outer.isel(**{xcoord: slice(mxg)})

    if (myg_da > 0 and keep_yboundaries and da.region.connection_lower_y is None
            and da_outer.region.connection_lower_y is not None):
        # da_outer may have fewer points in the y-direction, because it has a connection,
        # not an actual boundary. Need to get the extra points from its connection
        da_outer_lower = da_global.bout.from_region(da_outer.region.connection_lower_y,
                                                    with_guards=0)
        da_outer_lower = da_outer_lower.isel(**{xcoord: slice(-mxg, None),
                                                ycoord: slice(-myg_da, None)})
        save_region = da_outer.region
        da_outer = xr.concat((da_outer_lower, da_outer), ycoord, join='exact')
        # xr.concat takes attributes from the first variable, but we need da_outer's
        # region
        da_outer.attrs['region'] = save_region
    if (myg_da > 0 and keep_yboundaries and da.region.connection_upper_y is None
            and da_outer.region.connection_upper_y is not None):
        # da_outer may have fewer points in the y-direction, because it has a connection,
        # not an actual boundary. Need to get the extra points from its connection
        da_outer_upper = da_global.bout.from_region(da_outer.region.connection_upper_y,
                                                    with_guards=0)
        da_outer_upper = da_outer_upper.isel(**{xcoord: slice(-mxg, None),
                                                ycoord: slice(myg_da)})
        da_outer = xr.concat((da_outer, da_outer_upper), ycoord, join='exact')
        # xr.concat takes attributes from the first variable, so region is OK

    if xcoord in da.coords:
        # Some coordinates may not be single-valued, so use local coordinates for
        # neighbouring region, not communicated ones. Ensures the coordinates are
        # continuous so that interpolation works correctly near the boundaries.
        slices = da.region.get_outer_guards_slices(mxg=mxg)
        new_xcoord = da_global[xcoord].isel(**{xcoord: slices[xcoord]})
        new_ycoord = da_global[ycoord].isel(**{ycoord: slices[ycoord]})
        da_outer = da_outer.assign_coords(**{xcoord: new_xcoord, ycoord: new_ycoord})

    save_region = da.region
    da = xr.concat((da, da_outer), xcoord, join='exact')
    # xarray<0.15.0 only keeps attrs that are the same on all variables passed to concat
    da.attrs['region'] = save_region

    return da


def _concat_lower_guards(da, da_global, mxg, myg):
    """
    Concatenate lower y-guard cells to da, which is in a single region, getting the guard
    cells from the global array
    """

    if myg <= 0:
        return da

    xcoord = da_global.metadata['bout_xdim']
    ycoord = da_global.metadata['bout_ydim']

    da_lower = da_global.bout.from_region(da.region.connection_lower_y,
                                          with_guards={xcoord: mxg, ycoord: 0})

    # select just the points we need to fill the guard cells of da
    da_lower = da_lower.isel(**{ycoord: slice(-myg, None)})

    if ycoord in da.coords:
        # Some coordinates may not be single-valued, so use local coordinates for
        # neighbouring region, not communicated ones. Ensures the coordinates are
        # continuous so that interpolation works correctly near the boundaries.
        slices = da.region.get_lower_guards_slices(mxg=mxg, myg=myg)

        if slices[ycoord].start < 0:
            # For core-only or limiter topologies, the lower-y slice may be out of the
            # global array bounds
            raise ValueError(
                    'Trying to fill a slice which is not present in the global array, '
                    'so do not have coordinate values for it. Try setting '
                    'keep_yboundaries=True when calling open_boutdataset.')

        new_xcoord = da_global[xcoord].isel(**{xcoord: slices[xcoord]})
        new_ycoord = da_global[ycoord].isel(**{ycoord: slices[ycoord]})
        da_lower = da_lower.assign_coords(**{xcoord: new_xcoord, ycoord: new_ycoord})

    save_region = da.region
    da = xr.concat((da_lower, da), ycoord, join='exact')
    # xr.concat takes attributes from the first variable (for xarray>=0.15.0, keeps attrs
    # that are the same in all objects for xarray<0.15.0)
    da.attrs['region'] = save_region

    return da


def _concat_upper_guards(da, da_global, mxg, myg):
    """
    Concatenate upper y-guard cells to da, which is in a single region, getting the guard
    cells from the global array
    """

    if myg <= 0:
        return da

    xcoord = da_global.metadata['bout_xdim']
    ycoord = da_global.metadata['bout_ydim']

    da_upper = da_global.bout.from_region(da.region.connection_upper_y,
                                          with_guards={xcoord: mxg, ycoord: 0})
    # select just the points we need to fill the guard cells of da
    da_upper = da_upper.isel(**{ycoord: slice(myg)})

    if ycoord in da.coords:
        # Some coordinates may not be single-valued, so use local coordinates for
        # neighbouring region, not communicated ones. Ensures the coordinates are
        # continuous so that interpolation works correctly near the boundaries.
        slices = da.region.get_upper_guards_slices(mxg=mxg, myg=myg)

        if slices[ycoord].stop > da_global.sizes[ycoord]:
            # For core-only or limiter topologies, the upper-y slice may be out of the
            # global array bounds
            raise ValueError(
                    'Trying to fill a slice which is not present in the global array, '
                    'so do not have coordinate values for it. Try setting '
                    'keep_yboundaries=True when calling open_boutdataset.')

        new_xcoord = da_global[xcoord].isel(**{xcoord: slices[xcoord]})
        new_ycoord = da_global[ycoord].isel(**{ycoord: slices[ycoord]})
        da_upper = da_upper.assign_coords(**{xcoord: new_xcoord, ycoord: new_ycoord})

    save_region = da.region
    da = xr.concat((da, da_upper), ycoord, join='exact')
    # xarray<0.15.0 only keeps attrs that are the same on all variables passed to concat
    da.attrs['region'] = save_region

    return da
