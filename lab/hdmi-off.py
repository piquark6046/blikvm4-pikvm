#!/usr/bin/env python3
"""Hold DRM master while disabling a verified HDMI connector's DPMS property.

A short-lived modetest write is insufficient: DRM last-close restores fbcon.
This process keeps the descriptor open until signalled, then restores DPMS On.
"""
import argparse
import ctypes
import ctypes.util
import os
import signal
import time


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--connector',type=int,required=True)
    p.add_argument('--property',type=int,required=True)
    a=p.parse_args()
    lib=ctypes.CDLL(ctypes.util.find_library('drm'),use_errno=True)
    lib.drmSetMaster.argtypes=[ctypes.c_int]
    lib.drmSetMaster.restype=ctypes.c_int
    lib.drmModeConnectorSetProperty.argtypes=[ctypes.c_int,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_uint64]
    lib.drmModeConnectorSetProperty.restype=ctypes.c_int
    fd=os.open('/dev/dri/card0',os.O_RDWR|os.O_CLOEXEC)
    def check(rc):
        if rc: raise OSError(ctypes.get_errno(),os.strerror(ctypes.get_errno()))
    def stop(_sig,_frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM,stop)
    try:
        check(lib.drmSetMaster(fd))
        check(lib.drmModeConnectorSetProperty(fd,a.connector,a.property,3))
        print('DPMS_OFF_HELD',flush=True)
        # Bounded fail-safe even if the parent disappears.
        deadline=time.monotonic()+45
        while time.monotonic()<deadline: time.sleep(.2)
    except KeyboardInterrupt:
        pass
    finally:
        check(lib.drmModeConnectorSetProperty(fd,a.connector,a.property,0))
        os.close(fd)


if __name__=='__main__': main()
