#
# compareExtinctions.py
#

#
# Use Bovy's dustmaps and Alessandro Mazzi's STILISM_LOCAL.py to
# compare the lallement and bovy extinction predictions for a
# particular sight line.
#

import mwdust
import stilism_local
import numpy as np

# for timings
import time

# For filename operations and optional directory creation
import os, glob

# To space the samples out in equatorial rather than galactic
from astropy.coordinates import SkyCoord
from astropy import units as u

from astropy.io import fits

# To determine spacings for samples about a central sight line
import healpy as hp

import matplotlib.pylab as plt
import matplotlib.gridspec as gridspec
plt.ion()

class lineofsight(object):

    """Evaluates E(B-V) vs distance for a particular line of sight. The
bovy et al. 2019 combined map can be passed in (as argument objBovy)
or can be re-imported here."""

    def __init__(self, l=0., b=4., \
                 distMaxPc=8000, distMinPc=0.5, distStepPc=10, \
                 distances=np.array([]), \
                 objBovy = None, Rv=3.1, \
                 distMaxCoarsePc = 15000., \
                 nDistBins = 400,
                 map_version='19'):

        # Sight line, max distance
        self.l = l
        self.b = b
        self.distMaxPc = distMaxPc
        self.distMinPc = distMinPc
        self.distStepPc = distStepPc

        # Maximum overall distance, *IF* we are using a coarser set of
        # bins for the bovy et al. distances than for the L19
        # distances.
        self.distMaxCoarsePc = distMaxCoarsePc

        # If we are generating distances to fit in a larger scheme
        # (where we need the same number of bins in every sight line),
        # we will need to enforce the total number of bins. If we're
        # letting stilism_local generate distances, this quantity is
        # ignored.
        self.nDistBins = nDistBins
        
        # Conversion factor from A_5555 to E(B-V)
        self.Rv=Rv
        
        # Distances generated by stilism_local, maximum distance along
        # this sight line for stilism_local
        if np.size(distances) > 0:
            self.distsPc = np.copy(distances)
        else:
            self.distsPc = np.array([])
        self.distLimPc = 1e9 # initialize very high

        # bovy et al. distance model - if not initialised
        if objBovy is None:
            self.objBovy = mwdust.Combined19()
        else:
            self.objBovy = objBovy

        # extinction evaluates
        self.ebvL19 = np.array([])
        self.ebvBovy = np.array([])

        # the version of LallementDustMap must be either '18' or '19', as string
        self.lallementMap = stilism_local.LallementDustMap(version=map_version,Rv=Rv)

    def generateDistances(self, Verbose=False):

        """Generates a distance array appropriate for this sight
line. Fine-grained distances are used over the range in which L+19 is
defined, then switches over to a coarse-grained set of distances for
Bovy et al.

        """

        # Generate an array of "fine-grained" distances
        distsFine = stilism_local.generate_distances(self.distMaxPc,
                                                     self.distMinPc, \
                                                     self.distStepPc)

        # Find the maximum distance that fits inside the L19
        # volume. Currently the routine in stilism_local returns the
        # boolean and the xyz coords since those are needed for the
        # interpolation. We don't need those quantities here, though.
        distMax, _, _ = stilism_local.find_max_distance(self.l, self.b, \
                                                        distsFine)

        # OK now we set the maximum distance for the "fine" set of the
        # distances, adding a few steps onto the end to allow for
        # neighboring sight lines to take different paths through the
        # cube.
        self.distLimPc = distMax + 5*self.distStepPc

        # Now we generate the "fine" and "coarse" distance arrays and
        # abut them together.
        distsClose = stilism_local.generate_distances(self.distLimPc, \
                                                      self.distMinPc, \
                                                      self.distStepPc)

        # we have to determine the coarse step size dynamically too.
        nBinsFar = self.nDistBins - np.size(distsClose)

        # What we do if we sent in too few bins to begin with needs
        # some thought... I think for the moment it's better to warn
        # and extend the footprint in this case. We use a conditional
        # so that we can put the warning in (rather than use np.min()
        # in the above line). We could put in a conditional for
        # whether we actually want to do this (rather than just
        # crashing), but for the moment let's ensure this actually
        # does run all the way through...
        if nBinsFar < 0:
            print("generateDistances WARN - nFine > nTotal. Extending the coarse array to 10 elements. This may not be what you want...")
            nBinsFar = 10
            
        # We want the arrays to mesh more or less seamlessly. Here's
        # how: we use linspace to take the maximum close distance out
        # to the maximum total distance, WITHOUT the endpoints. Then
        # we find the step resulting and shift the array by that
        # distance.
        distsFar = np.linspace(np.max(distsClose), self.distMaxCoarsePc, \
                               nBinsFar, endpoint=False)
        # Update the step size and shift the coarse array by one step
        self.distStepCoarsePc = distsFar[1] - distsFar[0]
        distsFar += self.distStepCoarsePc
        
        #distMinFar = np.max(distsClose)+self.distStepCoarsePc
        #distsFar = np.linspace(distMinFar, self.distMaxCoarsePc, nBinsFar, \
        #                       endpoint=True)

        self.distsPc = np.hstack(( distsClose, distsFar ))

        # Ensure the limits sent to stilism_local are consistent with
        # this. If we're sending stilism a distance array then those
        # values should be ignored anyway, but it doesn't hurt to make
        # them consistent.
        self.distMinPc = np.min(self.distsPc)
        self.distMaxPc = np.max(self.distsPc)
        self.distStepPc = (self.distMaxPc - self.distMinPc) \
                          / np.size(self.distsPc)
        
        if Verbose:
            nbins = np.size(self.distsPc)
            stepFine = distsClose[1] - distsClose[0]
            stepFar  = distsFar[1] - distsFar[0]
            print("generateDistances INFO - nbins %i, fine step %.3f, coarse step %.3f" % (nbins, stepFine, stepFar))
        
    def getLallementEBV(self):

        """Evaluates the Lallement+19 extinction"""

        # we supply the get_ebv_lallement routine with our array of
        # distances. If it's zero length, get_ebv_lallement will
        # generate its own. Otherwise it uses the values we
        # supply. This leads to an apparently redundant set of
        # keywords in the call.
        l19, dists, distLim \
            = self.lallementMap.get_ebv(self.l, self.b, \
                                              self.distMaxPc, \
                                              self.distMinPc, \
                                              self.distStepPc, \
                                              distances=self.distsPc)

        # Pass the l19 values, converted to E(B-V)
        ## new 2021-04-05: not needed since LallementDustMap handles conversion automatically
        #self.ebvL19 = l19 / self.Rv
        self.ebvL19 = l19
        
        # pass the distance array generated to the instance, IF it
        # wasn't already generated.
        if np.size(self.distsPc) < 1:
            self.distsPc = np.copy(dists)
            self.distLimPc = np.copy(distLim)

    def getBovyEBV(self):

        """Evaluates Bovy et al. E(B-V) for this sight line"""

        self.ebvBovy = self.objBovy(self.l, self.b, self.distsPc/1000.)

        # extinctions cannot be negative
        bLo = self.ebvBovy < 0.
        self.ebvBovy[bLo] = 0.
        
        
    def showLos(self, ax=None, alpha=1.0, lw=1, zorder=5, \
                noLabel=False, \
                showPoints=False):

        """Adds a plot for the line of sight to the current axis"""

        # start an axis if one was not supplied
        newAx = False
        if ax is None:
            fig1 = plt.figure(1)
            fig1.clf()
            ax = fig1.add_subplot(111)
            newAx = True

        # hack for the labels
        labl19 = 'L+19'
        lablBov = 'Bovy'
        if noLabel:
            labl19 = ''
            lablBov = ''

        # show the points?
        marker=None
        markerB=None
        if showPoints:
            marker='o'
            markerB='s'
            
        b19 = self.distsPc <= self.distLimPc
        dumLlo = ax.plot(self.distsPc[b19], self.ebvL19[b19], 'k-', \
                         label=labl19, \
                         alpha=alpha, lw=lw, zorder=zorder, \
                         marker=marker, ms=2)

        dumLhi = ax.plot(self.distsPc[~b19], self.ebvL19[~b19], 'k--', \
                         alpha=alpha, lw=lw, zorder=zorder, \
                         marker=marker, ms=1)

        dumBo = ax.plot(self.distsPc, self.ebvBovy, 'r-', \
                        label=lablBov, \
                        alpha=alpha, lw=lw, zorder=zorder+1, \
                        marker=markerB, ms=1)

        # if we are doing a new axis, decorate it
        if not newAx:
            return

        self.decorateAxes(ax)

    def showDistMax(self, ax=None):

        """Draw an indicator showing the maximum distance for L19"""

        if ax is None:
            return

        if self.distLimPc > self.distMaxPc:
            return

        blah = ax.axvline(self.distLimPc, ls='--', color='k', alpha=0.3)
        
        #ymax = np.max(self.ebvL19)
        #dum = ax.plot([self.distLimPc, self.distLimPc], [0., ymax], \
            #'k--', alpha=0.3)
            
    def decorateAxes(self, ax=None):

        """One-liner to decorate the current plot axes appropriately for the
extinction vs distance plot"""

        if ax is None:
            return
        
        ax.set_xlabel('Distance (pc)')
        ax.set_ylabel('E(B-V)')
        ax.grid(which='both', zorder=1, color='0.5', alpha=0.5)
        ax.set_title('l=%.2f, b=%.2f' % (self.l, self.b))
        
