#!/usr/bin/env python3
#
# Copyright 2023 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""uch.py Basic command line interface for Pegasus Astro USB Control Hub.

https://pegasusastro.com/products/usb-control-hub/
Only compatible with linux.
"""

import argparse
import fcntl
import serial
import sys
import time

LOCKFILE = '/var/lock/uchserial.lck'
PORT = '/dev/ttyUSB0'
verbose_print = lambda *args, **kwargs: None


def main(argv=None):
    args = parse_args(argv)
    if args.verbose:
        global verbose_print
        verbose_print = print
    with Locker():
        uch = PegasusUCH(args.port)
        usbnum = args.usbnum
        if args.usbnum is not None:
            if args.set is None:  # just get the port status
                print(f'# Getting USB[{usbnum}] status')
                x = uch.get_port(usbnum)
            else:  # set the port on or off
                x = int(bool(args.set))
                print(f'# Setting USB[{usbnum}] = {x}')
                uch.set_port(usbnum, x)
                checkx = uch.get_port(usbnum)
                if x != checkx:
                    raise RuntimeError(f'Failed to set USB[{usbnum}]={x}')
            print(f'USB[{usbnum}]={x}')
        if args.list:  # list status of all ports, and ignore other arguments
            print('# List all port status:')
            for i in uch.portnums:
                x = uch.get_port(i)
                print(f'USB[{i}]={x}')


def parse_args(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', '-D', '--device', nargs='?', type=str,
                        default=PORT)
    parser.add_argument('usbnum', nargs='?', type=int, default=None)
    parser.add_argument('set', nargs='?', type=int, default=None)
    parser.add_argument('--list', '-l', action='store_true')
    parser.add_argument('--verbose', '-v', action='store_true')
    args = parser.parse_args(argv)
    return args


class Locker:
    def __enter__(self):
        verbose_print('trying to get lock')
        self.fp = open(LOCKFILE, 'w')
        fcntl.flock(self.fp.fileno(), fcntl.LOCK_EX)
        verbose_print('got lock')

    def __exit__(self, _type, value, tb):
        fcntl.flock(self.fp.fileno(), fcntl.LOCK_UN)
        self.fp.close()
        verbose_print('release lock')


class PegasusUCH:
    def __init__(self, serialport, nports=6):
        self.ser = serial.Serial(serialport, baudrate=9600,
                                 parity=serial.PARITY_NONE,
                                 stopbits=serial.STOPBITS_ONE,
                                 bytesize=serial.EIGHTBITS,
                                 timeout=3,
                                 write_timeout=3)
        self._rdat = None
        self.portnums = list(range(1, nports + 1))

    def _read_v2(self, size):
        rdat = self.ser.read(size)
        readsize = len(rdat)
        if readsize != size:
            raise RuntimeError(f'expected {size} bytes but read {readsize}')
        return rdat

    def _write(self, msg):
        if not isinstance(msg, str):
            raise TypeError
        s = f'{msg}\n'.encode()
        self.ser.write(s)
        while self.ser.out_waiting > 0:
            time.sleep(0.1)

    def _get_status(self):
        self._write("PA")
        rdat = self._read_v2(size=16)
        self._rdat = rdat.decode()

    def get_port(self, usbnum):
        """Get the usb port status: 1=ON, 0=OFF."""
        if usbnum not in (1, 2, 3, 4, 5, 6):
            raise ValueError(f'USB port {usbnum} out of range')
        self.ser.reset_output_buffer()
        self.ser.reset_input_buffer()
        self._get_status()
        i = usbnum2dati(usbnum)
        ret = int(self._rdat[i])
        return ret

    def set_port(self, usbnum, x):
        """Set the usb port status: 1=ON, 0=OFF."""
        if usbnum not in (1, 2, 3, 4, 5, 6):
            raise ValueError(f'USB port {usbnum} out of range')
        if x not in (0, 1):
            raise ValueError(f'Bad setting: {x}.'
                             f' USB port setting must be 0 or 1.')
        self.ser.reset_output_buffer()
        self.ser.reset_input_buffer()
        msg = f'U{usbnum}:{x}'
        self._write(msg)
        # read back the confirmation
        conf = (self._read_v2(6)).decode().strip()
        if conf != msg:
            raise RuntimeError(f'set_port failed. Wanted: {msg}, got: {conf}')


def usbnum2dati(usbnum):
    return 7 + usbnum


if __name__ == '__main__':
    main()
