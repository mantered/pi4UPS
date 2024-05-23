#!/usr/bin/env python3
import logging
import logging.config
import signal, sys, os
from ina226 import INA226
import time
import threading
from datetime import datetime
from time import sleep
import pigpio
import schedule
from alive_progress import alive_bar
from alive_progress.animations.bars import bar_factory

logger = logging.getLogger(__name__)
logging.basicConfig(filename='events.log', encoding='utf-8', level=logging.ERROR)
noerror_bar = bar_factory('▏▎▍▌▋▊▉',borders ='[]', errors =('<',''))

# set the sense pin from the battery, the resistor divider output is Low at power loss
PowerSense_GPIO = 4

## ? set to False if you don't need hourly readings
heartBeat = True

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
        # print("Worker is running...")
        ina.wake(3)        
        sampling(True)
        sleep(3)
        time.sleep(1)
    
def time_now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

# remaps voltage range to percentage of usable power left
# the simple method uses just the battery voltage not the (real capacity - consumption)
# ?TODO later: checking capacity usage from known 2200mah x2
# estimate Battery_left = Battery_capacity/Power drawn
# real tested battery capacity needed using batBenchmark.py

def remap(number):                         
    number_s = number - from_min
    to_max_s = to_max - from_min
    return ((number_s / to_max_s) * 99) + 1

def run_once(f):
    def wrapper(*args, **kwargs):
        if not wrapper.has_run:
            wrapper.has_run = True
            return f(*args, **kwargs)
    wrapper.has_run = False
    return wrapper

# CTRL+C detected => exit
def signal_handler(sig, frame):
    
    worker_thread_running = False
    if worker_thread is not None:
        worker_thread.join()
    
    # disconnecting from pigpio to avoid 100% CPU usage
    pi.stop()
    sys.exit(0)
    
def my_callback(gpio, level, tick):
    global worker_thread_running, worker_thread,start_time, stop_time

    if level == 1:   
        
        os.system('cls||clear')
        print("Power restored")
        print("Trickle charging... ")
        
        if worker_thread_running:
            worker_thread_running = False
            stop_time = time.time()
            worker_thread.join()  # Wait for the worker thread to finish
            elapsed_time = stop_time - start_time
            print("UPS mode: %.0f sec" % elapsed_time)
            logger.info(f"{time_now()}  > UPS ran for: {int(elapsed_time)} sec")            

    else:                 
        
        os.system('cls||clear')
        print("Power Loss! UPS ACTIVE! ALERT!")
        if not worker_thread_running:
            worker_thread_running = True
            worker_thread = threading.Thread(target=worker)
            start_time = time.time()
            worker_thread.start()
     

def sampling(source):
    os.system('cls||clear')
    ina.set_low_battery(from_min)
    
    print("Battery status:")
    
    vbat = ina.voltage()
    if (vbat > to_max):
        vbat = to_max
    elif (vbat <= from_min):
        print('DANGER! Shutdown iminent!')
        
        # ! Call for system shutdown
        # save battery life status
        logger.info(f"{time_now()}  > UPS battery too low, shutting down.")    
        os.system('sudo shutdown now')
    
    if source:
        print("Battery voltage : %.2f V" % vbat)
        print("Current draw    : %.0f mA" % ina.current())    
        print("Percent left    :{:3.1f}%".format(remap(vbat)))
        logger.info(f"{time_now()}  > Stats: {round(vbat,2),int(ina.current())}")
        sleep(4)
    else:
        print('hourly check DONE!')
        logger.info(f"{time_now()}  > heartBeat: {round(vbat,2),int(ina.current())}")
        print("Trickle charging... ")
    
# TODO estimate time left in UPS mode
def _calc_time_left(self, vbat):
    time_left = int(self._calc_bat_charge_percent(vbat) * 60 * self.BAT_CAPACITY / self.CURRENT_DRAW)
    if time_left < 0:
        time_left = 0
    return time_left


def hourly_check():
    sampling(False)

def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)


def main():
    # run once at start
    @run_once
    def check_at_start():
        
        # ? enable heartBeat
        if heartBeat:
            scheduler_thread.start()

        maximum = max_amps*1000
        current = int(ina.current())
                
        print("Power draw: {:6.2f} W".format(ina.power()/1000))

        if current < 0 or maximum <= 0 or current > maximum:
                print("Invalid current or maximum battery levels.")

        with alive_bar(maximum, title='Current draw (mAh)', length=10, bar=noerror_bar, stats=False, elapsed=False) as bar:
            for i in range(maximum):
                if i < current:
                    bar()
                time.sleep(0.0005)
            
            
        logger.info(f"{time_now()}  > UPS service started.")        
            
    
    pi.set_pull_up_down(PowerSense_GPIO, pigpio.PUD_UP)   
    pi.set_mode(PowerSense_GPIO, pigpio.INPUT)   
    pi.set_glitch_filter(PowerSense_GPIO, 10000)

    cb = pi.callback(PowerSense_GPIO, pigpio.EITHER_EDGE, my_callback) 
    check_at_start()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.pause()
    
    
if __name__ == "__main__":

    os.system('cls||clear')    
    print("Starting Ups service ... ")
    
    schedule.every().hour.do(hourly_check)    
    
    # testing with 5 min
    # schedule.every(5).minutes.do(hourly_check)

    # # start the scheduler in a separate thread
    scheduler_thread = threading.Thread(target=run_scheduler)
    scheduler_thread.daemon = True  # This ensures the thread will exit when the main program does
    main()