#### Test the comparison

def testOneSightline(l=0., b=4., Rv=3.1, useCoarse=False):

    """Try a single sight line"""

    # Import the bovy et al. map so we don't have to re-initialize it
    # for each sight-line
    combined19 = mwdust.Combined19()
    
    los = lineofsight(l, b, objBovy=combined19, Rv=Rv)

    if useCoarse:
        los.generateDistances(Verbose=True)
    los.getLallementEBV()
    los.getBovyEBV()

    # show the line of sight
    los.showLos(showPoints=True)

def hybridSightline(lCen=0., bCen=4., \
                    nl=5, nb=5, \
                    maxPc=9000., minPc=0.5, stepPc=25, \
                    nside=64, \
                    pixFillFac=1.0, collisionArcmin=2., \
                    pctUpper=75., pctLower=25., \
                    Rv=3.1, \
                    distFrac=1., diffRatioMin=0.5, \
                    setLimDynamically=True, \
                    minEBV=1.0e-3, \
                    minDistL19=1000., \
                    returnValues = False, \
                    tellTime=True, \
                    doPlots=True, \
                    figName='', \
                    useTwoBinnings=True, \
                    nBinsAllSightlines = 500, \
                    distancesPc = np.array([]), \
                    hpid=-1, nested=False, \
                    objBovy=None):

    """Samples the Bovy et al. and Lallement et al. 2019 E(B-V) vs
    distance maps, constructed as the median E(B-V) vs distance curve
    over nl x nb samples about the central sight line. Returns a
    hybrid E(B-V) vs distance curve as E(B-V), distances, if
    "returnValues" is set.

    A lightly modified version of Alessandro Mazzi's
    "stilism_local.py" is used to query Lallement et al. 2019.
    
    REQUIREMENTS beyond the standard numpy and matplotlib: 

    stilism_local.py: Currently, the script "stilism_local.py" must be
    accessible on PYTHONPATH (or be in the current working directory),
    and it must be able to locate the "stilism_cube_2.h5" file.

    mwdust - Bovy's 3D extinction models and sampler.

    healpy - must be present on the system (to convert NSIDE into a
    pixel area). If mwdust successfully installed on your system then
    you probably already have this.

    MORE INFO, ARGUMENTS:

    The median over all the samples is taken as the E(B-V) curve for
each of the two models. The Lallement et al. 2019 model is scaled to
match the Bovy et al. model at a transition distance. This transition
distance can be determined dynamically or set to a fixed fraction of
the maximum distance of validity of the Lallement et al. 2019
model.

    ARGUMENTS:

    lCen, bCen = central line of sight, in degrees.

    nl, nb = number of points in l, b about which to draw
    samples. (The samples will be drawn in a grid (nl x nb) about the
    central line of sight.)

    maxPc, minPc, stepPc = max, min, stepsize for the distance in
    parsecs along the line of sight. (minPc should be small but not
    zero: 0.5 pc seems a sensible level to use.)

    nside = Healpix NSIDE (used to estimate the side-length for the
    square region sampled)

    pixFillFrac = fraction of the side-length of the healpix to sample
    with our pointings (the default is to sample out to the corners of
    the pixel).

    collisionArcmin = closest distance a sample can fall to the line
    of sight without being rejected as a duplicate of the central line
    of sight.

    pctUpper, pctLower = lower and upper percentiles for displaying
    the variation of E(B-V) within the healpix. (May be ambiguous to
    interpret for small (nl x nb).)

    Rv = scale factor converting L19's A_555 to E(B-V). Default 3.1.

    distFrac = fraction of the L19 maximum distance to use as a
    default for the overlap point between L19 and Bovy.

    diffRatioMin = minimum fractional difference btween L19 and Bovy
    for the two predictions to be considered "discrepant". Used if
    estimating the overlap distance dynamically.

    setLimDynamically: setting the overlap distance dynamically?

    minEBV = minimum value for the Bovy extinction. Bovy points below
    this value are ignored.

    minDistL19 = minimum acceptable dynamically determined overlap
    distance. If the dynamically determined distance is less than this
    value, the default (distFrac x max(dist_L19) is used instead.

    tellTime = report the timing to screen

    doPlots = prepare plots?

    returnValues = return the extinction and distances?

    figName = filename for output figure file. If length < 3, no
    figure is saved to disk.

    useTwoBinnings: Uses finer distance bins for L19 than for Bovy et al., such that the total number of bins is the same for all sight lines.

    nBinsAllSightlines = number of bins total for the sightlines

    distancesPc = input array of distances in parsecs. If supplied, all the clever distance methods here are ignored in favor of the input distances.

    hpid: if >0, then a healpix ID is being supplied, and will
    override the choice of l, b. The field center is constructed from
    this healpix id.

    nested: if using hpids, is this with NESTED? Default is False
    because sims_maf seems to use RING by default.

    objBovy = bovy et al. dust object. Defaults to None and is
    re-initialized in this method. But, could be passed in here too to
    save time.

    EXAMPLE CALL:

    compareExtinctions.hybridSightline(0, 4, figName='test_l0b4_ebvCompare.png', nl=5, nb=5, tellTime=True)

    """

    # For our timing report
    t0 = time.time()
    
    # generate samples in l, b to sample a typical healpix
    pixSideDeg = hp.nside2resol(nside, arcmin=True) / 60.

    # how far to the edge of the pixel do we go in our samples?
    pixEdge = np.min([pixFillFac, 1.0])
    
    # now we generate the grid of samples
    dL = pixSideDeg * pixEdge * np.linspace(-1., 1., nl, endpoint=True)
    dB = pixSideDeg * pixEdge * np.linspace(-1., 1., nb, endpoint=True)

    # create meshgrid and ravel into 1D arrays
    ll, bb = np.meshgrid(dL, dB)
    
    # convert the field center into equatorial so that we can generate
    # the samples within the healpix
    if hpid < 0:
        cooGAL = SkyCoord(lCen*u.deg, bCen*u.deg, frame='galactic')
        raCen = cooGAL.icrs.ra.degree
        deCen = cooGAL.icrs.dec.degree
    else:
        raCen, deCen = hp.pix2ang(nside, hpid, nested, lonlat=True)
        cooEQ = SkyCoord(raCen*u.degree, deCen*u.degree, frame='icrs')
        lCen = cooEQ.galactic.l.degree
        bCen = cooEQ.galactic.b.degree
        
    vRA = ll.ravel() + raCen
    vDE = bb.ravel() + deCen

    # Ensure the coords of the samples actually are on the sphere...
    bSampl = (vDE >= -90.) & (vDE <= 90.)
    vRA = vRA[bSampl]
    vDE = vDE[bSampl]
    
    cooSamples = SkyCoord(vRA*u.deg, vDE*u.deg, frame='icrs')
    vL = np.asarray(cooSamples.galactic.l.degree)
    vB = np.asarray(cooSamples.galactic.b.degree)

    # handle the wraparound
    bLhi = vL > 180.
    vL[bLhi] -= 360.
    
    #vL = ll.ravel() + lCen
    #vB = bb.ravel() + bCen

    # knock out any points that are closer than distanceLim to the
    # central sight line
    offsets = (vL-lCen)**2 + (vB - bCen)**2
    bSamplesKeep = (offsets*3600. > collisionArcmin**2) & \
                   (vB >= -90.) & (vB <= 90.)

    if np.sum(bSamplesKeep) < 1:
        print("hybridSightline WATCHOUT - no samples kept. Check your line of sight coordinates are valid.")
        return
    
    vL = vL[bSamplesKeep]
    vB = vB[bSamplesKeep]

    # OK now we can proceed. First build the line of sight for the
    # center, then repeat for the nearby sight lines. If we already
    # initialized the bovy dust object somewhere else, we can pass it
    # in. If not initialized, then we initialize here.
    if objBovy is None:
        combined19 = mwdust.Combined19()
    else:
        combined19 = objBovy
        
    # for our timing report: how long did it take to get this far?
    t1 = time.time()
    
    # now build the line of sight
    losCen = lineofsight(lCen, bCen, maxPc, minPc, stepPc, \
                         objBovy=combined19, Rv=Rv, \
                         nDistBins=nBinsAllSightlines, \
                         distances=distancesPc)

    # If a distances array was not supplied, AND we want to use our
    # two-binning scheme to generate the distances, then generate the
    # distances.
    if useTwoBinnings and np.size(distancesPc) < 1:
        losCen.generateDistances(Verbose=tellTime)
    
    losCen.getLallementEBV()
    losCen.getBovyEBV()

    # Set up a figure...
    if doPlots:
        fig1 = plt.figure(1, figsize=(12,5))
        fig1.clf()
        fig1.subplots_adjust(wspace=0.3)

        # let's try using gridspec to customize our layout
        gs = fig1.add_gridspec(nrows=2, ncols=3)
        ax1 = fig1.add_subplot(gs[:,0:2])

        # ax1=fig1.add_subplot(121)
        
        losCen.showLos(ax=ax1, alpha=0.1, lw=2, zorder=10, noLabel=True)
        losCen.decorateAxes(ax1)
        losCen.showDistMax(ax1)
    
    # construct arrays for all the samples as a function of
    # distance. We'll do this vstack by vstack.
    stackDist = np.copy(losCen.distsPc) # to ensure they're all the same...
    stackL19 = np.copy(losCen.ebvL19)
    stackBovy = np.copy(losCen.ebvBovy)
    
    # now loop through the samples. We pass in the same distance array
    # as we used for the central line of sight, IF we are using our
    # two-binning scheme.
    for iSample in range(np.size(vL)):
        distsInput = np.copy(distancesPc) # use input distances if any
                                          # were given.
        if useTwoBinnings:
            distsInput = losCen.distsPc 
        losThis = lineofsight(vL[iSample], vB[iSample], \
                              maxPc, minPc, stepPc, \
                              objBovy=combined19, \
                              Rv=Rv, \
                              distances=distsInput)
        losThis.getLallementEBV()
        losThis.getBovyEBV()

        #if doPlots:
        #    losThis.showLos(ax=ax1, alpha=0.3, lw=1, zorder=3)

        # accumulate to the stacks so that we can find the statistics
        # across the samples
        stackDist = np.vstack(( stackDist, losThis.distsPc ))
        stackL19  = np.vstack(( stackL19,  losThis.ebvL19 ))
        stackBovy = np.vstack(( stackBovy, losThis.ebvBovy ))

    # now compute the statistics. We do the median and the upper and
    # lower percentiles.
    distsMed = np.median(stackDist, axis=0)
    ebvL19Med = np.median(stackL19, axis=0)    
    ebvBovyMed = np.median(stackBovy, axis=0)

    # find the scale factor for the Rv factor that causes L19 to line
    # up with Bovy et al. along the sight line, out to our desired
    # comparison distance.

    # We set a default comparison point: some fraction of the maximum
    # distance along this sight line for which we have the L+19 model.
    distCompare = losCen.distLimPc * distFrac

    # We can also try to set the decision distance dynamically. Here I
    # find all the distances for which the L+19 extinction is within
    # fraction "diffRatioMin" of the Bovy et al. extinction, and find
    # the maximum distance for which the two sets are this close. If
    # that distance is less than some cutoff ("minDistL19") then the
    # dynamically estimated max distance is discarded.
    if setLimDynamically:
        bNear = (distsMed <= losCen.distLimPc) & \
                (ebvL19Med > 0) & (ebvBovyMed > 0 ) & \
                (np.abs(ebvBovyMed / ebvL19Med - 1.0) < diffRatioMin)
        if np.sum(bNear) > 0:
            # what minimum distance satisfied this expression?
            distMinCalc = np.max(distsMed[bNear])

            # Only apply the revised limit if it is farther than our
            # desired minimum.
            if distMinCalc > minDistL19:
                distCompare = distMinCalc
            
            
    # now we set our scale factor based on comparison to Bovy. Some
    # regions of Bovy still produce zero E(B-V) for all distances, so
    # we set a minimum (if bovy AT THE COMPARISON POINT is below our
    # threshold minEBV, then we do no scaling).
    rvFactor = 1. # our default: no scaling.
    quadFactor = 1.
    iMaxL19 = np.argmin(np.abs(distsMed - distCompare))
    if ebvBovyMed[iMaxL19] > minEBV:
        rvFactor = ebvL19Med[iMaxL19] / ebvBovyMed[iMaxL19]

        # Also compute a factor for quadratic scaling if we want to
        # try that
        quadFactor = ebvBovyMed[iMaxL19] / ebvL19Med[iMaxL19]
        
    RvScaled = Rv * rvFactor

    ### Merge the two median curves. This will be our E(B-V) curve
    ### with distance.
    ebvHybrid = np.copy(ebvBovyMed)
    b19 = distsMed < distCompare
    ebvL19scaled = ebvL19Med/rvFactor

    # try quadratic scaling (note that the area plot later doesn't yet
    # know about this)
    # ebvL19scaled = quadFactor * ebvL19Med**2
    
    #ebvHybrid[b19] = ebvL19Med[b19]/rvFactor
    ebvHybrid[b19] = ebvL19scaled[b19]
    
    bBovBad = ebvHybrid < minEBV
    # ebvHybrid[bBovBad] = ebvL19Med[bBovBad]/rvFactor
    ebvHybrid[bBovBad] = ebvL19scaled[bBovBad]
    
    if tellTime:
        t2 = time.time()
        dtBovy = t1 - t0
        dtSample = t2 - t1
        dtTotal = t2 - t0
        
        print("TIMING: setup:%.2e s, querying:%.2e s, total:%.2e s" \
              % (dtBovy, dtSample, dtTotal))
    
    # if not plotting, return
    if not doPlots:
        if returnValues:
            return ebvHybrid, distsMed, 1.0
        else:
            return
        
    ## Now we compute the upper and lower levels for plotting. I am
    ## not certain if it's better to use percentiles or to use the
    ## standard deviation (there is a tradeoff when there are few
    ## samples) so both are computed for the moment.
    ebvL19Std = np.std(stackL19, axis=0)
    ebvL19Levs = np.percentile(stackL19, [pctLower, pctUpper],\
                                axis=0)
    
    ebvBovyStd = np.std(stackBovy, axis=0)
    ebvBovyLevs = np.percentile(stackBovy, [pctLower, pctUpper],\
                                axis=0)

    ### Now we plot the regions of coverage to the percentile limits,
    ### for the bovy and for the L+19 predictions.
    dumLevsL19 = ax1.fill_between(distsMed, ebvL19Levs[0], ebvL19Levs[1], \
                                  zorder=9, alpha=0.4, color='0.5')
    dumLevsBovy = ax1.fill_between(distsMed, ebvBovyLevs[0], ebvBovyLevs[1], \
                                  zorder=9, alpha=0.3, color='r')

    ### Show the median levels for Bovy and for L+19
    dumMedsL19  = ax1.plot(distsMed, ebvL19Med, color='k', ls='-.', \
                           zorder=20, lw=2, \
                           label=r'L19, R$_V$=%.2f' % (Rv))
    dumMedsBovy = ax1.plot(distsMed, ebvBovyMed, color='r', ls='--', \
                           zorder=21, lw=2, label='Bovy median')

    # Overplot the hybrid EBV curve
    dumHybrid = ax1.plot(distsMed, ebvHybrid, ls='-', color='c', lw=6, \
                         label='Hybrid E(B-V)', zorder=31, alpha=0.5)
    
    # show lallement et al. scaled up to bovy et al. at the transition
    coloScaled='b'
    dumScal = ax1.plot(distsMed[b19], ebvL19scaled[b19], \
                       color=coloScaled, \
                       lw=2, \
                       ls=':', \
                       label=r'L19, R$_{V}$=%.2f' % (RvScaled), \
                       zorder=35, alpha=0.75)
    dumLevsScal = ax1.fill_between(distsMed[b19], \
                                   ebvL19Levs[0][b19]/rvFactor, \
                                   ebvL19Levs[1][b19]/rvFactor, \
                                   color=coloScaled, \
                                   alpha=0.2, \
                                   zorder=34)
        
        #sAnno = "Green dashed: L19 w/ Rv=%.2f" % (RvScaled)
        #dum = ax1.annotate(sAnno, (0.95,0.05), xycoords='axes fraction', \
        #                   ha='right', va='bottom', color='g')

    # override the axis title:
    sTitle = '(lCen, bCen)=(%.2f, %.2f), NSIDE=%i. %i samples' % \
                  (lCen, bCen, nside, 1+len(vL))
    # add the levels information
    sTitle = '%s. Pct lower, upper = %.1f, %.1f' % (sTitle, pctLower, pctUpper)
    ax1.set_title(sTitle)

    # ok NOW we do the legend.
    leg = ax1.legend(loc=0, frameon=True, facecolor='w', framealpha=1.)

    # Now show these over the figure
    #dumAvgL19 = ax1.errorbar(distsMed, ebvL19Med, \
    #                         yerr=ebvL19Std, \
    #                         ls=None, ms=5, 
    #                         zorder=20)

    #dumAvgL19 = ax1.errorbar(distsMed, ebvBovyMed, \
    #                         yerr=ebvBovyStd, \
    #                         ls=None, ms=5, 
    #                         zorder=20)

    # Show a panel giving the sight lines looked at here. We will want
    # the maximum bovy extinctions for each (since that goes farther):
    maxBovy = stackBovy[1::,-1] # for our colors, not including the
                                # central los.
    
    # debug - what sight lines are we looking at here?
    #fig2 = plt.figure(2, figsize=(3,3))
    #fig2.clf()
    #ax2 = fig1.add_subplot(224)
    ax2 = fig1.add_subplot(gs[1,2])
    dumCen = ax2.plot(lCen, bCen, 'm*', ms=20, zorder=1)
    dumSamp = ax2.scatter(vL, vB, c=maxBovy, zorder=2, cmap='Greys', \
                          edgecolor='0.5', marker='s', s=25)
    cbar = fig1.colorbar(dumSamp, ax=ax2, label='E(B-V) (Bovy)')
    ax2.set_xlabel('l, degrees')
    ax2.set_ylabel('b, degrees')
    ax2.grid(which='both', zorder=1, color='0.5', alpha=0.5)
    ax2.set_title('sight-line samples about %.2f, %.2f' % (lCen, bCen), \
                  fontsize=9)
    # fig2.subplots_adjust(left=0.25, bottom=0.25)

    # save the figure to disk
    if len(figName) > 3:
        fig1.savefig(figName, overwrite=True)

    if returnValues:
        return ebvHybrid, distsMed, rvFactor

