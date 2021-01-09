#!/usr/bin/python3
# vim:ts=4:sw=4:tw=0:et

import os
import argparse
import logging as log
import sys

from astral import Astral, Location
import ephem
from math import degrees

class ExtendAction(argparse.Action):
        """
        This class is used to extend arrays for argparse
        """

        def __call__(self, parser, namespace, values, option_string=None):
                items = getattr(namespace, self.dest) or []
                items.extend(values)
                setattr(namespace, self.dest, items)

parser = argparse.ArgumentParser()
parser.register('action', 'extend', ExtendAction)
parser.add_argument('-v', '--verbose', dest='verbose', action='store_true', help='verbose information on progress of the data checks')
parser.add_argument('-d', '--debug', dest='debug', action='store_true', help='debug information on progress of the data checks')
parser.add_argument('-c', '--config', dest='configFile', nargs=1, help='location of config file')
parser.add_argument('-l', '--log', dest='logFile', nargs=1, help='location of log file')
parser.set_defaults(configFile='capture-shot.conf', logFile=None, pidFile=None, dryrun=False)
args = parser.parse_args()

logFormatStr = "%(levelname)s|%(name)s|%(asctime)s|%(message)s"

logger = log.getLogger("ShellyRollerController")
formatter = log.Formatter(logFormatStr)

if args.logFile is None and not args.nodaemon:
        print "Log file has to be specified for the daemon mode"
        exit(1)

logFH = None
if args.logFile is not None:
        logFH = log.FileHandler(args.logFile[0])
        logFH.setFormatter(formatter)
        if args.debug or args.verbose:
                # file logging max to INFO, since otherwise we fill the storage too fast
                logFH.setLevel(log.INFO)
        logHandlers.append(logFH)
        logSH = log.StreamHandler()
        logSH.setFormatter(formatter)
        logHandlers.append(logSH)
else:
        stdout_logger = log.getLogger('STDOUT')
        sl = StreamToLogger(stdout_logger, log.INFO)
        sys.stdout = sl
        stderr_logger = log.getLogger('STDERR')
        sl = StreamToLogger(stderr_logger, log.ERROR)
        sys.stderr = sl

logLevel = log.WARN
if args.debug:
        logLevel = log.DEBUG
elif args.verbose:
        logLevel = log.INFO


a = Astral()
a.solar_depression = 'civil'

city = Location()
city.name = 'City'
city.region = 'Country'
city.latitude = 0.0
city.longitude = 0.0
city.timezone = 'UTC'
city.elevation = 0

with open(args.configFile) as configFile:
        config = json.load(configFile)
        if "thresholds" in config:
                for k in ('avgWindThreshold', 'avgGustThreshold', 'windRestoreCoefficiet', 'timeOpenThresholdMinutes', 'timeRestoreThresholdMinutes', 'closeAtTemperatureAtAnyAzimuth', 'closeAtTemperatureAtDirectSunlight', 'temperatureRestoreCoefficient'):
                        exec(k + " = config['thresholds'].get('" + k + "', " + k + ")")
        if "rollers" in config:
                for roller in config['rollers']:
                        rollers.append(ShellyRollerController(roller['name'], str(roller['IP']), str(roller['rollerUsername']), str(roller['rollerPassword']), roller['solarAzimuthMin'], roller['solarAzimuthMax']))
        if "WeeWxGaugeFile" in config:
                gaugeFile = config['WeeWxGaugeFile'].get('location', gaugeFile)
                sleepTime = config['WeeWxGaugeFile'].get('readPeriodSecs', sleepTime)
                historyLength = config['WeeWxGaugeFile'].get('numberOfAvergagedReadings', historyLength)
        if "location" in config:
                city.latitude = config['location'].get('latitude', city.latitude)
                city.longitude = config['location'].get('longitude', city.longitude)
                city.name = config['location'].get('city', city.name)
                city.country = config['location'].get('region', city.region)
                city.timezone = config['location'].get('timezone', city.timezone)
                city.elevation = config['location'].get('elevation', city.elevation)


ephem_home = ephem.Observer()
ephem_home.lat, ephem_home.lon, ephem_home.elevation = str(city.latitude), str(city.longitude), int(city.elevation)
ephem_moon = ephem.Moon()

