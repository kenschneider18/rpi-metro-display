# Get DC metrorail stations JSON response and write to a file
# Copyright (C) 2020  Kenneth Schneider

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
import json
import sys
import requests

def sanitize_input(station_name):
    station_name = station_name.replace("/", " ")
    station_name = station_name.replace("-", " ")
    station_name = station_name.replace("'", "")
    station_name = station_name.lower()

    return station_name

if len(sys.argv) != 3:
    print("Usage updateStationInfo.py <api_key> <output_dir>")
    sys.exit(2)

api_key = sys.argv[1]
output_dir = sys.argv[2]
headers = {"api_key":api_key, "Accept":"application/json"}

resp = requests.get("https://api.wmata.com/Rail.svc/json/jStations", headers=headers)

stations_json = resp.json()
# Loop through and sanitize the station names. Since we're
# doing this here and don't have a utils file (yet) we need
# to make sure to keep the sanitize_input() in this file
# and in all other places in sync.
for station in stations_json['Stations']:
    station['Name'] = sanitize_input(station['Name'])

stations_file = open(output_dir, "w")
stations_file.write(json.dumps(stations_json))
stations_file.close()
