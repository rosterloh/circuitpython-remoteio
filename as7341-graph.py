import os

if 'BLINKA_MCP2221' not in os.environ: 
    os.environ['BLINKA_MCP2221'] = '1'

from time import sleep
import board
from adafruit_as7341 import AS7341

i2c = board.I2C()
sensor = AS7341(i2c)
 
 
def bar_graph(read_value):
    scaled = int(read_value / 1000)
    return "[%5d] " % read_value + (scaled * "*")
 

data = sensor.all_channels()
print("F1 - 415nm/Violet  %s" % bar_graph(data[0]))
print("F2 - 445nm/Indigo  %s" % bar_graph(data[1]))
print("F3 - 480nm/Blue    %s" % bar_graph(data[2]))
print("F4 - 515nm/Cyan    %s" % bar_graph(data[3]))
print("F5 - 555nm/Green   %s" % bar_graph(data[4]))
print("F6 - 590nm/Yellow  %s" % bar_graph(data[5]))
print("F7 - 630nm/Orange  %s" % bar_graph(data[6]))
print("F8 - 680nm/Red     %s" % bar_graph(data[7]))