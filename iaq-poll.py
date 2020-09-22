import os

if 'BLINKA_MCP2221' not in os.environ: 
    os.environ['BLINKA_MCP2221'] = '1'

import board
import logging
import time
from adafruit_hts221 import HTS221, Rate
from adafruit_sgp30 import Adafruit_SGP30
from datetime import datetime

logging.basicConfig(
    format='%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S')
logging.info("*** Indoor air quality monitor via {} ***".format(board.board_id))

i2c = board.I2C()
hts = HTS221(i2c)
hts.data_rate = Rate.ONE_SHOT
hts.take_measurements()
first_temperature_reading = hts.temperature
first_humidity_reading = hts.relative_humidity

sgp30 = Adafruit_SGP30(i2c)
sgp30.set_iaq_baseline(0x8973, 0x8AAE)

eco2_tvoc_baseline = []
valid_eco2_tvoc_baseline = False
climate_update_time = 0
climate_update_delay = 150
eco2_tvoc_update_time = 0
eco2_tvoc_update_delay = 150
eco2_tvoc_get_baseline_update_time = 0
start_time = time.time()
testsamples = 0

while testsamples<20:
    # Discard the initialisation readings as per page 8/15 of the datasheet
    eco2, tvoc = sgp30.iaq_measure()
    if eco2 != 400 or tvoc != 0:
        break
    time.sleep(1.0)
    testsamples += 1
    logging.info("IAQ initialising, please wait.")

logging.info("IAQ initialised. {} samples discarded".format(testsamples))

try:
    while True:
        run_time = round((time.time() - start_time), 0)
        
        time_since_climate_update = time.time() - climate_update_time
        if time_since_climate_update >= climate_update_delay:
            climate_update_time = time.time()
            hts.take_measurements()
            logging.info("Temperature: {:.2f} C, Humidity: {:.2f} %".format(hts.temperature, hts.relative_humidity))
            #absolute_hum = int(1000 * 216.7 * (hts.relative_humidity/100 * 6.112 * math.exp(17.62 * hts.temperature / (243.12 + hts.temperature)))
            #               /(273.15 + hts.temperature))
            #sgp30.set_iaq_humidity(absolute_hum)

        time_since_eco2_tvoc = time.time() - eco2_tvoc_update_time
        if time_since_eco2_tvoc >= eco2_tvoc_update_delay:
            eco2_tvoc_update_time = time.time()
            eco2, tvoc = sgp30.iaq_measure()
            logging.info("eCO2: {:d} ppm, TVOC: {:d} ppb".format(eco2, tvoc))
        
        # if run_time > 43200: 
        time_since_eco2_tvoc_get_baseline = time.time() - eco2_tvoc_get_baseline_update_time
        if time_since_eco2_tvoc_get_baseline >= 3600: # Update every hour
            eco2_tvoc_get_baseline_update_time = time.time()
            eco2_tvoc_baseline = sgp30.get_iaq_baseline()
            eco2_tvoc_baseline.append(eco2_tvoc_get_baseline_update_time)
            logging.info("Current eCO2/TVOC Baseline: [{}, {}]".format(hex(eco2_tvoc_baseline[0]), hex(eco2_tvoc_baseline[1])))

        time.sleep(0.5)
except KeyboardInterrupt:
    logging.info('Keyboard Interrupt')