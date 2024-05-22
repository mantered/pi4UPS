#!/usr/bin/env python3
import logging
import logging.config
import signal, sys
from ina226 import INA226
import time
import threading
from datetime import datetime
from time import sleep
import RPi.GPIO as GPIO
import stressinjector as injector

# pip install stress-injector
# pip install stress
# # benchmarking the batteries at variable load, log consumption, estimate capacity and running time

logger = logging.getLogger(__name__)
logging.basicConfig(filename='benchmark.log', encoding='utf-8', level=logging.INFO)

def time():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


if __name__ == '__main__':
    injector.CPUStress(seconds=300)