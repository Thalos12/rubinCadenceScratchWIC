"""
This script gets the value of E(B-V) from Lallement's extinction map.
One pointing at a time.
"""

import argparse
import math
import os

import h5py
import numpy as np
from scipy import interpolate

# lallement18 => 'stilism_cube.h5' --- returns E(B-V)
# lallement19 => 'stilism_cube_2.h5' --- returns A0

py_folder = os.path.dirname(os.path.abspath(__file__))
extmaps_dir = os.path.join(os.path.dirname(py_folder), 'extmaps')

class LallementDustMap(object):
    map_path = {'18':os.path.join(extmaps_dir,'stilism_cube.h5'),
                '19':os.path.join(extmaps_dir,'stilism_cube_2.h5')}

    def __init__(self, version='19', Rv=3.1):
        """Initialize Lallement's dust map.
        Beware that the version 2018 of the map has E(B-V) values while the 2019 one has
        A0 values.

        Args:
            version (str): Either '18' (map of E(B-V)) or '19' (map of A0).
        """
        if version not in self.map_path:
            message = "The version of the map must be either one of {}"\
                        .format(", ".join(self.map_path.keys()))
            raise ValueError(message)
        self.version = version

        map_path = self.map_path[self.version]
        print("Setting up the map {}.".format(map_path))
        dust_map = h5py.File(map_path, mode='r')
        stilism = dust_map['stilism']
        cube = stilism['cube_datas']
        ebv = cube[:]
        steps = cube.attrs['gridstep_values']
        center = cube.attrs['sun_position'] * steps
        self.x0 = np.arange(ebv.shape[0])*steps[0] - center[0]
        self.y0 = np.arange(ebv.shape[1])*steps[1] - center[1]
        self.z0 = np.arange(ebv.shape[2])*steps[2] - center[2]
        if version == '19':
            # At least for version 2019 of the map
            self.x0 += 0.5*steps[0]
            self.y0 += 0.5*steps[1]
            self.z0 += 0.5*steps[2] 
        self.rgi = interpolate.RegularGridInterpolator((self.x0, self.y0, self.z0), ebv, \
                                                        bounds_error=False, fill_value=0.)

        self.set_Rv(Rv)

        print("Setup complete.")

    def find_max_distance(self, l=0, b=0, dists=np.array([])):

        """Find the maximum distance in a supplied array that is within the
        bounds of the extinction samples

        Returns the maximum distance, the boolean array indicating which
        distances are inside the cube, and the xyz coordinates along this
        sight line from the distances.

        Args:
            l (float): Galactic latitude of the pointing.
            b (array): Galactic longitude of the pointing.
            dists (array): Array of distances

        """

        # Split out from get_ebv_lallement so that we can call this piece
        # from other routines (e.g. when finding a sensible maximum
        # distance)

        if np.size(dists) < 1:
            return 0., np.array([]), np.array([])

        xyz = gal_to_xyz(l, b, dists)
        bInCube = (np.abs(xyz[0]) < self.x0[-1]) & \
                (np.abs(xyz[1]) < self.y0[-1]) & \
                (np.abs(xyz[2]) < self.z0[-1])

        distMax = np.max(dists[bInCube])

        return distMax, bInCube, xyz
        
    def get_ebv(self, l,b,dist,dmin=0.5,dstep=5, \
                        distances=np.array([]), returnAv=False,\
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
        distMax, bInCube, xyz_interp = self.find_max_distance(l, b, d_interp)

        
        #xyz_interp = gal_to_xyz(l,b,d_interp)
        
        # WIC - update the selection for objects being inside the cube
        #bInCube = (np.abs(xyz_interp[0])<x0[-1]) & \
        #          (np.abs(xyz_interp[1])<y0[-1]) & \
        #          (np.abs(xyz_interp[2])<z0[-1])
        
        #distMax = np.max(d_interp[bInCube])

        # The regular grid interpolator returns zero for points outside
        # the cube, which do not impact the sum along the sight line.
        ebv_interp = self.rgi(xyz_interp)

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
        if returnAv:
            fact = self.fact_EBV2A
            if Verbose:
                print("Converting map version {} to Av (fact={})".format(self.version,fact))
            Av = np.cumsum(ebv_interp*d_step) * fact
            return Av, d_interp, distMax # it is an E(B-V), must multiply by Rv

        fact = self.fact_A2EBV
        if Verbose:
            print("Converting map version {} to E(B-V) (fact={})".format(self.version,fact))
        ebv = np.cumsum(ebv_interp*d_step) * fact
        return ebv, d_interp, distMax # it is an E(B-V), must multiply by Rv

    def set_Rv(self,newRv):
        """Update the value of Rv.

        Args:
            newRv (float]): New value of Rv to use in the conversion of the map.
        """

        self.Rv = newRv
        # factor for L19 is 1 because it is already extinction (A0)
        self.fact_EBV2A = newRv if self.version=='18' else 1
        # factor for L18 is 1 because it is already color excess (E(B-V))
        self.fact_A2EBV = 1 if self.version=='18' else 1/newRv


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


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('l',type=float)
    parser.add_argument('b',type=float)
    parser.add_argument('dist',type=float)
    parser.add_argument('-m','--map-version',dest='map_version',choices=['18','19'],type=str, default='19')
    parser.add_argument('-a','--return-av',dest='returnAv',action='store_true')
    parser.add_argument('-v','--verbose',action='store_true')
    parser.add_argument('-r','--Rv',type=float,default=3.1)
    
    args = parser.parse_args()
    
    lallement = LallementDustMap(args.map_version,Rv=args.Rv)
    ebv = lallement.get_ebv(args.l,args.b,args.dist,returnAv=args.returnAv,Verbose=args.verbose)
    print(ebv[0][-1])
