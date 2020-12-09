#!/bin/bash
if [[ $(ps aux | grep rpi-metro-display | grep -v grep) ]]; then
    echo "rpi-metro-display is already running."
else
    echo "Starting rpi-metro-display..."
    python /home/pi/rpi-metro-display/rpi-metro-display.py
fi
