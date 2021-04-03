"""
This script gets the value of E(B-V) from Lallement's extinction map.
One pointing at a time.
"""

import argparse
import math

import h5py
import numpy as np
from scipy import interpolate

print("Setting up the map.")
#lallement = h5py.File('stilism_cube.h5',mode='r')
lallement = h5py.File('stilism_cube_2.h5',mode='r')
# lallement = h5py.File('map3D_GAIAdr2_feb2019.h5',mode='r')
stilism = lallement['stilism']
cube = stilism['cube_datas']
ebv = cube[:]

steps = cube.attrs['gridstep_values']
center = cube.attrs['sun_position'] * steps

x0 = np.arange(ebv.shape[0])*steps[0] - center[0]
y0 = np.arange(ebv.shape[1])*steps[1] - center[1]
z0 = np.arange(ebv.shape[2])*steps[2] - center[2]

rgi = interpolate.RegularGridInterpolator((x0,y0,z0),ebv, \
                                          bounds_error=False, fill_value=0.)
print("Setup complete.")

def gal_to_xyz(l,b,dist):
    l_rad = math.radians(l)
    b_rad = math.radians(b)
    R = dist*math.cos(b_rad)
    x = R*math.cos(l_rad)
    y = R*math.sin(l_rad)
    z = dist*math.sin(b_rad)
    return x,y,z

def generate_distances(dmax=4300, dmin=0.5, dstep=5):

    """Generates uniformly spaced distances."""

    # the default dmax is a little higher than the max distance at
    # (45,0).

    # refactored out of get_ebv_lallement so that we can access this
    # from other routines.

    return np.arange(dmin,dmax+0.1*dstep,dstep)
    
def find_max_distance(l=0, b=0, dists = np.array([])):

    """Find the maximum distance in a supplied array that is within the
bounds of the extinction samples

    Returns the maximum distance, the boolean array indicating which
    distances are inside the cube, and the xyz coordinates along this
    sight line from the distances.

    """

    # Split out from get_ebv_lallement so that we can call this piece
    # from other routines (e.g. when finding a sensible maximum
    # distance)
    
    if np.size(dists) < 1:
        return 0., np.array([]), np.array([])

    xyz = gal_to_xyz(l,b,dists)
    bInCube = (np.abs(xyz[0])<x0[-1]) & \
              (np.abs(xyz[1])<y0[-1]) & \
              (np.abs(xyz[2])<z0[-1])

    distMax = np.max(dists[bInCube])

    return distMax, bInCube, xyz
    
def get_ebv_lallement(l,b,dist,dmin=0.5,dstep=5, \
                      distances=np.array([]), \
                      Verbose=False):

    # Now accespts an array of distances. The stepsize is computed
    # element by element.
    
    # d_interp = np.arange(dmin,dist+0.1*dstep,dstep)
    if np.size(distances) < 1:
        d_interp = generate_distances(dist, dmin, dstep)
    else:
        d_interp = distances

    # generate the distance step allowing for nonunuform bins
    d_step = d_interp - np.roll(d_interp, 1)
    d_step[0] = d_step[1] # the zeroth element needs specifying
        
    # distance, boolean and xyz refactored to a separate method
    distMax, bInCube, xyz_interp = find_max_distance(l, b, d_interp)

    
    #xyz_interp = gal_to_xyz(l,b,d_interp)
    
    # WIC - update the selection for objects being inside the cube
    #bInCube = (np.abs(xyz_interp[0])<x0[-1]) & \
    #          (np.abs(xyz_interp[1])<y0[-1]) & \
    #          (np.abs(xyz_interp[2])<z0[-1])
    
    #distMax = np.max(d_interp[bInCube])

    # The regular grid interpolator returns zero for points outside
    # the cube, which do not impact the sum along the sight line.
    ebv_interp = rgi(xyz_interp)

    if np.sum(~bInCube) > 0 and Verbose:
        print("get_ebv_lallement INFO - some distances are beyond the cutoff %.1f pc for this sight line" % (distMax))
    
    #if not np.all( (np.abs(xyz_interp[0])<x0[-1]) & (np.abs(xyz_interp[1])<y0[-1]) & (np.abs(xyz_interp[2])<z0[-1])):
    #    max_dist = z0[-1] / math.sin(math.radians(b))

    #    # try max_dist_x
    #    max_dist_x = x0[-1] / math.cos(math.radians(b))

    #    max_dist = np.min([max_dist, max_dist_x])
        
    #    print("Queried distance of {}pc is out of the map. Maximum distance for this sightline is {:.1f}pc.".format(dist,max_dist))
    #    return np.nan, d_interp
    #ebv_interp = rgi(xyz_interp)
    return np.cumsum(ebv_interp*d_step), d_interp, distMax # it is an E(B-V), must multiply by Rv

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('l',type=float)
    parser.add_argument('b',type=float)
    parser.add_argument('dist',type=float)
    
    args = parser.parse_args()
    
    get_ebv_lallement(args.l,args.b,args.dist)