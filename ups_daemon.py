import logging
import logging.config
import sys, os, signal
from ina226 import INA226
import time
import threading
from datetime import datetime
from time import sleep
import pigpio


logger = logging.getLogger(__name__)
logging.basicConfig(filename='events.log', encoding='utf-8', level=logging.INFO)


# set the sense pin from the battery, the resistor divider output is Low at power loss
PowerSense_GPIO = 4


# ! adjust the shunt resistance in Ohms
shunt = 0.008

# ? Battery alarm voltage 3.2V, max charged to 4.2V
# from_min can be changed, the rest are limitgs set by the module

from_min = 3.2
to_max = 4.22
max_amps = 3


ina = INA226(busnum=1, max_expected_amps=max_amps, shunt_ohms=shunt, log_level=logging.ERROR)
ina.configure()

pi = pigpio.pi() # Connect to local Pi

# Flags to control the worker thread
worker_thread_running = False
worker_thread = None
start_time = None
stop_time = None

# Define a worker function that runs in a separate thread
# @timed(unit='s', name='UPS mode: ')
def worker():
    while worker_thread_running:
        ina.wake(3)        
        sampling()
        sleep(3)
        time.sleep(1)
    
def time_now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

# CTRL+C detected => exit
def signal_handler(sig, frame):
    worker_thread_running = False
    if worker_thread is not None:
        worker_thread.join()
    sys.exit(0)


def remap(number):                         
    number_s = number - from_min
    to_max_s = to_max - from_min
    return ((number_s / to_max_s) * 99) + 1

    
def my_callback(gpio, level, tick):
    global worker_thread_running, worker_thread,start_time, stop_time


    if level == 1:   
        
        if worker_thread_running:
            worker_thread_running = False
            stop_time = time.time()
            worker_thread.join()  # Wait for the worker thread to finish
            elapsed_time = stop_time - start_time
            logger.info(f"{time_now()}  > UPS ran for: {int(elapsed_time)} sec")            

    else:                 
        logger.info(f"{time_now()}  > Power restored, charging mode ...")        
        if not worker_thread_running:
            worker_thread_running = True
            worker_thread = threading.Thread(target=worker)
            start_time = time.time()
            worker_thread.start()
     

def sampling():
    
    ina.set_low_battery(from_min)
    vbat = ina.voltage()

    if (vbat > to_max):
        vbat = to_max
    elif (vbat <= from_min):
        
        # ! Call for system shutdown
        # save battery life status
        logger.info(f"{time_now()}  > UPS battery too low, shutting down.")    
        os.system('sudo shutdown now')
        
    logger.info(f"{time_now()}  > Stats: {round(vbat,2),int(ina.current())}")
    sleep(4)


def main():
    
    pi.set_pull_up_down(PowerSense_GPIO, pigpio.PUD_UP)   
    pi.set_mode(PowerSense_GPIO, pigpio.INPUT)   
    pi.set_glitch_filter(PowerSense_GPIO, 10000)
    cb = pi.callback(PowerSense_GPIO, pigpio.EITHER_EDGE, my_callback)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.pause()
    logger.info(f"{time_now()}  > Waiting for the power loss signal ...")        

    
    
if __name__ == "__main__":
    
    logger.info(f"{time_now()}  > UPS started ...")        
    main()
