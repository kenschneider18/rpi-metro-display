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
from rgbmatrix import RGBMatrix, RGBMatrixOptions, graphics
from flask import Flask, jsonify, request
from multiprocessing import Process, Value, Array, Manager
import ctypes
import time
import sys
import os
import requests
import json
import logging
from incidents import get_incidents, draw_incident
from logging.handlers import TimedRotatingFileHandler, SysLogHandler
from traceback import format_exception

app = Flask(__name__)

# Global shared variables
station_code = None
direction = None
stations_file = None
lines_file = None

def exception_hook(exctype, value, tb):
    logging.error("Uncaught exception!")
    logging.error('Type: {}'.format(exctype))
    logging.error('Value: {}'.format(value))
    logging.error('TB: {}'.format(tb))
    logging.error(format_exception(exctype, value, tb))

def show_train_times(api_key, font_file, canvas, prev_lines, prev_cars, prev_dests, prev_times, force_update):
    lines, cars, dests, times = get_train_data(api_key)
    if lines == None and \
        cars == None and \
        dests == None and \
        times == None:
        lines, cars, dests, times = prev_lines, prev_cars, prev_dests, prev_times
        logging.error("Error getting update from WMATA API.")
    elif cmp(lines, prev_lines) != 0 or \
        cmp(cars, prev_cars) != 0 or \
        cmp(dests, prev_dests) != 0 or \
        cmp(times, prev_times) != 0:
        force_update = True
    elif force_update: 
        # Needed after an incident is displayed and the train times haven't changed
        # Realistically I could do without this condition because it's only a log
        # but to me it's nice to have
        logging.debug("Times did not change but a display update was foced.")
    else:
        logging.debug("No update")

    if force_update:
        draw_display(canvas, font_file, lines, cars, dests, times)

    return lines, cars, dests, times

def run_display(api_key, font_file):
    global station_code

    incidents_check_count = 0
    canvas = init_matrix()
    logging.info("RUNNING PROGRAM")

    prev_lines = []
    prev_cars = []
    prev_dests = []
    prev_times = []

    draw_display(canvas, font_file, [], [], [], [])

    while True:
        force_update = False
        if incidents_check_count == 12: # check for incidents every minute
            force_update = True
            station = get_station_by_code(station_code.value)
            if station == None:
                logging.error("Could not find station for code: {}", station_code.value)
            line_codes = get_line_codes_from_station(station)
            incidents = get_incidents(line_codes, api_key)
            for incident in incidents:
                logging.info("Calling draw_incident for: {}".format(incident))
                draw_incident(canvas, font_file, incident)
            incidents_check_count = 0

        prev_lines, prev_cars, prev_dests, prev_times = show_train_times(api_key, font_file, canvas, prev_lines, prev_cars, prev_dests, prev_times, force_update)
        
        time.sleep(5)
        incidents_check_count += 1

def init_matrix():
    options = RGBMatrixOptions()
    options.rows = 32
    options.chain_length = 4
    options.pwm_bits = 3
    options.pwm_lsb_nanoseconds = 300
    options.gpio_slowdown = 2
    return RGBMatrix(options = options)

