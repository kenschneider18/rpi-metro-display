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
from multiprocessing import Process, Value, Array
import ctypes
import time
import sys
import os
import requests
import json
import logging

def init_matrix():
    options = RGBMatrixOptions()
    options.rows = 32
    options.chain_length = 4
    options.pwm_bits = 3
    options.pwm_lsb_nanoseconds = 300
    options.gpio_slowdown = 2
    return RGBMatrix(options = options)

def get_incidents(lines_requested, api_key):
    messages = []
    try:
        headers = {"api_key":api_key, "Accept":"application/json"}
        resp = requests.get('https://api.wmata.com/Incidents.svc/json/Incidents', headers=headers)
	logging.info("Attempting to get train data!")
        if resp.status_code != 200:
            logging.error("Error getting train data! Response status code: ", resp.status_code)
        else:
            resp_json = resp.json()
            logging.info("Attemtpting to read JSON")

            for incident in resp_json['Incidents']:
                logging.info("Incident: {}".format(incident))
                logging.info("I am looping")
                # Grab the lines, strip the strings afterward because
                # if we split on '; ' instead of ';' we miss the single
                # string case
                lines_affected = incident['LinesAffected'].split(';')
                logging.info("Lines: {}".format(lines_requested))
                logging.info(lines_affected)
                for index, line in enumerate(lines_affected):
                    lines_affected[index] = unicode.strip(line)

                logging.info(set(lines_requested).intersection(lines_affected))
                if bool(set(lines_requested).intersection(lines_affected)):
                    messages.append(incident['Description'])
                    logging.info("matched!")
    except Exception as e:
        logging.error('Well that went wrong... {}', str(e))

    logging.info(messages)

    return messages

def compute_offset(line):
    pxLength = len(line) * 6
    offset = (128 - pxLength) / 2
    return offset

def add_line(line, lines):
    offset = compute_offset(line)
    lines.append((line, offset))


def divide_lines(words, lines):
    line = words[0]

    for word in words[1:]:
        if len(line) < 21 and len(word) + 1 + len(line) < 21:
            line += ' ' + word
        else:
            add_line(line, lines)
            line = word
    # Add in last line
    add_line(line, lines)


def split_by_length_in_place(words):
    for index, word in enumerate(words):
        n = len(word)
        if n > 21:
            insert_offset = 0
            for x in range(0, n, 20):
                if x == 0:
                    words[index] = word[x : x + 20] + '-'
                else:
                    word_extension = word[x : x + 20]
                    if len(word_extension) >= 20:
                        word_extension += '-'
                    words.insert(index + insert_offset, word_extension)
                insert_offset += 1
    return words


def draw_message(canvas, message, font_file):
    logging.info("Got to draw message")
    font = graphics.Font()
    font.LoadFont(font_file)
    red_color = graphics.Color(255,0,0)
    yellow_color = graphics.Color(200,125,0)
    title_divided = message.split(': ', 1)

    title = ''
    if len(title_divided) == 1:
        words = split_by_length_in_place(message.split(' '))
    elif len(title_divided) == 2:
        title = split_by_length_in_place(title_divided[0])
        words = split_by_length_in_place(title_divided[1].split(' '))
    else:
        words = split_by_length_in_place(message.split(' '))
        logging.error("Error! Title divided length > 2")

    title_lines = []
    # Shouldn't need to worry about a word
    # longer than 21 for now since Silver/Blue/Orange 
    # is the max # of metro lines per alert assuming all lines
    # is all lines
    if title != '':
        divide_lines(title.split(' '), title_lines)

    lines = []
    divide_lines(words, lines)

    height_delta = 8

    logging.info("Drawing lines")

    for index, title_line in enumerate(title_lines):
        lines.insert(index, title_line)

    for i in xrange(0, len(lines), 4):
        if len(lines) - i < 4:
            lines_to_display = len(lines) - i
        else:
            lines_to_display = 4

        for x in range(0,lines_to_display):
            color = yellow_color
            if i+x <= len(title_lines)-1:
               color = red_color
            graphics.DrawText(canvas, font, lines[i+x][1], 7 + x*height_delta, color, lines[i+x][0])
        time.sleep(5)
        canvas.Clear()


def draw_incident(canvas, font_file, message):
    logging.info("Got to draw incident")
    height_delta = 8
    width_delta = 6

    total_width = 128

    font = graphics.Font()
    font.LoadFont(font_file)
    red_color = graphics.Color(255,0,0)
    yellow_color = graphics.Color(200,125,0)
    green_color = graphics.Color(50,150,0)

    canvas.Clear()
    
    for y in range(0, 8):
        for x in range(0, 32):
            x0 = x * 4
            x1 = x0 + 3
            if x % 2 == 0 and y <= 3:
                graphics.DrawLine(canvas, x0, y, x1, y, yellow_color)
            elif x % 2 != 0 and y > 3:
                graphics.DrawLine(canvas, x0, y, x1, y, yellow_color)

    logging.info("Got past drawing squares")

    if "scheduled maintenance" in message or "scheduled track work" in message:
        graphics.DrawText(canvas, font, 1, 15, red_color, "SCHEDULED")
        graphics.DrawText(canvas, font, 1, 23, red_color, "TRACK WORK")
        logging.info("Drawing scheduled track workd")
    else:
        logging.info("Drawing service advisory")
        service = "SERVICE"
        advisory = "ADVISORY"
        graphics.DrawText(canvas, font, compute_offset(service), 15, red_color, service)
        graphics.DrawText(canvas, font, compute_offset(advisory), 23, red_color, advisory)

    for y in range(24, 32):
        for x in range(0, 32):
            x0 = x * 4
            x1 = x0 + 3
            if x % 2 == 0 and y <= 27:
                graphics.DrawLine(canvas, x0, y, x1, y, yellow_color)
            elif x % 2 != 0 and y > 27:
                graphics.DrawLine(canvas, x0, y, x1, y, yellow_color)

    logging.info("Got past drawing other squares")

    time.sleep(5)

    canvas.Clear()
    draw_message(canvas, message, font_file)

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage incidents.py <api_key> <font_file>")
        sys.exit(2)

    api_key = sys.argv[1]
    font_file = sys.argv[2]

    matrix = init_matrix()
    messages = get_incidents(['SV', 'OR', 'GR'], api_key)
    for message in messages:
        draw_incident(matrix, message, font_file)