def loopSightlines(nside=64, imin=0, imax=25, \
                   nbins=300, nested=False, \
                   nl=5, nb=5, tellTime=False, \
                   reportInterval=100, \
                   fitsPath='', \
                   dirChunks='./ebvChunks', \
                   fracPix=1.):

    """Wrapper: samples the 3D extinction hybrid model for a range of
    healpixels

    nside = healpix nside
 
    imin, imax = first and last hpids to use 

    nbins = number of distance bins to use for each sightline

    nl, nb = number of samples to use around each sight line

    reportInterval = write do disk (and/or provide screen output)
    every this many healpix

    fitsPath = if >3 characters, the path to output fits file that
    overrides auto-generated output path

    dirChunks = if auto-generating the output path, the directory into
    which the file will go. Ignored if fewer than 4 characters.

    """

    # set up the healpix quantities
    npix = hp.nside2npix(nside)

    print("loopSightlines INFO: nside %i, npix %i, %.3e" \
          % (nside, npix, npix))
    
    # How far through this are we going to go?
    if imax < 0 or imax > npix:
        imax = npix

    # set imin appropriately
    if imin > imax:
        imin = np.max([imax - 25, 0])
        
        print("loopSightlines WARN - supplied imax > imin. Defaulted to %i, %i" % (imin, imax))
        
    # Number of sightlines
    nSightlines = imax - imin

    # let's construct a filename for this segment so we can keep track
    # of them later.
    if len(fitsPath) < 4:
        fitsChunk = 'ebv3d_nside%i_hp%i_%i.fits' % (nside, imin, imax)
        if len(dirChunks) > 3:
            fitsPath = '%s/%s' % (dirChunks, fitsChunk)
            if not os.access(dirChunks, os.R_OK):
                dirChunks = os.makedirs(dirChunks)
        else:
            fitsPath = fitsChunk[:]
                
    # set up distance and E(B-V) arrays for only the ones we will be
    # running. We also store the healpix IDs so that we could do this
    # in pieces and then stitch them together later.
    shp = (nSightlines, nbins)

    # set up the arrays we'll be using
    hpids = np.arange(imin, imax)
    dists = np.zeros(shp)
    ebvs  = np.zeros(shp)

    # Let's keep track of the scale factor we used to merge L19 with
    # Bovy et al:
    sfacs = np.ones(nSightlines)

    # Set up header information for the inevitable serialization. I
    # think astropy has a nice way to do this, for the moment we can
    # build one with a dictionary.
    dMeta = {'nside':nside, 'nested':nested, \
             'hpmin':imin, 'hpmax':imax, \
             'nbins':nbins, 'nl':nl, 'nb':nb, \
             'fracPix':fracPix}

    # For reporting the sightlines to terminal
    tStart = time.time()
    
    # OK now loop through this. We don't want to have to redo the bovy
    # initialization for each sight line, so let's initialize it here.
    combined19 = mwdust.Combined19()
    
    for iHP in range(np.size(hpids)):    
        ebvsThis, distsThis, rvFactor  \
            = hybridSightline(0., 0., \
                              nl=nl, nb=nb, \
                              setLimDynamically=False, \
                              useTwoBinnings=True, \
                              nBinsAllSightlines=nbins, \
                              Rv=3.1, \
                              pixFillFac=fracPix, \
                              nested=nested, \
                              nside=nside, \
                              objBovy=combined19, \
                              doPlots=False, \
                              tellTime=tellTime, \
                              returnValues=True, \
                              hpid=hpids[iHP])

        # now put the results into the master arrays by row number
        # (which is why we loop through the length of the hp array and
        # not the hpids themselves):
        dists[iHP] = distsThis
        ebvs[iHP] = ebvsThis
        sfacs[iHP] = rvFactor

        # Write to disk every so often
        if iHP >= reportInterval and iHP % reportInterval < 1:
            writeExtmap(hpids, dists, ebvs, sfacs, \
                        dMeta=dMeta, \
                        fitsPath=fitsPath)

            print("loopSightlines INFO: %i of %i: hpid %i: %.2e s" \
                  % (iHP, nSightlines, hpids[iHP], time.time()-tStart))
            
    # use our method to write to disk
    writeExtmap(hpids, dists, ebvs, sfacs, dMeta, fitsPath)
    
