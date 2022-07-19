# SnowMeasureLivox-NCAR
Python device driver and point cloud processing software for parallel data collection and processing with Livox Mid-70 LiDAR sensor. Intended for use in remote snow measurement using a Raspberry Pi. Developed for NCAR|UCAR.

<hr>

## Prerequisites
* Tested on Raspberry Pi 3,4 with standard Raspian (Raspberry Pi OS). Python 3.8+ required.
* For GPS timestamp data labelling, Adafruit Ultimate GPS v3 module
* Developed using the Livox Mid-70. See https://www.livoxtech.com/mid-70/downloads for LiDAR User Manual 

## Preparation
A corresponding Raspberry Pi OS has been made to make initial steps simple. If this image is not used directly, a few steps must be taken to configure the Raspberry Pi:
- Set a static IP address of 192.168.1.2 for the Ethernet port (symlink eth0).
- Allow access to the hardware UART pins by disabling the serial console in the raspi-config menu.
- Upgrade Python to version 3.8 or higher and download all necessary libraries (check module imports for non Standard Library modules).

Due to the large memory requirements of point cloud data, a high storage USB flash drive or external hard drive is likely necessary if data is not significantly downsized. In [openpylivox.py](./src/openpylivox.py), [pointcloudprocessor.py](./src/pointcloudprocessor.py), and [SnowMeasureLivox.py](./SnowMeasureLivox.py), the path string for saving data must be changed to reflect the external storage.

## Configuration
All parameters related to scheduling and data processing are found in [main_config.ini](./config/main_config.ini) and [processing_config.ini](./config/processing_config.ini) respectively. Due to the nature of the Ground Elevation routine, arrays must be limited to identical bin size and number of bins for ground level subtraction and direct comparison. Read the comments in those .ini files and their respective use in [SnowMeasureLivox.py](./SnowMeasureLivox.py) and
[pointcloudprocessor.py](./src/pointcloudprocessor.py).

## Main functionality
Collection sessions are determined by the number of recordings and the duration of recordings. An entire session is performed when SnowMeasureLivox.py is executed; to perform another collection session, an OS level scheduler (such as a cron job) or altering SnowMeasureLivox.py to collect again is required.
