#!/usr/bin/env python3
"""Fixed harmless retention load: 32 unique 384-hex-character messages/second."""
import hashlib,syslog,time
syslog.openlog('m8f2-retention',syslog.LOG_PID,syslog.LOG_USER)
start=time.monotonic()
for i in range(32*7500):
 payload=''.join(hashlib.sha256(f'm8f2:{i}:{n}'.encode()).hexdigest() for n in range(6))
 syslog.syslog(syslog.LOG_INFO,f'probe={i:010d} payload={payload}')
 time.sleep(max(0,start+(i+1)/32-time.monotonic()))
