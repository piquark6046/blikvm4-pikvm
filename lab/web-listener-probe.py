#!/usr/bin/env python3
"""Bridge-side reachability checks for the isolated target, not a LAN scan."""
import json
import socket
import time


def probe():
    result={'result':'failed','target':'192.168.88.2','probes':[]}
    for port in (22,80,443,8000,8080):
        with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as client:
            client.settimeout(2)
            start=time.monotonic()
            rc=client.connect_ex((result['target'],port))
            result['probes'].append({'port':port,'connect_errno':rc,
                                     'elapsed':time.monotonic()-start})
            assert (rc==0)==(port==22),result
    result['result']='passed'
    return result


if __name__=='__main__':
    print(json.dumps(probe()))
