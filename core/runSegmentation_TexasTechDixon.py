import os
import time

import cv2
import nrrd
import scipy.io
import scipy.ndimage.morphology
import skimage.draw
import skimage.measure
import skimage.morphology
import skimage.segmentation

from core.biasCorrection import correctBias
from util import constants
from util.util import *


# Get resulting path for debug files
def getDebugPath(path):
    return os.path.join(constants.pathDir, 'debug', path)


# Get resulting path for files
def getPath(path):
    return os.path.join(constants.pathDir, path)


# noinspection PyUnusedLocal
def segmentAbdomenSlice(slice, fatImageMask, waterImageMask, bodyMask):
    # Fill holes in the fat image mask and invert it to get the background of fat image
    # OR the fat background mask and fat image mask and take NOT of mask to get the fat void mask
    fatBackgroundMask = np.logical_not(scipy.ndimage.morphology.binary_fill_holes(fatImageMask))
    fatVoidMask = np.logical_or(fatBackgroundMask, fatImageMask)
    fatVoidMask = np.logical_not(fatVoidMask)

    # Next, remove small objects based on their area
    # Size is the area threshold of objects to use. This number of pixels must be set in an object for it to stay.
    # remove_small_objects is more desirable than using a simple binary_opening operation in this case because
    # binary_opening with a 5x5 disk SE was removing long, skinny objects that were not wide enough to pass the test.
    # However, their area is larger than smaller objects that I need to remove. So remove_small_objects is better since
    # it utilizes area. Odd issue where a warning will appear saying that a boolean image should be given. This is a
    # bug in skimage because I traced it down and the label function is returning odd values
    fatVoidMask = skimage.morphology.remove_small_objects(fatVoidMask, constants.thresholdAbdominalFatVoidsArea)

    # Use active contours to get the abdominal mask
    # Originally, I attempted this using the convex hull but I was not a huge fan of the results since there were
    # instances where the outline was concave and not convex
    # For active contours, we need an initial contour. We will start with an outline of the body mask
    # Find contours of body mask
    image, contours, hierarchy = cv2.findContours(bodyMask.astype(np.uint8), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    # Sort the contours by area and select the one with largest area, this will be the body mask contour
    sortedContourArea = np.array([cv2.contourArea(contour) for contour in contours])
    index = np.argmax(sortedContourArea)
    initialContour = contours[index]
    initialContour = initialContour.reshape(initialContour.shape[::2])

    # Perform active contour snake algorithm to get outline of the abdominal mask
    snakeContour = skimage.segmentation.active_contour(fatVoidMask.astype(np.uint8) * 255, initialContour, alpha=0.70,
                                                       beta=0.01, gamma=0.1, max_iterations=2500, max_px_move=1.0,
                                                       w_line=0.0, w_edge=1.0, convergence=0.1)

    # Draw snake contour on abdominalMask variable
    # Two options, polygon fills in the area and polygon_perimeter only draws the perimeter
    # Perimeter is good for testing while polygon is the general use one
    abdominalMask = np.zeros(fatVoidMask.shape, np.uint8)
    rr, cc = skimage.draw.polygon(snakeContour[:, 0], snakeContour[:, 1])
    # rr, cc = skimage.draw.polygon_perimeter(snakeContour[:, 0], snakeContour[:, 1])
    abdominalMask[cc, rr] = 1

    # SCAT is all fat outside the abdominal mask
    # VAT is all fat inside the abdominal mask
    SCAT = np.logical_and(np.logical_not(abdominalMask), fatImageMask)
    VAT = np.logical_and(abdominalMask, fatImageMask)

    # Remove objects from SCAT where the area is less than given constant
    SCAT = skimage.morphology.remove_small_objects(SCAT, constants.minSCATObjectArea)

    # Remove objects from VAT where the area is less than given constant
    VAT = skimage.morphology.remove_small_objects(VAT, constants.minVATObjectArea)

    return fatVoidMask, abdominalMask, SCAT, VAT


def segmentThoracicSlice(slice, fatImageMask, waterImageMask, bodyMask, CATAxial, CATPosterior, CATAnterior,
                         CATInferior, CATSuperior):
    # Fill holes in the fat image mask and invert it to get the background of fat image
    # OR the fat background mask and fat image mask and take NOT of mask to get the fat void mask
    fatBackgroundMask = np.logical_not(scipy.ndimage.morphology.binary_fill_holes(fatImageMask))
    fatVoidMask = np.logical_or(fatBackgroundMask, fatImageMask)
    fatVoidMask = np.logical_not(fatVoidMask)

    # Next, remove small objects based on their area
    # Size is the area threshold of objects to use. This number of pixels must be set in an object for it to stay.
    # remove_small_objects is more desirable than using a simple binary_opening operation in this case because
    # binary_opening with a 5x5 disk SE was removing long, skinny objects that were not wide enough to pass the test.
    # However, their area is larger than smaller objects that I need to remove. So remove_small_objects is better since
    # it utilizes area.
    # Odd issue where a warning will appear saying that a boolean image should be given. This is a bug in skimage
    # because I traced it down and the label function is returning odd values
    fatVoidMask = skimage.morphology.remove_small_objects(fatVoidMask, constants.thresholdThoracicFatVoidsArea)

    # Use active contours to get the abdominal mask
    # Originally, I attempted this using the convex hull but I was not a huge fan of the results since there were
    # instances where the outline was concave and not convex
    # For active contours, we need an initial contour. We will start with an outline of the body mask
    # Find contours of body mask
    image, contours, hierarchy = cv2.findContours(bodyMask.astype(np.uint8), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    # Sort the contours by area and select the one with largest area, this will be the body mask contour
    sortedContourArea = np.array([cv2.contourArea(contour) for contour in contours])
    index = np.argmax(sortedContourArea)
    initialContour = contours[index]
    initialContour = initialContour.reshape(initialContour.shape[::2])

    # Perform active contour snake algorithm to get outline of the abdominal mask
    snakeContour = skimage.segmentation.active_contour(fatVoidMask.astype(np.uint8) * 255, initialContour, alpha=0.70,
                                                       beta=0.01, gamma=0.1, max_iterations=2500, max_px_move=1.0,
                                                       w_line=0.0, w_edge=5.0, convergence=0.1)

    # Draw snake contour on abdominalMask variable
    # Two options, polygon fills in the area and polygon_perimeter only draws the perimeter
    # Perimeter is good for testing while polygon is the general use one
    thoracicMask = np.zeros(fatVoidMask.shape, np.uint8)
    rr, cc = skimage.draw.polygon(snakeContour[:, 0], snakeContour[:, 1])
    # rr, cc = skimage.draw.polygon_perimeter(snakeContour[:, 0], snakeContour[:, 1])
    thoracicMask[cc, rr] = 1

    # Lungs are defined as being within body and not containing any fat or water content
    # lungMask = bodyMask & ~fatImageMask & ~waterImageMask
    # Next, remove any small objects from the binary image since the lungs will be large
    # Fill any small holes within the lungs to get the full lungs
    lungMask = np.logical_and(np.logical_and(bodyMask, np.logical_not(fatImageMask)), np.logical_not(waterImageMask))
    lungMask = skimage.morphology.binary_opening(lungMask, skimage.morphology.disk(10))
    lungMask = scipy.ndimage.morphology.binary_fill_holes(lungMask)

    # SCAT is all fat outside the thoracic mask
    # ITAT is all fat inside the thoracic mask
    SCAT = np.logical_and(np.logical_not(thoracicMask), fatImageMask)
    ITAT = np.logical_and(thoracicMask, fatImageMask)
    CAT = np.zeros_like(ITAT, dtype=bool)

    # Remove objects from SCAT where the area is less than given constant
    SCAT = skimage.morphology.remove_small_objects(SCAT, constants.minSCATObjectArea)

    if CATInferior <= slice <= CATSuperior:
        posterior = int(np.round(np.interp(slice, CATAxial, CATPosterior)))
        anterior = int(np.round(np.interp(slice, CATAxial, CATAnterior)))

        # Label the objects of lung mask. There should only be two objects, the left and right lung
        # Get centroid of each object. Left lung is on left side, so centroid should be below half of total coronal
        # plane size
        lungMaskLabels = skimage.morphology.label(lungMask)
        lungProps = skimage.measure.regionprops(lungMaskLabels, cache=True)

        # Sort lung objects based on area descending, first two largest objects are the left/right lung
        sortedAreaIndices = sorted(range(len(lungProps)), key=lambda x: lungProps[x].area, reverse=True)

        # Next, sort the two lungs based on their sagittal centroid coordinate
        # Smaller sagittal centroid coordinate is the left lung, other is right lung
        # Label ID is the regionprop index + 1
        sortedCentroidIndices = sorted(sortedAreaIndices[0:2], key=lambda x: lungProps[x].centroid[0])
        leftLung = (lungMaskLabels == sortedCentroidIndices[0] + 1)
        rightLung = (lungMaskLabels == sortedCentroidIndices[1] + 1)

        # For the left and right lung, retrieve the outer contour index on a row-by-row basis.
        # Left lung will be lower index and right-lung will be upper index for ROI of CAT
        leftIndices = maxargwhere(leftLung, axis=1)
        rightIndices = minargwhere(rightLung, axis=1)

        # Only extract the relevant indices from posterior to anterior slices
        # Any -1 values indicate there was no lung mask located there, so set it to the minimum index value
        leftIndices = leftIndices[posterior:anterior]
        rightIndices = rightIndices[posterior:anterior]

        leftIndices[leftIndices == -1] = defaultmin(leftIndices[leftIndices != -1], 0)
        rightIndices[rightIndices == -1] = rightIndices.max()

        # Create CATMask which is a mask of where fat can be located around the heart
        # From coronal plane, the upper and lower bounds are determined from user entered points
        # From sagittal plane, this is calculated based on the lungs going around the heart
        CATMask = np.zeros_like(ITAT, dtype=bool)
        for heartSlice, leftIndex, rightIndex in zip(range(posterior, anterior), leftIndices, rightIndices):
            CATMask[heartSlice, leftIndex:rightIndex] = True

        # CAT is defined as ITAT inside the CATMask
        CAT[CATMask] = ITAT[CATMask]

        # Remove objects from CAT where the area is less than given constant
        CAT = skimage.morphology.remove_small_objects(CAT, constants.minCATObjectArea)

    return fatVoidMask, thoracicMask, lungMask, SCAT, ITAT, CAT


# Segment depots of adipose tissue given Dixon MRI images
def runSegmentation(data):
    # Get the data from the data tuple
    fatImage, waterImage, config = data

    # Create debug directory regardless of whether debug constant is true
    # The bias corrected fat and water images are going to be created in this directory regardless of debug constant
    os.makedirs(getDebugPath(''), exist_ok=True)

    # Load values from config dictionary
    diaphragmAxial = config['diaphragmAxial']
    umbilicis = config['umbilicis']
    umbilicisInferior = umbilicis['inferior']
    umbilicisSuperior = umbilicis['superior']
    umbilicisLeft = umbilicis['left']
    umbilicisRight = umbilicis['right']
    umbilicisCoronal = umbilicis['coronal']

    CATBounds = list([(x['axial'], x['posterior'], x['anterior']) for x in config['CATBounds']])
    CATAxial = list([x[0] for x in CATBounds])
    CATPosterior = list([x[1] for x in CATBounds])
    CATAnterior = list([x[2] for x in CATBounds])

    # Convert three arrays to NumPy and get minimum/maximum axial slice
    # The min/max axial slice is used to determine the start and stopping point
    # of calculating CAT
    CATAxial = np.array(CATAxial)
    CATPosterior = np.array(CATPosterior)
    CATAnterior = np.array(CATAnterior)
    CATInferior = CATAxial.min()
    CATSuperior = CATAxial.max()

    # Sort the three arrays based on CAT axial, ascending
    CATAxialSortedInds = CATAxial.argsort()
    CATAxial = CATAxial[CATAxialSortedInds]
    CATPosterior = CATPosterior[CATAxialSortedInds]
    CATAnterior = CATAnterior[CATAxialSortedInds]

    # Perform bias correction on MRI images to remove inhomogeneity
    # If bias correction has been performed already, then load the saved data
    tic = time.perf_counter()
    if not constants.forceBiasCorrection and os.path.exists(getPath('fatImage.nrrd')) and os.path.exists(
            getPath('waterImage.nrrd')):
        fatImage, header = nrrd.read(getPath('fatImage.nrrd'))
        waterImage, header = nrrd.read(getPath('waterImage.nrrd'))

        # Transpose image to get back into C-order indexing
        fatImage, waterImage = fatImage.T, waterImage.T
    else:
        fatImage = correctBias(fatImage, shrinkFactor=constants.shrinkFactor, prefix='fatImageBiasCorrection')
        waterImage = correctBias(waterImage, shrinkFactor=constants.shrinkFactor, prefix='waterImageBiasCorrection')

        # If bias correction is performed, saved images to speed up algorithm in future runs
        nrrd.write(getPath('fatImage.nrrd'), fatImage.T, constants.nrrdHeaderDict)
        nrrd.write(getPath('waterImage.nrrd'), waterImage.T, constants.nrrdHeaderDict)

    toc = time.perf_counter()
    print('N4ITK bias field correction took %f seconds' % (toc - tic))

    # Create empty arrays that will contain slice-by-slice intermediate images when processing the images
    # These are used to print the entire 3D volume out for debugging afterwards
    fatImageMasks = np.zeros(fatImage.shape, bool)
    waterImageMasks = np.zeros(fatImage.shape, bool)
    bodyMasks = np.zeros(fatImage.shape, bool)
    fatVoidMasks = np.zeros(fatImage.shape, bool)
    abdominalMasks = np.zeros(fatImage.shape, bool)
    thoracicMasks = np.zeros(fatImage.shape, bool)
    lungMasks = np.zeros(fatImage.shape, bool)

    # Final 3D volume results
    SCAT = np.zeros(fatImage.shape, bool)
    VAT = np.zeros(fatImage.shape, bool)
    ITAT = np.zeros(fatImage.shape, bool)
    CAT = np.zeros(fatImage.shape, bool)

    for slice in range(0, fatImage.shape[0]):
        # for slice in range(diaphragmSuperiorSlice, fatImage.shape[0]):
        tic = time.perf_counter()

        fatImageSlice = fatImage[slice, :, :]
        waterImageSlice = waterImage[slice, :, :]

        # Segment fat/water images using K-means
        # labelOrder contains the labels sorted from smallest intensity to greatest
        # Since our k = 2, we want the higher intensity label at index 1
        labelOrder, centroids, fatImageLabels = kmeans(fatImageSlice, constants.kMeanClusters)
        fatImageMask = (fatImageLabels == labelOrder[1])
        labelOrder, centroids, waterImageLabels = kmeans(waterImageSlice, constants.kMeanClusters)
        waterImageMask = (waterImageLabels == labelOrder[1])

        # Algorithm assumes that the skin is a closed contour and fully connects
        # This is a valid assumption but near the umbilicis, there is a discontinuity
        # so this draws a line near there to create a closed contour
        if umbilicisInferior <= slice <= umbilicisSuperior:
            fatImageMask[umbilicisCoronal, umbilicisLeft:umbilicisRight] = True

        # Save fat and water masks for debugging
        fatImageMasks[slice, :, :] = fatImageMask
        waterImageMasks[slice, :, :] = waterImageMask

        # Get body mask by combining fat and water masks
        # Apply some closing to the image mask to connect any small gaps (such as at umbilical cord)
        # Fill all holes which will create a solid body mask
        # Remove small objects that are artifacts from segmentation
        bodyMask = np.logical_or(fatImageMask, waterImageMask)
        bodyMask = skimage.morphology.binary_closing(bodyMask, skimage.morphology.disk(3))
        bodyMask = scipy.ndimage.morphology.binary_fill_holes(bodyMask)
        bodyMasks[slice, :, :] = bodyMask

        # Superior of diaphragm is divider between thoracic and abdominal region
        if slice < diaphragmAxial:
            fatVoidMask, abdominalMask, SCATSlice, VATSlice = \
                segmentAbdomenSlice(slice, fatImageMask, waterImageMask, bodyMask)

            # Save some data for debugging
            fatVoidMasks[slice, :, :] = fatVoidMask
            abdominalMasks[slice, :, :] = abdominalMask
            SCAT[slice, :, :] = SCATSlice
            VAT[slice, :, :] = VATSlice
        else:
            fatVoidMask, thoracicMask, lungMask, SCATSlice, ITATSlice, CATSlice = \
                segmentThoracicSlice(slice, fatImageMask, waterImageMask, bodyMask, CATAxial, CATPosterior, CATAnterior,
                                     CATInferior, CATSuperior)

            # Save some data for debugging
            fatVoidMasks[slice, :, :] = fatVoidMask
            thoracicMasks[slice, :, :] = thoracicMask
            lungMasks[slice, :, :] = lungMask
            SCAT[slice, :, :] = SCATSlice
            ITAT[slice, :, :] = ITATSlice
            CAT[slice, :, :] = CATSlice

        toc = time.perf_counter()
        print('Completed slice %i in %f seconds' % (slice, toc - tic))

    # Write out debug variables
    # Note: All Numpy arrays are transposed before being written to NRRD file because the Numpy arrays are in C-order
    # whereas the NRRD specification says that the arrays should be in Fortran-order.
    # C-order means that you index the array as (z, y, x) where the first index is the slowest varying and the last
    # index is fastest varying. Fortran-order, on the other hand is the direct opposite, where you index it as
    # (x, y, z) with the first axis being the fastest varying and the last axis being the slowest varying.
    # There are different benefits to each method and it's primarily a standard that programming languages pick. MATLAB
    # & Fortran use Fortarn-ordered, while C and Python and other languages use C-order. C-order is used now because it
    # is what is primarily used by many Python libraries, including Numpy.
    if constants.debug:
        nrrd.write(getDebugPath('fatImageMask.nrrd'), skimage.img_as_ubyte(fatImageMasks).T, constants.nrrdHeaderDict)
        nrrd.write(getDebugPath('waterImageMask.nrrd'), skimage.img_as_ubyte(waterImageMasks).T,
                   constants.nrrdHeaderDict)
        nrrd.write(getDebugPath('bodyMask.nrrd'), skimage.img_as_ubyte(bodyMasks).T, constants.nrrdHeaderDict)

        nrrd.write(getDebugPath('fatVoidMask.nrrd'), skimage.img_as_ubyte(fatVoidMasks).T, constants.nrrdHeaderDict)
        nrrd.write(getDebugPath('abdominalMask.nrrd'), skimage.img_as_ubyte(abdominalMasks).T, constants.nrrdHeaderDict)

        nrrd.write(getDebugPath('lungMask.nrrd'), skimage.img_as_ubyte(lungMasks).T, constants.nrrdHeaderDict)
        nrrd.write(getDebugPath('thoracicMask.nrrd'), skimage.img_as_ubyte(thoracicMasks).T, constants.nrrdHeaderDict)

    # Save the results of adipose tissue segmentation
    nrrd.write(getPath('SCAT.nrrd'), skimage.img_as_ubyte(SCAT).T, constants.nrrdHeaderDict)
    nrrd.write(getPath('VAT.nrrd'), skimage.img_as_ubyte(VAT).T, constants.nrrdHeaderDict)
    nrrd.write(getPath('ITAT.nrrd'), skimage.img_as_ubyte(ITAT).T, constants.nrrdHeaderDict)
    nrrd.write(getPath('CAT.nrrd'), skimage.img_as_ubyte(CAT).T, constants.nrrdHeaderDict)

    # If desired, save the results in MATLAB
    if constants.saveMat:
        scipy.io.savemat(getPath('results.mat'), mdict={'SCAT': SCAT.T, 'VAT': VAT.T, 'ITAT': ITAT.T, 'CAT': CAT.T})