def writeExtmap(hpids=np.array([]), dists=np.array([]), \
                ebvs=np.array([]), sfacs=np.array([]), \
                masks=np.array([]), \
                dMeta={}, header=None, fitsPath='test.fits'):

    """Writes extinction map segment to fits. HDUs are, in this order:

    hpids, distance bins, E(B-V)s, scale factors = data arrays to write

    masks = optional boolean mask array

    dMeta = dictionary of metadata keywords to pass

    header = template header to send to the primary HDU

    fitsPath = filename for output file"""

    if np.size(hpids) < 1:
        return

    # Generate primary header, accepting template header if given
    hdu0 = fits.PrimaryHDU(hpids, header=header)
    for sKey in dMeta.keys():
        hdu0.header[sKey] = dMeta[sKey]

    # ... then the secondary arrays, which we will serialize as image hdus:
    hdul = fits.HDUList([hdu0])

    # now we append them
    for thisArr in [dists, ebvs, sfacs, masks]:

        hdul.append(fits.ImageHDU(thisArr))
    
    hdul.writeto(fitsPath, overwrite=True)

    # close the hdulist
    hdul.close()

def mergeMaps(sSrch='ebv3d_nside64_*fits', \
              pathJoined='merged_ebv3d_nside64.fits'):

    """Given partial healpix maps, merge them into a single all-sky hp
map. A list of paths matching the search string is constructed, and
the all-sky map constructed by slotting in the populated rows from the
individual files.

    """

    lPaths = glob.glob(sSrch)
    if len(lPaths) < 1:
        print("mergeMaps WARN - no paths match string %s" % (sSrch))
        return

    # ensure the output file doesn't overwrite any of the input files
    if len(pathJoined) < 4:
        pathJoined = 'test_mergedmaps.fits'

    # if the joined path is in the path of files, remove it from the
    # list to consider and prepend "tmp_" to the output path. This
    # should guard against any overwriting of input files.
    if pathJoined in lPaths:
        print("mergeMaps INFO - output path %s already in input path list. Removing from input path list and using a different output path." % (pathJoined))
        lPaths.remove(pathJoined)
        pathJoined = 'tmp_%s' % (os.path.split(pathJoined)[-1])
        
    # read the healpix info from the header of the first file in the
    # list. For the moment we trust the header rather than
    # constructing this information from the input data.
    hdr0 = fits.getheader(lPaths[0])

    try:
        nested = hdr0['NESTED']
        nside = hdr0['NSIDE']
        nbins = hdr0['NBINS']
    except:
        print("mergeMaps WARN - problem reading header keywords from %s" \
              % (lPaths[0]))
        return
        
    # Now we construct our master arrays.
    npix = hp.nside2npix(nside)

    # hpid, distance, ebvs, and a mask array. The mask array follows
    # np.masked convention that the mask is FALSE for GOOD points.
    hpidsMaster = np.arange(npix)
    distsMaster = np.zeros((npix, nbins))
    ebvsMaster = np.zeros((npix, nbins))
    sfacsMaster = np.zeros((npix))
    maskMaster = np.ones((npix, nbins), dtype='uint')

    # OK now we slot in the various pieces
    for path in lPaths:
        hdul = fits.open(path)
        rowsThis = hdul[0].data

        distsMaster[rowsThis] = hdul[1].data
        ebvsMaster[rowsThis] = hdul[2].data
        sfacsMaster[rowsThis] = hdul[3].data

        # This is a little clunky, since we're allowing for the
        # possibility that the input data might or might not have mask
        # data written, and that mask data may or may not be zero
        # sized.
        hasMask = False
        if len(hdul) > 4:
            if np.size(hdul[4].data) > 0:
                maskMaster[rowsThis] = hdul[4].data
                hasMask = True

        if not hasMask:
            maskMaster[rowsThis, :] = 0
            
        # Close the hdulist before moving on
        hdul.close()

    # now we have our combined arrays and template header. Write them!
    writeExtmap(hpidsMaster, distsMaster, ebvsMaster, sfacsMaster, \
                maskMaster, \
                header=hdr0, \
                fitsPath=pathJoined)
