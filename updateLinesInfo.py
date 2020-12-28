# Get DC metrorail lines JSON response and write to a file
# Display WMATA Metrorail times on a dot-matrix display
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
import requests
import sys
import json

def sanitize_input(station_name):
    station_name = station_name.replace("/", " ")
    station_name = station_name.replace("-", " ")
    station_name = station_name.replace("'", "")
    station_name = station_name.lower()

    return station_name

if len(sys.argv) != 3:
    print("Usage updateLinesInfo.py <api_key> <output_dir>")
    sys.exit(2)

api_key = sys.argv[1]
output_dir = sys.argv[2]
headers = {"api_key":api_key, "Accept":"application/json"}

resp = requests.get("https://api.wmata.com/Rail.svc/json/jLines", headers=headers)

lines_json = resp.json()
# Loop through and sanitize the station names. Since we're
# doing this here and don't have a utils file (yet) we need
# to make sure to keep the sanitize_input() in this file
# and in all other places in sync.
for line in lines_json['Lines']:
    line['DisplayName'] = sanitize_input(line['DisplayName'])


lines_file = open(output_dir, "w")
lines_file.write(json.dumps(lines_json))
lines_file.close()
