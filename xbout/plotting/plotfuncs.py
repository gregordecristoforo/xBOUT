import matplotlib
import matplotlib.pyplot as plt
import numpy as np

import xarray as xr

from .utils import (
    _create_norm,
    _decompose_regions,
    _is_core_only,
    _k3d_plot_isel,
    _make_structured_triangulation,
    plot_separatrices,
    plot_targets,
)


def regions(da, ax=None, **kwargs):
    """
    Plots each logical plotting region as a different color for debugging.

    Uses matplotlib.pcolormesh
    """

    x = kwargs.pop("x", "R")
    y = kwargs.pop("y", "Z")

    if len(da.dims) != 2:
        raise ValueError("da must be 2D (x,y)")

    if ax is None:
        fig, ax = plt.subplots()

    da_regions = _decompose_regions(da)

    colored_regions = [
        xr.full_like(da_region, fill_value=num / len(regions))
        for num, da_region in enumerate(da_regions.values())
    ]

    return [
        region.plot.pcolormesh(
            x=x,
            y=y,
            vmin=0,
            vmax=1,
            cmap="tab20",
            infer_intervals=False,
            add_colorbar=False,
            ax=ax,
            **kwargs,
        )
        for region in colored_regions
    ]


def plot2d_wrapper(
    da,
    method,
    *,
    ax=None,
    separatrix=True,
    targets=True,
    add_limiter_hatching=True,
    gridlines=None,
    cmap=None,
    norm=None,
    logscale=None,
    vmin=None,
    vmax=None,
    aspect=None,
    **kwargs,
):
    """
    Make a 2D plot using an xarray method, taking into account branch cuts (X-points).

    Wraps `xarray.plot` methods, so automatically adds labels.

    Parameters
    ----------
    da : xarray.DataArray
        A 2D (x,y) DataArray of data to plot
    method : xarray.plot.*
        An xarray plotting method to use
    ax : Axes, optional
        A matplotlib axes instance to plot to. If None, create a new
        figure and axes, and plot to that
    separatrix : bool, optional
        Add dashed lines showing separatrices
    targets : bool, optional
        Draw solid lines at the target surfaces
    add_limiter_hatching : bool, optional
        Draw hatched areas at the targets
    gridlines : bool, int or slice or dict of bool, int or slice, optional
        If True, draw grid lines on the plot. If an int is passed, it is used as the
        stride when plotting grid lines (to reduce the number on the plot). If a slice is
        passed it is used to select the grid lines to plot.
        If a dict is passed, the 'x' entry (bool, int or slice) is used for the radial
        grid-lines and the 'y' entry for the poloidal grid lines.
    cmap : Matplotlib colormap, optional
        Color map to use for the plot
    norm : matplotlib.colors.Normalize instance, optional
        Normalization to use for the color scale.
        Cannot be set at the same time as 'logscale'
    logscale : bool or float, optional
        If True, default to a logarithmic color scale instead of a linear one.
        If a non-bool type is passed it is treated as a float used to set the linear
        threshold of a symmetric logarithmic scale as
        linthresh=min(abs(vmin),abs(vmax))*logscale, defaults to 1e-5 if True is passed.
        Cannot be set at the same time as 'norm'
    vmin : float, optional
        Minimum value for the color scale
    vmax : float, optional
        Maximum value for the color scale
    aspect : str or float, optional
        Passed to ax.set_aspect(). By default 'equal' is used.
    levels : int or iterable, optional
        Only used by contour or contourf, sets the number of levels (if int) or the level
        values (if iterable)
    **kwargs : optional
        Additional arguments are passed on to method

    Returns
    -------
    artists
        List of the artist instances
    """

    # TODO generalise this
    x = kwargs.pop("x", "R")
    y = kwargs.pop("y", "Z")

    if len(da.dims) != 2:
        raise ValueError("da must be 2D (x,y)")

    if ax is None:
        fig, ax = plt.subplots()
    else:
        fig = ax.get_figure()

    if aspect is None:
        aspect = "equal"
    ax.set_aspect(aspect)

    if vmin is None:
        vmin = da.min().values
    if vmax is None:
        vmax = da.max().values

    # set up 'levels' if needed
    if method is xr.plot.contourf or method is xr.plot.contour:
        levels = kwargs.get("levels", 7)
        if isinstance(levels, np.int):
            levels = np.linspace(vmin, vmax, levels, endpoint=True)
            # put levels back into kwargs
            kwargs["levels"] = levels
        else:
            levels = np.array(list(levels))
            kwargs["levels"] = levels
            vmin = np.min(levels)
            vmax = np.max(levels)

        levels = kwargs.get("levels", 7)
        if isinstance(levels, np.int):
            levels = np.linspace(vmin, vmax, levels, endpoint=True)
            # put levels back into kwargs
            kwargs["levels"] = levels
        else:
            levels = np.array(list(levels))
            kwargs["levels"] = levels
            vmin = np.min(levels)
            vmax = np.max(levels)

    # Need to create a colorscale that covers the range of values in the whole array.
    # Using the add_colorbar argument would create a separate color scale for each
    # separate region, which would not make sense.
    if method is xr.plot.contourf:
        # create colorbar
        norm = _create_norm(logscale, norm, vmin, vmax)
        sm = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
        # make colorbar have only discrete levels
        # average the levels so that colors in the colorbar represent the intervals
        # between the levels, as contourf colors filled regions between the given levels.
        cmap = matplotlib.colors.LinearSegmentedColormap.from_list(
            "discrete cmap",
            sm.to_rgba(0.5 * (levels[:-1] + levels[1:])),
            len(levels) - 1,
        )
        # re-make sm with new cmap
        sm = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
        sm.set_array([])
        fig.colorbar(sm, ticks=levels, ax=ax)
    elif method is xr.plot.contour:
        # create colormap to be shared by all regions
        norm = matplotlib.colors.Normalize(vmin=levels[0], vmax=levels[-1])
        sm = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
        cmap = matplotlib.colors.ListedColormap(
            sm.to_rgba(levels), name="discrete cmap"
        )
    else:
        # pass vmin and vmax through kwargs as they are not used for contourf or contour
        # plots
        kwargs["vmin"] = vmin
        kwargs["vmax"] = vmax

        # create colorbar
        norm = _create_norm(logscale, norm, vmin, vmax)
        sm = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
        sm.set_array([])
        cmap = sm.get_cmap()
        fig.colorbar(sm, ax=ax)

    if method is xr.plot.pcolormesh:
        if "infer_intervals" not in kwargs:
            kwargs["infer_intervals"] = False

    da_regions = _decompose_regions(da)

    # Plot all regions on same axis
    add_labels = [True] + [False] * (len(da_regions) - 1)
    artists = [
        method(
            region,
            x=x,
            y=y,
            ax=ax,
            add_colorbar=False,
            add_labels=add_label,
            cmap=cmap,
            **kwargs,
        )
        for region, add_label in zip(da_regions.values(), add_labels)
    ]

    if method is xr.plot.contour:
        # using extend='neither' guarantees that the ends of the colorbar will be
        # consistent, regardless of whether artists[0] happens to have any values below
        # vmin or above vmax. Unfortunately it does not seem to be possible to combine
        # all the QuadContourSet objects in artists to have this done properly. It would
        # be nicer to always draw triangular ends as if there are always values below
        # vmin and above vmax, but there does not seem to be an option available to force
        # this.
        extend = kwargs.get("extend", "neither")
        fig.colorbar(artists[0], ax=ax, extend=extend)

    if gridlines is not None:
        # convert gridlines to dict
        if not isinstance(gridlines, dict):
            gridlines = {"x": gridlines, "y": gridlines}

        for key, value in gridlines.items():
            if value is True:
                gridlines[key] = slice(None)
            elif isinstance(value, int):
                gridlines[key] = slice(0, None, value)
            elif value is not None:
                if not isinstance(value, slice):
                    raise ValueError(
                        "Argument passed to gridlines must be bool, int or "
                        "slice. Got a " + type(value) + ", " + str(value)
                    )

        x_regions = [da_region[x] for da_region in da_regions.values()]
        y_regions = [da_region[y] for da_region in da_regions.values()]

        for x, y in zip(x_regions, y_regions):
            if (
                not da.metadata["bout_xdim"] in x.dims
                and not da.metadata["bout_ydim"] in x.dims
            ) or (
                not da.metadata["bout_xdim"] in y.dims
                and not da.metadata["bout_ydim"] in y.dims
            ):
                # Small regions around X-point do not have segments in x- or y-directions,
                # so skip
                # Currently this region does not exist, but there is a small white gap at
                # the X-point, so we might add it back in future
                continue
            if gridlines.get("x") is not None:
                # transpose in case Dataset or DataArray has been transposed away from the usual
                # form
                dim_order = (da.metadata["bout_xdim"], da.metadata["bout_ydim"])
                yarg = {da.metadata["bout_ydim"]: gridlines["x"]}
                plt.plot(
                    x.isel(**yarg).transpose(*dim_order, transpose_coords=True),
                    y.isel(**yarg).transpose(*dim_order, transpose_coords=True),
                    color="k",
                    lw=0.1,
                )
            if gridlines.get("y") is not None:
                xarg = {da.metadata["bout_xdim"]: gridlines["y"]}
                # Need to plot transposed arrays to make gridlines that go in the
                # y-direction
                dim_order = (da.metadata["bout_ydim"], da.metadata["bout_xdim"])
                plt.plot(
                    x.isel(**xarg).transpose(*dim_order, transpose_coords=True),
                    y.isel(**yarg).transpose(*dim_order, transpose_coords=True),
                    color="k",
                    lw=0.1,
                )

    ax.set_title(da.name)

    if _is_core_only(da):
        separatrix = False
        targets = False

    if separatrix:
        plot_separatrices(da_regions, ax, x=x, y=y)

    if targets:
        plot_targets(da_regions, ax, x=x, y=y, hatching=add_limiter_hatching)

    return artists


