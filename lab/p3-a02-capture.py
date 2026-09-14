"""Passive bounded UART recorder which survives power/UART hotplug together."""
import contextlib,datetime,fcntl,json,os,select,termios,time,tty
from pathlib import Path
import sys
D=Path(sys.argv[1])
P=Path('/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0')
def stamp():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def main():
 D.mkdir(mode=0o700,exist_ok=False)
 deadline=time.monotonic()+600;segment=0;total=0
 with (D/'events.jsonl').open('x',buffering=1) as events:
  def event(kind,**kw):events.write(json.dumps(dict(utc=stamp(),monotonic_ns=time.monotonic_ns(),event=kind,**kw))+'\n')
  (D/'ready.json').write_text(json.dumps(dict(pid=os.getpid(),started_utc=stamp(),uart=str(P),baud=115200,format='8N1',passive=True,duration_seconds=600,hotplug_retry=True,early_firmware_capture='FULL_CHAIN_REQUIRED',qualification_credit=False,scope='P3-A attempt 02 cycle 1 continuous UART capture')))
  event('watcher_ready')
  while time.monotonic()<deadline and not (D/'STOP').exists():
   if not P.exists():time.sleep(.02);continue
   fd=None;old=None
   try:
    fd=os.open(P,os.O_RDONLY|os.O_NOCTTY|os.O_NONBLOCK)
    fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    fcntl.ioctl(fd,termios.TIOCEXCL)
    old=termios.tcgetattr(fd);tty.setraw(fd,termios.TCSANOW)
    a=termios.tcgetattr(fd);a[2]&=~(termios.CSIZE|termios.PARENB|termios.CSTOPB|termios.CRTSCTS);a[2]|=termios.CS8|termios.CLOCAL|termios.CREAD;a[4]=a[5]=termios.B115200
    termios.tcsetattr(fd,termios.TCSANOW,a)
    segment+=1;event('uart_open',segment=segment,resolved=str(P.resolve()))
    with (D/f'uart-{segment:03}.raw').open('xb',buffering=0) as raw:
     while time.monotonic()<deadline and not (D/'STOP').exists():
      if not select.select([fd],[],[],.25)[0]:continue
      b=os.read(fd,65536)
      if not b:raise OSError('UART EOF/disconnected')
      raw.write(b);total+=len(b);event('rx',segment=segment,bytes=len(b),data=b.decode('utf-8','backslashreplace'))
   except (OSError,termios.error) as exc:event('uart_unavailable',segment=segment,error=str(exc));time.sleep(.1)
   finally:
    if fd is not None:
     if old is not None:
      with contextlib.suppress(OSError,termios.error):termios.tcsetattr(fd,termios.TCSANOW,old)
     with contextlib.suppress(OSError):fcntl.ioctl(fd,termios.TIOCNXCL)
     os.close(fd)
  event('watcher_finished',segments=segment,bytes=total)
if __name__=='__main__':main()
