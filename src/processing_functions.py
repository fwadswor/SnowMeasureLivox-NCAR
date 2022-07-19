# -*- coding: utf-8 -*-
"""
Created on Mon Jun 27 15:27:10 2022

@author: Fletcher Wadsworth
@email: wadsworthfletcher@gmail.com
"""

# Module containing point cloud processing functions. Functions are called in 
# pointcloudprocessor.py. Parameters for arguments are found in processing_config.ini.
# At the moment, the JIT compilation given by Numba is not implemented due to some Numpy
# functionality which is not supported. Thorough testing has not been done as to whether 
# the JIT compilation is faster with these routines.

# Written by Fletcher Wadsworth for NCAR|UCAR, found at:
#     https://github.com/fwadswor/SnowMeasureLivox-NCAR
    
# &&&&&&&&&&&&
# Need to put NCAR license/info/whatever else here
# &&&&&&&&&&&&

#Import libraries
#from numba import jit
import numpy as np
#import math



#Function to approximate average ground elevation in 10 cm bins
#@jit
def GroundVolumeMeasure(datapoints, ground_truth_elevations, save_above_ground, bin_size,
                        min_thresh, max_distance_enable, max_x, max_y):
    """

    
    Parameters
    ----------
        datapoints : numpy array of dtype float32
            point cloud data of shape (# points, 3) containing x,y,z coords
        ground_truth_elevations : numpy array of dtype float32
            array containing elevation in control conditions (no snow)
        save_above_ground : bool
            flag commanding function whether to save record point
        max_dist : int 
            denotes side length of square area in meters
        bin_size : float
            denotes side length of bin size in meters
            note: bin_size should be < 0 for 
        min_thresh : float
            denotes max distance above minimum height for point to be considered in average
        max_distance_enable : bool
            indicates to use config. params. for max distances along each axis
        max_x : int
            all points with x coord. > max_x are pruned from data array
        max_y : int
            all points with y coord. > max_y are pruned from data array
            
    
    Returns
    -------
        avg_height: np array of max_bins/bin_size square containing mean of heights
                    within tolerance of minimum height of point in that bin
                    
    Notes
    -----
        1 : origin is at the sensor, implying negative y and z coordinates.
        2 : a coordinate transform may be required for visualization
    """
    
    
    #Determine whether to use provided max distance parameters or max distances from data
    if max_distance_enable:
        #Prune points greater than distance thresholds from data array
        #x values are strictly positive
        good_vals = datapoints[:,0] < max_x
        datapoints = datapoints[good_vals]
        #origin is at center of y-z plane, 
        good_vals = datapoints[:,1] < max_y /2
        datapoints = datapoints[good_vals]
        good_vals = datapoints[:,1] > -max_y/2 
        datapoints = datapoints[good_vals]
    else:
        max_x = np.max(datapoints[:,0])
        max_y = np.max(datapoints[:,1])
        
#     #Coordinate transform to make origin at corner of x-y area for indexing
    datapoints[:,1] += max_y/2 #now minimum y coord. value = 0
