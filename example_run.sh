#!/bin/bash
echo "Starting rpi-metro-display..."
python /home/pi/rpi-metro-display/rpi-metro-display.py <path-to-log-file> <wmata-api-key> <station-code> <direction-code> <font-file> <path-to-metro-lines-file> <path-to-metro-stations-file>
