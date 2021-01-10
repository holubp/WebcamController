#!/usr/bin/python3
# vim:ts=4:sw=4:tw=0:et

import os
import time
import datetime
import argparse
import logging as log
import sys
import json
import pytz

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
parser.add_argument('-r', '--dry-run', dest='dryrun', action='store_true', help='do not run the actual tools')
parser.add_argument('-p', '--preserve-all-manual', dest='preserveallmanual', action='store_true', help='keep all manual exposures')
parser.set_defaults(configFile='capture-shot.conf', logFile=None, pidFile=None, dryrun=False, preserveallmanual=False)
args = parser.parse_args()

logFormatStr = "%(levelname)s|%(name)s|%(asctime)s|%(message)s"
logger = log.getLogger("CaptureShot")
logLevel = log.WARN
if args.debug:
    logLevel = log.DEBUG
elif args.verbose:
    logLevel = log.INFO
log.basicConfig(level=logLevel, format=logFormatStr)

city = {}
city['latitude'] = 0.0
city['longitude'] = 0.0
city['name'] = "City"
city['country'] = "Country"
city['timezone'] = "UTC"
city['elevation'] = 0

remote = None

with open(args.configFile) as configFile:
    config = json.load(configFile)
    if 'location' in config:
        city = config['location']
        assert 'latitude' in city
        assert 'longitude' in city
        assert 'name' in city
        assert 'country' in city
        assert 'timezone' in city
        assert 'elevation' in city
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

log.info(f"City: {city['latitude']} {city['longitude']} {city['name']} {city['country']} {city['timezone']} {city['elevation']}")

ephem_home = ephem.Observer()
ephem_home.lat, ephem_home.lon, ephem_home.elevation = str(city['latitude']), str(city['longitude']), int(city['elevation'])
ephem_moon = ephem.Moon()

location = LocationInfo(name = city['name'], region = city['country'], latitude = city['latitude'], longitude = city['longitude'], timezone = city['timezone'])
observer = location.observer
#observer.elevation = city['elevation']

now = time.localtime()
target_dir = f'{fswebcam["dir"]}/'+time.strftime('%Y/%m', now)
target_file = time.strftime('%Y%m%d-%H%M%S', now)
if not os.path.exists(target_dir):
    log
    os.makedirs(target_dir)
params_auto_false=lambda: f'-s "Exposure, Auto=Aperture Priority Mode" -s "Exposure, Auto Priority=False" -F {num_frames}'
params_auto_true=lambda: f'-s "Exposure, Auto=Aperture Priority Mode" -s "Exposure, Auto Priority=True" -F {num_frames}'
params_manual=lambda: f'-s "Exposure, Auto=Manual Mode" -s "Exposure (Absolute)={exposure}" -s "Exposure, Auto Priority=False" -F {num_frames_factor*num_frames}'

s = sun(location.observer, tzinfo=None)
utc=pytz.UTC
time_now = utc.localize(datetime.datetime.now())
log.debug("Sun events in UTC: dawn={dawn}, sunrise={sunrise}, noon={noon}, sunset={sunset}, dusk={dusk}".format(**s))
log.debug(f"Time now in UTC: {time_now}")
offset = 30
if time_now > (s['sunrise'] + datetime.timedelta(minutes=offset)) and time_now < (s['sunset'] + datetime.timedelta(minutes=-offset)) :
    log.debug(f"Time is between sunrise and sunset (with adjustments of {offset} minutes)")
    num_frames = 10
elif time_now > s['dawn'] and time_now < s['dusk']:
    log.debug("Time is between dawn and sunrise or sunset and dusk")
    num_frames = 50
else:
    log.debug("Time is night between dusk and dawn")
    num_frames = 100

num_frames_factor = 1

def run(cmd : str):
    if args.dryrun:
        print(cmd)
    else:
        log.debug(f'Running cmd: {cmd}')
        os.system(cmd)

run(f'{fswebcam["bin"]} {params_auto_false()} {fswebcam["params"]} {target_dir}/{target_file}-auto-false.{fswebcam["ext"]}')
run(f'{fswebcam["bin"]} {params_auto_true()} {fswebcam["params"]} {target_dir}/{target_file}-auto-true.{fswebcam["ext"]}')
for (exposure, num_frames_factor) in [(x*y, f) for (y,f) in [(1,2), (10,1), (100,1), (1000,2)] for x in [1, 2, 5]]:
    run(f'{fswebcam["bin"]} {params_manual()} {fswebcam["params"]} {target_dir}/{target_file}-manual-{exposure}.{fswebcam["ext"]}; exiv2 -M"set Exif.Photo.ExposureTime {exposure}/5000" {target_dir}/{target_file}-manual-{exposure}.{fswebcam["ext"]}')
run(f'OMP_NUM_THREADS=4 enfuse --exposure-optimum=0.7 --hard-mask -v --compression=80 -o {target_dir}/{target_file}-HDR.{fswebcam["ext"]} {target_dir}/{target_file}-manual-*.{fswebcam["ext"]}')
# TODO: select best one based on histogram structure
# this is just a simple time heuristic
#if time_now > s['sunrise'] and time_now < s['sunset']:
#    run(f'cp {target_dir}/{target_file}-manual-500.{fswebcam["ext"]} {target_dir}/{target_file}-manual.{fswebcam["ext"]}')
#else:
#    run(f'cp {target_dir}/{target_file}-manual-5000.{fswebcam["ext"]} {target_dir}/{target_file}-manual.{fswebcam["ext"]}')
# for now we go for the largest file -- assuming maximum amount of data worth of JPEG visual model
run(f'cp `ls --sort=size {target_dir}/{target_file}-manual-*.{fswebcam["ext"]} | head -1` {target_dir}/{target_file}-manual.{fswebcam["ext"]}')
if not args.preserveallmanual:
    run(f'rm {target_dir}/{target_file}-manual-*.{fswebcam["ext"]}')

run(f'cp {target_dir}/{target_file}-auto-false.{fswebcam["ext"]} {fswebcam["dir"]}/current-auto-false.{fswebcam["ext"]}')
run(f'cp {target_dir}/{target_file}-auto-true.{fswebcam["ext"]} {fswebcam["dir"]}/current-auto-true.{fswebcam["ext"]}')
run(f'cp {target_dir}/{target_file}-manual.{fswebcam["ext"]} {fswebcam["dir"]}/current-manual.{fswebcam["ext"]}')
run(f'cp {target_dir}/{target_file}-HDR.{fswebcam["ext"]} {fswebcam["dir"]}/current-HDR.{fswebcam["ext"]}')

run(f'cd {fswebcam["dir"]} && {remote["rsync"]} * {remote["hostname"]}:{remote["dir"]}/')

run(f'rm -r {fswebcam["dir"]}')
