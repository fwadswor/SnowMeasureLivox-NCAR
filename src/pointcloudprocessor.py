# -*- coding: utf-8 -*-
"""
Created on Mon Jun 27 15:27:10 2022

@author: Fletcher Wadsworth
@email: wadsworthfletcher@gmail.com
"""

# Module with class for performing desired point cloud processing routines.
# Processing routines are found in the processing_functions.py module, and configuration
# parameters are found in the processing_config.ini config file.

# Objects of this type are intended to work as a process in tandem with an
# openpylivox object to conduct data collection and processing routines in parallel.
# The specific processing functionality is contained in the processing_functions.py module.
# Care should be taken when adding or altering processing functions here or in
# the function definition module; since this is a mutliprocessing implementation,
# excessive changes may result in synchronicity problems between the processes, 
# causing poorer performance or incorrect data in the worst case.

# Written by Fletcher Wadsworth for NCAR|UCAR, found at:
#     https://github.com/fwadswor/SnowMeasureLivox-NCAR
    
# &&&&&&&&&&&&
# Need to put NCAR license/info/whatever else here
# &&&&&&&&&&&&


#Import necessary libraries
import numpy as np
#import os
import processing_functions as pf
import configparser
#import multiprocessing as mp
from multiprocessing import shared_memory

class PointCloudProcessor:
    
    def __init__(self, gps_file_name, null_points, num_points, data_ready_for_proc, data_processor_empty, data_processor_not_copying):
        
        
        #self.data_array = None
        self._num_points = num_points
        self.gps_file_name = gps_file_name
        self.data_ready = data_ready_for_proc
        self.data_processor_empty = data_processor_empty
        self.not_copying = data_processor_not_copying
        self.null_points = null_points
        
        #Read collection config file for parameters and routines
        self.conf = configparser.ConfigParser()
        self.conf.read('processing_config.ini') 
        self.conf_sections = self.conf.sections()

        
        #Obtain data array from shared memory
        self.shared_memory_array = shared_memory.SharedMemory(name='SHARED_BUFF')
        #Bind shared data array to numpy array
        self.shared_array = np.ndarray((self._num_points,3), dtype='float32', buffer=self.shared_memory_array.buf)
        print("PROCESSOR SAYS: shared_memory: ",self.shared_memory_array)
        print("PROCESSOR SAYS: shape of shared_array: ",self.shared_array.shape)
        #Load ground truth elevation measurements
        #self.ground_elevation = np.load('FILENAME.npy')
        self.ground_elevation = 3
        
        #Flag to indicate routine is complete to parallel collection process
        #self.processing_complete = False
        
        
        print("PROCESSOR SAYS: Processor initialization complete!")
        
        
    #def run_processing(self, data_array, data_ready=False):
    def run_processing(self, records_per_session):
        for n in range(records_per_session):
            file_num = str(n)
            #Wait until data is ready
            print("PROCESSOR SAYS: Processor waiting for data!")
            self.data_ready.wait()
            #Set flag to indicate copying is in progress, not to start overwriting
            self.not_copying.clear()
            print("PROCESSOR SAYS: Processor copying data from shared array!")
            #Copy data from shared array locally to process
            self.data = np.copy(self.shared_array)
            filename_bytes = self.gps_file_name.value
            filename_string = filename_bytes.decode('utf-8')
            nullPts = self.null_points.value
            #Reset copying flag
            self.not_copying.set()
            #Set flag to True indicating that this process is occupied
            self.data_processor_empty.clear()
            
            #---------Ground/snow elevation estimation routine----------
            
            #eliminate null points in array
            rows = self.data.shape[0]
            self.data = self.data[:rows-nullPts]
            
            #Check if routine is enabled in config file
            if (self.conf['GroundVolumeMeasure'].getboolean('enable')):
                #Function call for GroundVolumeMeasure
                save_above_ground = self.conf['GroundVolumeMeasure'].getboolean('save_above_ground')
                print("PROCESSOR SAYS: Processor performing ground elevation routine!")
                elevations, air_points = pf.GroundVolumeMeasure(self.data, self.ground_elevation, save_above_ground,         
                                                    float(self.conf['GroundVolumeMeasure']['bin_size']),
                                                    float(self.conf['GroundVolumeMeasure']['min_threshold']),
                                                    self.conf['GroundVolumeMeasure'].getboolean('use_distance_params'),
                                                    float(self.conf['GroundVolumeMeasure']['max_distance_x']),
                                                    float(self.conf['GroundVolumeMeasure']['max_distance_y']))
                
                
                #Generate binary filename and save file
                print("PROCESSOR SAYS: Processor saving elevation data file!")
                np.save(filename_string + '_elevations_'+file_num+'.npy',elevations)
                
                if save_above_ground:
                    np.save(filename_string + '_air_pointcloud_'+file_num+'.npy', air_points)
                
                
            #------------3D mesurement density bins routine------------  
                
            #Check if routine is enabled in config file
            if (self.conf['Density3D'].getboolean('enable')):
                #Make tuples from config. parameters for function call
                print("PROCESSOR SAYS: Processor performing 3d density binning routine!")
                bin_sizes = (float(self.conf['Density3D']['bin_size_x']),
                             float(self.conf['Density3D']['bin_size_y']),
                             float(self.conf['Density3D']['bin_size_z']))
                use_distance_params = (self.conf['Density3D'].getboolean('use_distance_params_x'),
                                       self.conf['Density3D'].getboolean('use_distance_params_y'),
                                       self.conf['Density3D'].getboolean('use_distance_params_z'))
                print('-'*40)                       
                print("Use distance params in 3D binning routine: ",use_distance_params)                       
                max_distances = (float(self.conf['Density3D']['max_distance_x']),
                                 float(self.conf['Density3D']['max_distance_y']),
                                 float(self.conf['Density3D']['max_distance_z']))
                
                #function call for 3d density routine
                density3d = pf.Binning3D(self.data, bin_sizes, 
                                               use_distance_params, max_distances)
                
                #Generate binary filename and save data to file
                print("PROCESSOR SAYS: Processor saving 3d density data file!")
                np.save(filename_string + '_3d_density_'+file_num+'.npy', density3d)
            
                
            #------ Put in more data processing function calls here if desired ------
            
            #------------------------------------------------------------------------
            
            #Set flag to indicate process is complete and ready for more data    
            self.data_processor_empty.set()
             
            
        
        
        