def get_train_data(api_key):
    global station_code

    headers = {"api_key":api_key, "Accept":"application/json"}

    try:
        resp = requests.get("https://api.wmata.com/StationPrediction.svc/json/GetPrediction/" + station_code.value, headers=headers)
    except Exception as e:
        logging.error("An error occured while getting train data: {}".format(str(e)))
        return None, None, None, None

    lines = []
    cars = []
    dests = []
    times = []

    if resp.status_code != 200:
        logging.error("Error getting train data! Response status code: ", resp.status_code)
    else:
        try:
            resp_json = resp.json()

            logging.debug("GOT RESPONSE!!")

            for train in resp_json['Trains']:
                if train['Group'] == direction.value:
                    car = parse_value(train['Car'])
                    dest = parse_value(train['Destination'])
                    line = parse_value(train['Line'])
                    time = parse_value(train['Min'])
                    lines.append(line)
                    cars.append(car)
                    dests.append(dest)
                    times.append(time)

            # If there are no trains in our group, we need to see if they're on the other
            # platform for single tracking
            if len(lines) == 0 and len(cars) == 0 and len(dests) == 0 and len(times) == 0:
                # Using the terminal station names which we can get from the codes
                # we can see if there are any trains going to our destination on the other
                # pltform
                station = get_station_by_code(station_code.value)
                terminals = get_line_terminals(station)
                trains_on_opposite_platform = []
                for train in resp_json['Trains']:
                    for terminal in terminals:
                        if terminal == sanitize_input(parse_value(train['DestinationName'])):
                            trains_on_opposite_platform.append(train)

                # If there are trains for our destination on the other
                # platform, switch the direction and recreate our trains
                # to be displayed
                new_direction = "1"
                if len(trains_on_opposite_platform) > 0:
                    if direction.value == "1":
                        new_direction = "2"
                    for train in resp_json['Trains']:
                        if train['Group'] == new_direction:
                            car = parse_value(train['Car'])
                            dest = parse_value(train['Destination'])
                            line = parse_value(train['Line'])
                            time = parse_value(train['Min'])
                            lines.append(line)
                            cars.append(car)
                            dests.append(dest)
                            times.append(time)


        except ValueError:
            logging.error("Received value error, invalid JSON.")

    return lines, cars, dests, times

def draw_display(canvas, font_file, lines, cars, dests, mins):
    height_delta = 8
    width_delta = 6

    total_width = 128

    font = graphics.Font()
    font.LoadFont(font_file)
    red_color = graphics.Color(255,0,0)
    yellow_color = graphics.Color(200,125,0)
    green_color = graphics.Color(50,150,0)

    canvas.Clear()
    graphics.DrawText(canvas, font, 0, 7, red_color, "LN CAR  DEST")
    graphics.DrawText(canvas, font, 111, 7, red_color, "MIN")

    i = 0
    for line in lines:
        graphics.DrawText(canvas, font, 0, 15 + i*height_delta, yellow_color, line)
        i += 1

    i = 0
    for car in cars:
        # Handle case for No Passenger trains
        if lines[i] == "No" and car == "":
            graphics.DrawText(canvas, font, 28, 15 + i*height_delta, yellow_color, "Pa")
        elif car == "8": # 8 car trains are green
            graphics.DrawText(canvas, font, 20, 15 + i*height_delta, green_color, car)
        else:
            graphics.DrawText(canvas, font, 20, 15 + i*height_delta, yellow_color, car)
        i += 1

    i = 0
    for dest in dests:
        graphics.DrawText(canvas, font, 40, 15 + i*height_delta, yellow_color, dest)
        i += 1

    i = 0
    for time in mins:
        x = total_width - len(time)*width_delta + 1 # Add one to account for space at end
        graphics.DrawText(canvas, font, x, 15 + i*height_delta, yellow_color, time)
        i += 1

def parse_value(value):
    return value if value != None else ""

def serve():
    app.run(host="0.0.0.0")



def convert_line(line):
    global lines_file
    with open(lines_file.value) as lf:
        lines_json = json.load(lf)
        for existing_line in lines_json['Lines']:
            logging.debug("Input line: {}, compared to: {}".format(line, existing_line['DisplayName']))
            if sanitize_input(line) == existing_line['DisplayName']:
                logging.debug("Matched! Returning {}".format(existing_line['LineCode']))
                return existing_line['LineCode']

    return None

def get_station_by_code(code):
    global stations_file
    with open(stations_file.value) as sf:
        stations = json.load(sf)
        for station in stations['Stations']:
            if station['Code'] == code:
                return station

    return None

def get_station_by_name(station_name, station_lines=None):
    global stations_file
    with open(stations_file.value) as sf:
        stations = json.load(sf)
        for station in stations['Stations']:
            if station_name in station['Name']:
                if station_lines == None:
                    return station
                elif matching_lines(station, station_lines) > 0:
                    return station
    return None

def parse_direction(direction, line):
    if direction == "1":
        code = line["EndStationCode"]
    else:
        code = line["StartStationCode"]

    station = get_station_by_code(code)

    if station != None:
        return station['Name']
    else:
        return ''

def search_lines(line_code):
    global direction
    global lines_file
    with open(lines_file.value) as lf:
        lines_json = json.load(lf)
        for line in lines_json['Lines']:
            if line['LineCode'] == line_code:
                return parse_direction(direction.value, line)

