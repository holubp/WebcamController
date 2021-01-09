#!/usr/bin/python3
# vim:ts=4:sw=4:tw=0:et

import os
import time
import datetime
import argparse
import logging as log
import sys
import json

from astral import LocationInfo
from astral.sun import sun
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
parser.set_defaults(configFile='capture-shot.conf', logFile=None, pidFile=None, dryrun=False)
args = parser.parse_args()

logFormatStr = "%(levelname)s|%(name)s|%(asctime)s|%(message)s"

logger = log.getLogger("ShellyRollerController")
formatter = log.Formatter(logFormatStr)


logLevel = log.WARN
if args.debug:
    logLevel = log.DEBUG
elif args.verbose:
    logLevel = log.INFO


city = {}
city['latitude'] = 0.0
city['longitude'] = 0.0
city['name'] = "City"
city['region'] = "Country"
city['timezone'] = "UTC"
city['elevation'] = 0

remote = None

with open(args.configFile) as configFile:
    config = json.load(configFile)
    if 'location' in config:
        city['latitude'] = config['location'].get('latitude', city['latitude']),
        city['longitude'] = config['location'].get('longitude', city['longitude']),
        city['name'] = config['location'].get('city', city['name']),
        city['country'] = config['location'].get('region', city['region']),
        city['timezone'] = config['location'].get('timezone', city['timezone'])
        city['elevation'] = config['location'].get('elevation', city['elevation'])
    if 'remote' in config:
        remote = config['remote']
        assert 'hostname' in remote
        assert 'dir' in remote
        assert 'rsync' in remote
    assert 'fswebcam' in config
    if 'fswebcam' in config:
        fswebcam = config['fswebcam']
        assert 'bin' in fswebcam
        assert 'params' in fswebcam
        assert 'dir' in fswebcam
        assert 'ext' in fswebcam

#location = LocationInfo(name = city['name'], region = city['region'], latitude = city['latitude'], longitude = city['longitude'], timezone = city['timezone'])
#observer = location.observer
#observer.elevation = city['elevation']

#ephem_home = ephem.Observer()
#ephem_home.lat, ephem_home.lon, ephem_home.elevation = str(city['latitude']), str(city['longitude']), int(city['elevation'])
#ephem_moon = ephem.Moon()

now = time.localtime()
target_dir = f'{fswebcam["dir"]}/'+time.strftime('%Y/%m', now)
target_file = time.strftime('%Y%m%d-%H%M%S', now)
if not os.path.exists(target_dir):
    log
    os.makedirs(target_dir)
params_auto_false=lambda: f'-s "Exposure, Auto=Aperture Priority Mode" -s "Exposure, Auto Priority=False" -F {num_frames}'
params_auto_true=lambda: f'-s "Exposure, Auto=Aperture Priority Mode" -s "Exposure, Auto Priority=True" -F {num_frames}'
params_manual=lambda: f'-s "Exposure, Auto=Manual Mode" -s "Exposure (Absolute)={exposure}" -s "Exposure, Auto Priority=False" -F {num_frames_factor*num_frames}'

#s = sun(location.observer, date=now, tzinfo=city.timezone)

num_frames_factor = 1
num_frames = 10
os.system(f'{fswebcam["bin"]} {fswebcam["params"]} {params_auto_false()} {target_dir}/{target_file}-auto-false.{fswebcam["ext"]}')
os.system(f'{fswebcam["bin"]} {fswebcam["params"]} {params_auto_true()} {target_dir}/{target_file}-auto-true.{fswebcam["ext"]}')
# TODO: set numberof frames based on the time of day w.r.t. sun
for (exposure, num_frames_factor) in [(x*y, f) for x in [1, 2, 5] for (y,f) in [(1,1), (10,1), (100,1), (1000,2)]]:
    os.system(f'{fswebcam["bin"]} {fswebcam["params"]} {params_manual()} {target_dir}/{target_file}-manual-{exposure}.{fswebcam["ext"]}; exiv2 -M"set Exif.Photo.ExposureTime {exposure}/5000" {target_dir}/{target_file}-manual-{exposure}.{fswebcam["ext"]}')
os.system(f'enfuse -o {target_dir}/{target_file}-HDR.{fswebcam["ext"]} {target_dir}/{target_file}-manual-*.{fswebcam["ext"]}')
# TODO: select best one based on time of the day w.r.t. sun or file size
os.system(f'cp {target_dir}/{target_file}-manual-2000.{fswebcam["ext"]} {target_dir}/{target_file}-manual.{fswebcam["ext"]}')
os.system(f'rm {target_dir}/{target_file}-manual-*.{fswebcam["ext"]}')

os.system(f'cp {target_dir}/{target_file}-auto-false.{fswebcam["ext"]} {fswebcam["dir"]}/current-auto-false.{fswebcam["ext"]}')
os.system(f'cp {target_dir}/{target_file}-auto-true.{fswebcam["ext"]} {fswebcam["dir"]}/current-auto-true.{fswebcam["ext"]}')
os.system(f'cp {target_dir}/{target_file}-manual.{fswebcam["ext"]} {fswebcam["dir"]}/current-manual.{fswebcam["ext"]}')
os.system(f'cp {target_dir}/{target_file}-HDR.{fswebcam["ext"]} {fswebcam["dir"]}/current-HDR.{fswebcam["ext"]}')

os.system(f'cd {fswebcam["dir"]} && {remote["rsync"]} * {remote["hostname"]}:{remote["dir"]}/')

print(f'rm -r {fswebcam["dir"]}')
