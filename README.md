# rpi-metro-display

Python 2 code for DC metrorail times display.

A guide to actually build and run this on your own is forthcoming. Until then, a few notes that might help you get started.

This program is intended to be run on a Raspberry Pi, and I've only ever run it on a Raspberry Pi 3B. It will probably run on a Raspberry Pi 4 and might actually run better, but I haven't tried it.

This was written several years ago, so it's still on Python 2. Given the recent interest in this code, I intend to upgrade to Python 3 in the near future.

This code depends on the [rpi-rgb-led-matrix](https://github.com/hzeller/rpi-rgb-led-matrix) library (hence the license choice). This library is not covered in the requirements.txt, you'll need to build it yourself as specified in that library's README.md. I'll provide more details with the release of my how-to guide.

The font that I use on my personal display is `fonts/6x10.bdf` from the `rpi-rgb-led-matrix` library.

Though it looks like one display, I'm actually using two of [these](https://www.adafruit.com/product/2277) Adafruit displays chained together. To drive and power them I'm using Adafruit's [RGB Matrix HAT](https://www.adafruit.com/product/2345).

A WMATA API Key is needed to get live train data. API keys are free and you can sign up for one [here](https://developer.wmata.com/).

The stations and lines files needed to run a display can be created using `updateLinesInfo.py` and `updateStationInfo.py` as stand alone programs.

Station and direction codes can be found using the WMATA API and its associated documentation.