def get_direction_from_terminal(station_name, station_lines):
    global lines_file
    station = get_station_by_name(station_name, station_lines)
    if station != None:
        logging.debug("Name: {} Code: {}".format(station['Name'], station['Code']))
        with open(lines_file.value) as lf:
            lines_json = json.load(lf)
            for line in lines_json['Lines']:
                if line['LineCode'] == "YL":
                    logging.debug("Start: {} End: {}".format(line['StartStationCode'], line['EndStationCode']))
                if station['Code'] == line['StartStationCode']:
                    return "2"
                elif station['Code'] == line['EndStationCode']:
                    return "1"
    logging.debug("Station is None.")
    return None

def get_line_terminals(station, lines=None):
    terminals = []

    # If the user hasn't specified (a) line(s)
    # get all of the lines that run through the
    # station
    if lines == None:
        lines = get_line_codes_from_station(station)

    for line_code in lines:
        terminals.append(search_lines(line_code))

    return list(set(terminals)) # Remove duplicates from the set (some lines have the same terminal station)

def matching_lines(station, station_lines):
    if station_lines == None or station == None:
        return 0

    # Need to get the intersection of the lines
    # passed in and the lines that go to the station
    # being examined. Return the length of the intersection
    lines = get_line_codes_from_station(station)

    # Convert lists to sets, perform bitwise AND to get
    # intersection.
    intersection = set(lines) & set(station_lines)

    return len(intersection)

def get_line_codes_from_station(station):
    lines = []

    # There are 4 possible line codes per
    # station. Each formatted as LineCodeX
    # where x is an integer. Grab the line
    # codes and return a list
    for x in range(1,5):
        line_code = station['LineCode{}'.format(x)]
        if line_code != None and line_code != "":
            lines.append(line_code)

    return lines


# Since there's no utils file (yet) make sure to
# update this everywhere there is one.
def sanitize_input(station_name):
    station_name = station_name.replace("/", " ")
    station_name = station_name.replace("-", " ")
    station_name = station_name.replace("'", "")
    station_name = station_name.lower()

    return station_name


def respond_success(station, lines=None, new_direction=None):
    global direction
    global station_code
    logging.debug("Updating station to: {} with code {}.".format(station['Name'], station['Code']))

    with station_code.get_lock():
        station_code.value = station['Code']

    if new_direction != None:
        with direction.get_lock():
            direction.value = new_direction

    terminals = get_line_terminals(station, lines)

    success_json = {
        "stationName": station['Name'],
        "directions": terminals
    }

    return jsonify(**success_json), 202


# Change station by code
@app.route('/station/code', methods=['POST'])
def change_station_by_code():
    global station_code
    req = request.get_json(force=True)
    with station_code.get_lock():
        try:
            station_code.value = req['station']
        except:
            badresp = {
                'reason': "invalid station code"
            }
            return jsonify(**badresp), 418 #lawl i is a teapot
    return '', 204