#    max_y += max_y/2
    
    point_count = datapoints.shape[0]
    print("Max X: ",max_x," Max Y: ",max_y)
    print("Bin Size: ",bin_size)
    #Preallocate arrays
    #Calculate number of square bins in area along both axes
    num_bins_x = int(max_x/bin_size)
    num_bins_y = int(max_y/bin_size)
    
    #Init. array of zeros for sum of height values
    sum_z = np.zeros((num_bins_x,num_bins_y),dtype='float32')
    
    #Array of minimum heights in each bin, preset to large number
    min_z = np.full((num_bins_x,num_bins_y), 10000)
    
    #Init. array of zeros for count of considered points in each bin
    count_z = np.zeros((num_bins_x,num_bins_y),dtype='int32')
    
    #If flag, initialize mask for indices corresponding to points above ground threshold
    if save_above_ground:
        above_ground_mask = np.zeros(point_count, dtype='bool')
        
    #Compute bin indices for each point
    x_bin = np.floor(datapoints[:,0]/bin_size).astype(int)
    y_bin = np.floor(datapoints[:,1]/bin_size).astype(int)
    #First pass: find min height of cloud points in each bin
    print("starting find min")
    for p1 in range(point_count):
        
        #x_bin = np.floor(datapoints[p1,0]/bin_size)
        #y_bin = np.floor(datapoints[p1,1]/bin_size)
        #replace current min with new point if less than
        min_z[x_bin[p1],y_bin[p1]] = min(min_z[x_bin[p1],y_bin[p1]], datapoints[p1,2])
        
    #Second pass: if each point is within tolerance of min, 
    #add height to sum and add 1 to count
    print("Ending find min, starting averaging")
    for p2 in range(point_count):
        #Indices of which bin each point belongs to (*10 so that indexing and 
        # bin size in cm are equal)
        #x_bin = math.floor(datapoints[p2,0]/bin_size-1)
        #y_bin = math.floor(datapoints[p2,1]/bin_size-1)
        #Check height w.r.t bin minimum and threshold
        if datapoints[p2,2] <= (min_z[x_bin[p1],y_bin[p1]] + min_thresh):
            count_z[x_bin[p1],y_bin[p1]] += 1
            sum_z[x_bin[p1],y_bin[p1]] += datapoints[p2,2]
            
        elif save_above_ground:
            above_ground_mask[p2] = True
    print("Computing results")
    #elementwise division between bin sum and bin count arrays for 
    #arithmetic mean per bin
    avg_height = np.divide(sum_z,count_z)
    #Replace NaN values from x/0 with 0
    #Note: np.nan_to_num is not supported by Numba, must do manually
    shape = avg_height.shape
    avg_height = avg_height.ravel()
    avg_height[np.isnan(avg_height)] = 0
    avg_height = avg_height.reshape(shape)
    #Subtract ground elevation to get snowpack height estimate
    avg_elevations = avg_height - ground_truth_elevations
    
    #Create value/array for points above ground threshold
    if not save_above_ground:
        air_points = 0 #Dummy value, if flag is not set then data will not be saved
    else:
        print(datapoints.shape)
        print(above_ground_mask.shape)
        air_points = datapoints[above_ground_mask,:]
    
    return avg_elevations, air_points


def Binning3D(data, binSizes, useDistanceParams, maxDistances):
    """
    Returns a 3D numpy array representing the density of point cloud points in
    bins over a defined 3D volume. Can be conceptualized as a 3D histogram.
    Parameters are set in processing_config.ini called from pointcloudprocessor.py
    
    Parameters
    ----------
        data : numpy array of dtype float32
            point cloud data of shape (# points, 3) containing x,y,z coords
        binSizes : tuple of floats
            contains desired approximate bin size in x,y,z directions in meters
        useDistanceParams : tuple of Booleans 
            designates whether to use distances in processing_config.ini as maximum
            distances under consideration or whether to consider the entire range of points
        bin_size : tuple of floats
            set max distance in each direction under consideration for density
        
            
    
    Returns
    -------
        hist3d: np.array containing point counts in each bin. See documentation for
        np.histogramdd for more information
    """
    #find max value of each coordinate (x,y,z) in data array
    max_values_data = np.max(data, axis=0)
    #print("Max values from data: ",max_values_data)
    
    #Check flags and set max distances, paring data array if necessary
    if useDistanceParams[0]:
        xMax = maxDistances[0]
        data_mask = data[:,0] <= xMax
        data = data[data_mask]
    else:
        xMax = max_values_data[0]
        
    if useDistanceParams[1]:
        yMax = maxDistances[1]
        data_mask = data[:,1] <= yMax
        data = data[data_mask]
    else:
        yMax = max_values_data[1]
        
    if useDistanceParams[2]:
        zMax = maxDistances[2]
        data_mask = data[:,2] <= zMax
        data = data[data_mask]
    else:
        zMax = max_values_data[2]
        
    #Create array with number of bins for input to histogram function
    #Note: number of bins will be approximate if the max distance is not divisible by
    # desired bin size
    max_values_xyz = [xMax, yMax, zMax]
    numBinsApprox = [int(abs(d/s)) for d,s in zip(max_values_xyz,list(binSizes))]
    
    #Debugging statements for multiprocessing development
#     print('*'*40)
#     print(max_values_xyz)
#     print(binSizes)
#     print(numBinsApprox)
#     print('*'*40)

    #numpy function call
    hist3d,bins = np.histogramdd(data, numBinsApprox)
        
    return hist3d