
#Standard library modules
import multiprocessing as mp
from multiprocessing import shared_memory
import configparser as cf
import traceback
from ctypes import c_char
import datetime
import time

#Raspberry Pi modules for GPS UART interface
import serial
import adafruit_gps




#Other modules
import openpylivox as opl
#import openpylivox_repeat_thread as opl
import pointcloudprocessor as pcp

def GetTimeGPS(gps_object, attempts, delay, utc_offset):
    while attempts > 0:
        
        gps_object.update()
        
        if not gps_object.has_fix():
            time.sleep(delay)
            attempts -= 1
            continue
        #Extract time values from received utc message
        month = str(gps.timestamp_utc.tm_mon)
        day = str(gps.timestamp_utc.tm_mday)
        year = str(gps.timestamp_utc.tm_year)
        minute = str(gps.timestamp_utc.tm_min)
        second = str(gps.timestamp_utc.tm_sec)
        #Correct hour from utc
        hour = str(gps.timestamp_utc.tm_hour + utc_offset)
        
        #Construct string
        datetime_string_filename = f'{year}-{month}-{day}__{hour}--{minute}--{second}'
        
        return datetime_string_filename
    
def GetDateTimeTest():
    format_string = '%Y-%m-%d__%H--%M--%S'
    dt_string = datetime.datetime.now().strftime(format_string)
    return dt_string



#Need to pass config. parameters to this
def SensorInit(sensor_object, ret_mode):
    connected = sensor_object.auto_connect('192.168.1.2')

    if connected:
        # Sensor object methods to display information about connection/device
        connParams = sensor_object.connectionParameters()
        firmware = sensor_object.firmware()
        serial = sensor_object.serialNumber()
        #Probably should be false in implementation to eliminate printing costs
        sensor_object.showMessages(True)

        sensor_object.lidarSpinUp()
        sensor_object.setLidarReturnMode(ret_mode)  # 0 = single first, 1 = single strongest, 2 = dual return
        # Unsure about this parameter, probably should be false for snow collection
        sensor_object.setRainFogSuppression(False)

        
        
def SensorOperation(sensor_object, number_records, record_duration, shared_dt_string, data_processor_empty,
                    gps, gps_attempts, gps_delay, hour_offset):
    secWaitBeforeCollect = 0.1
    
    for n in range(number_records):
        #Start data stream thread
        sensor_object.dataStart_RT_B()
        #Wait until processor is empty
        data_processor_empty.wait()
        print("Main says: Beginning collection " + str(n))
        #Uncomment to use datetime() method for file name
        #dt_string = GetDateTimeTest()
        #Uncomment to use GPS module for file name
        #dt_string = GetTimeGPS(gps, gps_attempts, gps_delay, hour_offset)
        filename = "Ground_Elevation_"+str(n)
        shared_dt_string.value = filename.encode('utf-8')
        #Begin collection of point cloud
        sensor_object.saveDataToFile(dt_string, secWaitBeforeCollect, record_duration)
        #Wait for all points to be collected
        while not sensor_object.doneCapturing():
            continue
        #Must stop/start thread for repeat collections
        sensor_object.dataStop()
    
    sensor_object.lidarSpinDown()
    
    sensor_object.disconnect()
    
    print("Data collection session has completed")
    
    
    
    

if __name__ == '__main__':

    #Initialize serial object for UART interface
    uart = serial.Serial("dev/ttyS0", baudrate=9600, timeout=10)
    #Instantiate GPS object
    gps = adafruit_gps.GPS(uart, debug=False)
    
    #Send commands to GPS to set return characteristics
    #See https://docs.circuitpython.org/projects/gps/en.latest/index.html
    #Set which return information to include
    gps.send_command(b"PMTK314,0,1,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0")
    #Set refresh rate in milliseconds
    gps.send_command(b"PMTK220,1000")
    
    
    
    #Open configparser object and read configuration file
    conf = cf.ConfigParser()
    conf.read('ground_calibrate_config.ini')
    conf_sections = conf.sections()
    
    # Get scheduling parameters from config. file
    record_duration = int(conf['Schedule']['record_duration'])
    number_records = int(conf['Schedule']['records_per_session'])
    time_between_records = int(conf['Schedule']['time_between_records'])
    
    # Get LiDAR parameters from config. file
    return_mode = int(conf['LiDAR Parameters']['return_mode'])
    rain_fog_suppress = conf['LiDAR Parameters'].getboolean('rain_fog_mode')
    
    # Get other script params from conf. file
    use_averaging = conf['Script Parameters'].getboolean('use_averaging')
    gps_fix_attempts = int(conf['Script Parameters']['gps_fix_attempts'])
    gps_fix_delay = int(conf['Script Parameters']['gps_fix_delay'])
    utc_hour_offset = int(conf['Script Parameters']['timezone_offset'])
    
    
    #Calculate points per cloud
    points_per_record = int(100_000 * (1 + return_mode//2) * record_duration)
    print("Points per record: ", points_per_record)
    
    # Create array in shared memory (num_points * 3 coords per point * 4 bytes per coord ==> num_points*12)
    SHARED_DATA_ARRAY = shared_memory.SharedMemory(name='SHARED_BUFF', create=True, size=points_per_record*12)
    print("MAIN SAYS: SHARED_DATA_ARRAY: ",SHARED_DATA_ARRAY)
    
    #Create a mp.Array to store current string
    SHARED_STRING_ARRAY = mp.Array(c_char, b'Ground_Elevations_X')
    
    #Create synchronization primitives from mp to coordinate between collection and data handling processes
    DATA_READY_4_PROCESSING = mp.Event()
    DATA_PROCESSOR_EMPTY  = mp.Event()
    DATA_PROCESSOR_NOT_COPYING = mp.Event()
    #Set true for initial collection blocks
    DATA_PROCESSOR_EMPTY.set()
    DATA_PROCESSOR_NOT_COPYING.set()
    #may need more
    
    # Instantiate objects for sensor handler and data handler classes
    # Optional final Boolean argument sets whether messages are printed
    try:
        #Instantiate LiDAR driver object with shared values passed as arguments
        sensor = opl.openpylivox(SHARED_STRING_ARRAY, DATA_READY_4_PROCESSING, DATA_PROCESSOR_EMPTY, 
                                 DATA_PROCESSOR_NOT_COPYING, points_per_record, True)
        
        SensorInit(sensor, return_mode)
        #Instantiate data processor object with shared values passed as arguments
        data_handler = pcp.PointCloudProcessor(SHARED_STRING_ARRAY, points_per_record, DATA_READY_4_PROCESSING,
                                                DATA_PROCESSOR_EMPTY, DATA_PROCESSOR_NOT_COPYING)
        #Bind run method of data processor to a separate process                                        
        data_process = mp.Process(target=data_handler.run_processing, args=(number_records,))
        data_process.start()
        #Begin LiDAR collection
        SensorOperation(sensor, number_records, record_duration, SHARED_STRING_ARRAY, DATA_PROCESSOR_EMPTY,
                        gps, gps_fix_attempts, gps_fix_delay, utc_hour_offset)
        #Join function
        data_process.join()
       
        print("Everything has completed!")
    except:
        traceback.print_exc()
    finally:
        SHARED_DATA_ARRAY.close()
        SHARED_DATA_ARRAY.unlink()
        print("Finally block executes")
        import sys
        sys.exit()
    