@app.route('/station/name', methods=['PUT'])
def change_station_by_name():
    global stations_file
    req = request.get_json(force=True)
    station_name = req['stationName']
    station_lines = None
    terminal_station = None

    if req.has_key('lines'):
        station_lines = req['lines']

    if req.has_key('directionOf'):
        terminal_station = req['directionOf']

    # TODO: Replace this mess of code with JSONschema validation
    if not isinstance(station_name, basestring):
        bad_name = {
            'error': ("Could not parse station code '{}'").format(req['stationName'])
        }
        return jsonify(**bad_name), 400
    else:
        station_name = sanitize_input(station_name)
    
    if station_lines != None:
        if not isinstance(station_lines, list):
            bad_lines = {
                'error': ("Could not parse lines: '{}'").format(station_lines)
            }
            return jsonify(**bad_lines), 400
        else:
            for index, line in enumerate(station_lines):
                if not isinstance(line, basestring) or len(line) < 2 or len(line) > 6:
                    bad_line = {
                        'error': ("Could not parse line '{}'").format(line)
                    }
                    return jsonify(**bad_line), 400
                elif len(line) == 2:
                    # Wait until we've validated we have a string as input.
                    # lines are two letter abbreviations in uppercase
                    line = line.upper()
                    station_lines[index] = line
                else:
                    line = convert_line(line)
                    station_lines[index] = line
                    if line == None:
                        bad_line = {
                        'error': ("Could not find valid line with color '{}'").format(line)
                        }
                        return jsonify(**bad_line), 400


    if terminal_station != None:
        if not isinstance(terminal_station, basestring):
            bad_station = {
                'error': "Could not parse '{}'".format(terminal_station)
            }
            return jsonify(**bad_station), 400
        terminal_station = sanitize_input(terminal_station)
    
    # Look inside cached stations file for the station name
    # and save the associated code
    with open(stations_file.value) as sf:
        stations = json.load(sf)
        for station in stations['Stations']:
            # Use 'in' operator because of stations like
            # 'foggy bottom gwu' and 'ballston mu' where
            # someone would either use one half of the name
            # or the other
            if station_name in station['Name']:
                if station_lines != None and terminal_station != None:
                    optional_direction = get_direction_from_terminal(terminal_station, station_lines)
                    logging.debug("DIRECTION: {}".format(optional_direction))
                    if optional_direction != None and matching_lines(station, station_lines) == len(station_lines):
                        return respond_success(station, station_lines, optional_direction)
                elif station_lines != None:
                    if matching_lines(station, station_lines) == len(station_lines):
                        return respond_success(station, station_lines)
                elif terminal_station != None:
                    # Need to pass the lines of the station
                    # to the get_direction_from_terminal due to
                    # edge case at Fort Totten. This station is the
                    # terminal of the Yellow line but it is also a Red
                    # line station. As a result if we search for the station
                    # by name, we must specify the line we want.
                    lines = get_line_codes_from_station(station)
                    logging.debug(lines)
                    optional_direction = get_direction_from_terminal(terminal_station, lines)
                    logging.debug("DIRECTION: {}".format(optional_direction))
                    if optional_direction != None:
                        return respond_success(station, station_lines, optional_direction)
                elif station['StationTogether1'] != "" or station['StationTogether2'] != "":
                    need_line = {
                        'error': ("Multiple platforms: must specify line(s) for '{}'").format(station_name)
                    }
                    return jsonify(**need_line), 400
                else:
                    return respond_success(station)

    not_found_message = "Could not find station with name '{}'".format(req['stationName'])

    if station_lines != None:
        not_found_message += " and lines '{}'".format(tuple(station_lines))

    if terminal_station != None:
        not_found_message += " and terminal station '{}'".format(terminal_station)

    not_found = {
        'error': not_found_message
    }
    return jsonify(**not_found), 404

@app.route('/direction')
def change_direction():
    global direction
    global station_code
    with direction.get_lock():
        if direction.value == "1":
            direction.value = "2"
        else:
            direction.value = "1"

    station = get_station_by_code(station_code.value)

    return respond_success(station)

@app.route('/state')
def get_state():
    global station_code

    station = get_station_by_code(station_code.value)

    if station == None:
        err_json = {
            'error': "Could not find station for code {}".format(station_code.value)
        }
        return jsonify(**err_json), 500

    return respond_success(station)


def main():
    global station_code
    global direction
    global stations_file
    global lines_file

    if len(sys.argv) != 8:
        print("Usage rpi-metro-display <log_file> <api_key> <initial_station_code> <initial_direction_code> <font_file> <lines_file> <stations_file>")
        sys.exit(2)

    sys.excepthook = exception_hook
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    #logging.basicConfig(filename='/home/pi/matrix-text-test/app.log',level=logging.DEBUG)
    handler = TimedRotatingFileHandler(sys.argv[1],
                                       when="d",
                                       interval=1,
                                       backupCount=5)
    #sys_log_handler = SysLogHandler('/dev/log')


    logger.addHandler(handler)
    #logger.addHandler(sys_log_handler)

    station_code = Array(ctypes.c_char, sys.argv[3])
    direction = Array(ctypes.c_char, sys.argv[4])
    lines_file = Array(ctypes.c_char, sys.argv[6])
    stations_file = Array(ctypes.c_char, sys.argv[7])
    server = Process(target = serve)
    run_displays = Process(target = run_display, args=(sys.argv[2],sys.argv[5],))
    server.start()
    run_displays.start()

if __name__ == '__main__':
    main()