def plot3d(
    da,
    style="surface",
    engine="k3d",
    levels=None,
    outputgrid=(100, 100, 25),
    color_map=None,
    plot=None,
    **kwargs,
):
    """
    Make a 3d plot

    Parameters
    ----------
    style : {'surface', 'poloidal planes'}
        Type of plot to make:
        - 'surface' plots the outer surface of the DataArray
        - 'poloidal planes' plots each poloidal plane in the DataArray
    engine : {'k3d', 'mayavi'}
        3d plotting library to use
    levels : sequence of (float, float)
        For isosurface, the pairs of (level-value, opacity) to plot
    outputgrid : (int, int, int) or None, optional
        For isosurface or volume plots, the number of points to use in the Cartesian
        (X,Y,Z) grid, that data is interpolated onto for plotting. If None, then do not
        interpolate and treat "bout_xdim", "bout_ydim" and "bout_zdim" coordinates as
        Cartesian (useful for slab simulations).
    color_map : k3d color map, optional
        Color map for k3d plots
    plot : k3d plot instance, optional
        Existing plot to add new plots to
    """

    if len(da.dims) != 3:
        raise ValueError(f"plot3d needs to be passed 3d data. Got {da.dims}.")

    da = da.bout.add_cartesian_coordinates()
    vmin = kwargs.pop("vmin", float(da.min().values))
    vmax = kwargs.pop("vmax", float(da.max().values))
    xcoord = da.metadata["bout_xdim"]
    ycoord = da.metadata["bout_ydim"]
    zcoord = da.metadata["bout_zdim"]

    if engine == "k3d":
        import k3d

        if color_map is None:
            color_map = k3d.matplotlib_color_maps.Viridis

        if plot is None:
            plot = k3d.plot()
            return_plot = True
        else:
            return_plot = False

        if style == "isosurface" or style == "volume":
            data = da.copy(deep=True).load()
            # data = da.bout.from_region('upper_outer_PFR').copy(deep=True).load()
            datamin = data.min().item()
            datamax = data.max().item()
            # data[0, :, :] = datamin - 2.*(datamax - datamin)
            # data[-1, :, :] = datamin - 2.*(datamax - datamin)
            # data[:, 0, :] = datamin - 2.*(datamax - datamin)
            # data[:, -1, :] = datamin - 2.*(datamax - datamin)

            if outputgrid is None:
                Xmin = da[da.metadata["bout_xdim"]][0]
                Xmax = da[da.metadata["bout_xdim"]][-1]
                Ymin = da[da.metadata["bout_ydim"]][0]
                Ymax = da[da.metadata["bout_ydim"]][-1]
                Zmin = da[da.metadata["bout_zdim"]][0]
                Zmax = da[da.metadata["bout_zdim"]][-1]

                grid = da.astype(np.float32).values
            else:
                ##interpolate to Cartesian array
                # rpoints = 200
                # zpoints = 200
                # Rmin = data['R'].min()
                # Rmax = data['R'].max()
                # Zmin = data['Z'].min()
                # Zmax = data['Z'].max()
                # nx, ny, nz = data.shape

                # newR = (xr.DataArray(np.linspace(Rmin, Rmax, rpoints), dims='r')
                #          .expand_dims({'z': zpoints, 'zeta': nz}, axis=[0, 1]))
                # newZ = (xr.DataArray(np.linspace(Zmin, Zmax, zpoints), dims='z')
                #        .expand_dims({'r': rpoints, 'zeta': nz}, axis=[2, 1]))
                # newzeta = data['zeta'].expand_dims({'r': rpoints, 'z': zpoints}, axis=[2, 0])

                # R = data['R'].expand_dims({'zeta': nz}, axis=2)
                # Z = data['Z'].expand_dims({'zeta': nz}, axis=2)
                # zeta = data['zeta'].expand_dims({'x': nx, 'theta': ny}, axis=[0, 1])

                # from scipy.interpolate import griddata
                # grid = griddata(
                #        (R.values.flatten(), Z.values.flatten(),
                #            zeta.values.flatten()),
                #        data.values.flatten(),
                #        (newR.values, newZ.values, newzeta.values),
                #        method='nearest')

                # if style == 'isosurface':
                #    plot += k3d.marching_cubes(grid.astype(np.float32),
                #                               bounds=[Rmin, Rmax, 0., 2.*np.pi, Zmin, Zmax],
                #                               level=1.,
                #                              )
                # elif style == 'volume':
                #    plot += k3d.volume(grid.astype(np.float32),
                #                       color_range=[datamin, datamax],
                #                       bounds=[Rmin, Rmax, 0., 2.*np.pi, Zmin, Zmax],
                #                      )
                # else:
                #    raise ValueError(f'{style} not supported here')

                # return plot

                xpoints, ypoints, zpoints = outputgrid
                nx, ny, nz = data.shape

                # interpolate to Cartesian array
                Xmin = data["X_cartesian"].min()
                Xmax = data["X_cartesian"].max()
                Ymin = data["Y_cartesian"].min()
                Ymax = data["Y_cartesian"].max()
                Zmin = data["Z_cartesian"].min()
                Zmax = data["Z_cartesian"].max()
                Rmin = data["R"].min()
                Rmax = data["R"].max()
                Zmin = data["Z"].min()
                Zmax = data["Z"].max()
                newX = xr.DataArray(np.linspace(Xmin, Xmax, xpoints), dims="x").expand_dims(
                    {"y": ypoints, "z": zpoints}, axis=[1, 0]
                )
                newY = xr.DataArray(np.linspace(Ymin, Ymax, ypoints), dims="y").expand_dims(
                    {"x": xpoints, "z": zpoints}, axis=[2, 0]
                )
                newZ = xr.DataArray(np.linspace(Zmin, Zmax, zpoints), dims="z").expand_dims(
                    {"x": xpoints, "y": ypoints}, axis=[2, 1]
                )
                newR = np.sqrt(newX ** 2 + newY ** 2)
                newzeta = np.arctan2(newY, newX)  # .values

                from scipy.interpolate import (
                    RegularGridInterpolator,
                    griddata,
                    LinearNDInterpolator,
                )

                # need to create 3d arrays of x and y values
                # create interpolators for x and y from R and Z
                # print('interpolate x')
                # newx = griddata((data['R'].values.flatten(), data['Z'].values.flatten()),
                #                data['x'].expand_dims({'theta': ny}, axis=1).values.flatten(),
                #                (newR.values, newZ.values),
                #                method = 'linear',
                #               )
                # print('interpolate y')
                # newy = griddata((data['R'].values.flatten(), data['Z'].values.flatten()),
                #                data['theta'].expand_dims({'x': nx}, axis=0).values.flatten(),
                #                (newR.values, newZ.values),
                #                method = 'linear',
                #               )
                # from scipy.interpolate import griddata
                # print('start interpolating')
                # grid = griddata(
                #        (data['X_cartesian'].values.flatten(),
                #            data['Y_cartesian'].values.flatten(),
                #            data['Z_cartesian'].values.flatten()),
                #        data.values.flatten(),
                #        (newX.values, newY.values, newZ.values),
                #        method='nearest',
                #        fill_value = datamin - 2.*(datamax - datamin)
                #       )
                # print('done interpolating')
                # print('start interpolating')
                # x = data['x']
                # y = data['theta']
                # z = data['zeta']
                # interp = RegularGridInterpolator(
                #          (x, y, z),
                #          data.values,
                #          bounds_error = False,
                #          fill_value = datamin - 2.*(datamax - datamin)
                #         )
                # grid = interp((newx, newy, newzeta),
                #              method='linear',
                #             )
                # print('done interpolating')
                print("start interpolating")
                # R3d = data['R'].expand_dims({'zeta': nz}, axis=2)
                # Z3d = data['Z'].expand_dims({'zeta': nz}, axis=2)
                # zeta3d = data['zeta'].expand_dims({'x': nx, 'theta': ny}, axis=(0, 1))
                # grid = griddata(
                #        (R3d.values.flatten(),
                #            Z3d.values.flatten(),
                #            zeta3d.values.flatten()),
                #        data.values.flatten(),
                #        (newR.values, newZ.values, newzeta.values),
                #        method='linear',
                #        fill_value = datamin - 2.*(datamax - datamin)
                #       )
                # interp = LinearNDInterpolator((R3d.values.flatten(), Z3d.values.flatten,
                #                                  zeta3d.values.flatten()),
                #                              data.values.flatten(),
                #                              fill_value = datamin - 2.*(datamax - datamin)
                #                             )
                # print('made interpolator')
                # grid = interp((newR.values, newZ.values, newzeta.values), method='linear')
                # Rcyl = (xr.DataArray(np.linspace(Rmin, Rmax, zpoints), dims='r')
                #          .expand_dims({'z': zpoints, 'zeta': nz}, axis=[1, 2]))
                # Zcyl = (xr.DataArray(np.linspace(Zmin, Zmax, zpoints), dims='z')
                #          .expand_dims({'r': zpoints, 'zeta': nz}, axis=[0, 2]))
                Rcyl = xr.DataArray(
                    np.linspace(Rmin, Rmax, 2 * zpoints), dims="r"
                ).expand_dims({"z": 2 * zpoints}, axis=1)
                Zcyl = xr.DataArray(
                    np.linspace(Zmin, Zmax, 2 * zpoints), dims="z"
                ).expand_dims({"r": 2 * zpoints}, axis=0)

                # Interpolate in two stages for efficiency. Unstructured 3d interpolation is
                # very slow. Unstructured 2d interpolation onto Cartesian (R, Z) grids,
                # followed by structured 3d interpolation onto the (X, Y, Z) grid, is much
                # faster.
                # Structured 3d interpolation straight from (psi, theta, zeta) to (X, Y, Z)
                # leaves artifacts in the output, because theta does not vary continuously
                # everywhere (has branch cuts).

                # order of dimensions does not really matter here - output only depends on
                # shape of newR, newZ, newzeta. Possibly more efficient to assign the 2d
                # results in the loop to the last two dimensions, so put zeta first.
                data_cyl = np.zeros((nz, 2 * zpoints, 2 * zpoints))
                print("interpolate poloidal planes")
                for z in range(nz):
                    data_cyl[z] = griddata(
                        (data["R"].values.flatten(), data["Z"].values.flatten()),
                        data.isel(zeta=z).values.flatten(),
                        (Rcyl.values, Zcyl.values),
                        method="cubic",
                        fill_value=datamin - 2.0 * (datamax - datamin),
                    )
                print("build 3d interpolator")
                interp = RegularGridInterpolator(
                    (data["zeta"].values, Rcyl.isel(z=0).values, Zcyl.isel(r=0).values),
                    data_cyl,
                    bounds_error=False,
                    fill_value=datamin - 2.0 * (datamax - datamin),
                )
                print("do 3d interpolation")
                grid = interp(
                    (newzeta, newR, newZ),
                    method="linear",
                )
                print("done interpolating")

            if style == "isosurface":
                if levels is None:
                    levels = [(0.5 * (datamin + datamax), 1.0)]
                for level, opacity in levels:
                    plot += k3d.marching_cubes(
                        grid.astype(np.float32),
                        bounds=[Xmin, Xmax, Ymin, Ymax, Zmin, Zmax],
                        level=level,
                        color_map=color_map,
                    )
            elif style == "volume":
                plot += k3d.volume(
                    grid.astype(np.float32),
                    color_range=[datamin, datamax],
                    bounds=[Xmin, Xmax, Ymin, Ymax, Zmin, Zmax],
                    color_map=color_map,
                )
            if return_plot:
                return plot
            else:
                return

        for region_name, da_region in _decompose_regions(da).items():

            npsi, ntheta, nzeta = da_region.shape

            if style == "surface":
                region = da_region.regions[region_name]

                if region.connection_inner_x is None:
                    # Plot the inner-x surface
                    plot += _k3d_plot_isel(
                        da_region,
                        {xcoord: 0},
                        vmin,
                        vmax,
                        color_map=color_map,
                        **kwargs,
                    )

                if region.connection_outer_x is None:
                    # Plot the outer-x surface
                    plot += _k3d_plot_isel(
                        da_region,
                        {xcoord: -1},
                        vmin,
                        vmax,
                        color_map=color_map,
                        **kwargs,
                    )

                if region.connection_lower_y is None:
                    # Plot the lower-y surface
                    plot += _k3d_plot_isel(
                        da_region,
                        {ycoord: 0},
                        vmin,
                        vmax,
                        color_map=color_map,
                        **kwargs,
                    )

                if region.connection_upper_y is None:
                    # Plot the upper-y surface
                    plot += _k3d_plot_isel(
                        da_region,
                        {ycoord: -1},
                        vmin,
                        vmax,
                        color_map=color_map,
                        **kwargs,
                    )

                # First z-surface
                plot += _k3d_plot_isel(
                    da_region, {zcoord: 0}, vmin, vmax, color_map=color_map, **kwargs
                )

                # Last z-surface
                plot += _k3d_plot_isel(
                    da_region, {zcoord: -1}, vmin, vmax, color_map=color_map, **kwargs
                )
            elif style == "poloidal planes":
                for zeta in range(nzeta):
                    plot += _k3d_plot_isel(
                        da_region,
                        {zcoord: zeta},
                        vmin,
                        vmax,
                        color_map=color_map,
                        **kwargs,
                    )
            else:
                raise ValueError(f"style='{style}' not implemented for engine='k3d'")

        if return_plot:
            return plot
        else:
            return

    elif engine == "mayavi":
        from mayavi import mlab

        if style == "surface":
            for region_name, da_region in _decompose_regions(da).items():
                region = da_region.regions[region_name]

                # Always include z-surfaces
                surface_selections = [
                    {da.metadata["bout_zdim"]: 0},
                    {da.metadata["bout_zdim"]: -1},
                ]
                if region.connection_inner_x is None:
                    # Plot the inner-x surface
                    surface_selections.append({da.metadata["bout_xdim"]: 0})
                if region.connection_outer_x is None:
                    # Plot the outer-x surface
                    surface_selections.append({da.metadata["bout_xdim"]: -1})
                if region.connection_lower_y is None:
                    # Plot the lower-y surface
                    surface_selections.append({da.metadata["bout_ydim"]: 0})
                if region.connection_upper_y is None:
                    # Plot the upper-y surface
                    surface_selections.append({da.metadata["bout_ydim"]: -1})

                for surface_sel in surface_selections:
                    da_sel = da_region.isel(surface_sel)
                    X = da_sel["X_cartesian"].values
                    Y = da_sel["Y_cartesian"].values
                    Z = da_sel["Z_cartesian"].values
                    data = da_sel.values

                    mlab.mesh(X, Y, Z, scalars=data, vmin=vmin, vmax=vmax, **kwargs)
        else:
            raise ValueError(f"style='{style}' not implemented for engine='mayavi'")

        plt.show()
    else:
        raise ValueError(f"Unrecognised plot3d() 'engine' argument: {engine}")
