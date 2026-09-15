#!/usr/bin/env python3
"""Independent declarative replay; does not import the candidate classifier."""
import re


def verify(rows, *, offline=False):
    if not rows: return False, []
    valid=True
    try:
        ts=[int(x['__MONOTONIC_TIMESTAMP']) for x in rows]
        if ts!=sorted(ts) or min(ts)<0:valid=False
        boots={x['_BOOT_ID'] for x in rows}
        if len(boots)!=1 or not re.fullmatch('[0-9a-f]{32}',next(iter(boots))):valid=False
        if any(not isinstance(x.get('MESSAGE'),str) or not 0<=int(x['PRIORITY'])<=7 for x in rows):valid=False
    except (KeyError,ValueError,TypeError):return False, []
    if not valid:return False, []
    messages=[x['MESSAGE'] for x in rows]
    units=[x.get('_SYSTEMD_UNIT') for x in rows]
    def select(unit,text):return [i for i,m in enumerate(messages) if units[i]==unit and m==text]
    nginx=select('init.scope','Started nginx.service - BliKVM loopback HTTPS Web UI.')
    kvmd=select('init.scope','Started kvmd.service - BliKVM video-only kvmd.')
    ready=select('kvmd.service','kvmd.htserver                     INFO --- ======== Running on http://unix:/run/kvmd/api/kvmd.sock: ========')
    if len(nginx)!=1 or len(kvmd)!=1 or len(ready)!=1:valid=False
    for unit in ('nginx.service','kvmd.service'):
        if len({r['_SYSTEMD_INVOCATION_ID'] for r in rows if r.get('_SYSTEMD_UNIT')==unit and '_SYSTEMD_INVOCATION_ID' in r})>1:valid=False
    for u,m in zip(units,messages):
        if u=='init.scope' and any(s in m for s in ('nginx.service','kvmd.service')) and any(s in m for s in ('Stopping ','Stopped ','Failed','Main process exited','Scheduled restart','Deactivated')):valid=False
    auth=[];removed=[];success=[];types={};pair={};candidates=[]
    for i,(u,m) in enumerate(zip(units,messages)):
        if int(rows[i]['PRIORITY'])<=3 or re.search(r'\b(?:ERROR|CRITICAL)\b|Traceback|\[(?:error|crit)\]|segfault|EXT4-fs error|I/O error|Buffer I/O|Kernel panic|Oops:|checksum error',m):candidates.append(i)
        if u=='kvmd.service':
            event=re.fullmatch(r"kvmd\.apps\.kvmd\.auth\s+INFO --- Logged (in|out) user '([^']+)'; (expire=INF, sessions_now|sessions_closed)=\d+",m)
            if event and ((event[1]=='in')==(event[3]=='expire=INF, sessions_now')):auth.append((i,event[1],event[2]))
            if re.fullmatch(r"kvmd\.apps\.kvmd\.server\s+INFO --- Removed client socket: WsSession\(id=\d+, \{'stream': (True|False)\}\); clients now: \d+",m):removed.append(i)
            if re.fullmatch(r"aiohttp\.access\s+INFO --- \[[^\]\n]+\] 'GET /auth/check HTTP/1.1' => 200; size=\d+ --- referer='[^'\n]*'; user_agent='[^'\n]*'",m):success.append(i)
        if u!='nginx.service':continue
        header=re.fullmatch(r'(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}) \[(crit|error)\] (\d+#\d+): \*(\d+) (.*)',m)
        if not header:continue
        body=header[5];suffix=', client: 192.168.88.1, server: blikvm-v4.lab, request: "GET / HTTP/1.1"'
        socket='connect() to unix:/run/kvmd/api/kvmd.sock failed (2: No such file or directory) while connecting to upstream'+suffix+', subrequest: "/auth_check", upstream: "http://unix:/run/kvmd/api/kvmd.sock:/auth/check", host: "blikvm-v4.lab"'
        auth502='auth request unexpected status: 502 while sending to client'+suffix+', host: "blikvm-v4.lab"'
        if body==socket and header[2]=='crit':types[i]='socket';pair[i]=(header[3],header[4])
        if body==auth502 and header[2]=='error':types[i]='auth';pair[i]=(header[3],header[4])
        for query in ('','?stream=false'):
            reset='recv() failed (104: Connection reset by peer) while proxying upgraded connection, client: 192.168.88.1, server: blikvm-v4.lab, request: "GET /api/ws'+query+' HTTP/1.1", upstream: "http://unix:/run/kvmd/api/kvmd.sock:/ws'+query+'", host: "blikvm-v4.lab"'
            if body==reset and header[2]=='error':types[i]='reset'
    if len(ready)==1:
        if len(kvmd)==1 and ts[kvmd[0]]>=ts[ready[0]]:valid=False
        if not any(ts[i]>ts[ready[0]] for i in success):valid=False
        if not any(t=='in' and ts[i]>ts[ready[0]] for i,t,_ in auth):valid=False
    offline_proof=[]
    if offline:
        wanted=[('init.scope','Starting systemd-networkd-wait-online.service - Wait for Network to be Online...'),
                ('systemd-networkd-wait-online.service','Timeout occurred while waiting for network connectivity.'),
                ('init.scope','Failed to start systemd-networkd-wait-online.service - Wait for Network to be Online.'),
                ('ssh.service','Server listening on 192.168.88.2 port 22.'),
                ('systemd-networkd.service','eth0: Gained carrier')]
        matches=[select(u,m) for u,m in wanted]
        if all(len(m)==1 for m in matches):
            points=[m[0] for m in matches]
            if all(ts[points[n]]<ts[points[n+1]] for n in range(4)):offline_proof=points
    output=[]
    for i in candidates:
        result='REJECTED';w=[]
        if len(ready)==len(nginx)==len(kvmd)==1:
            kind=types.get(i)
            if kind in ('socket','auth'):
                partners=[j for j,k in types.items() if k==('auth' if kind=='socket' else 'socket') and pair[j]==pair[i] and (ts[i]<=ts[j] if kind=='socket' else ts[j]<=ts[i])]
                if len(partners)==1 and all(max(ts[nginx[0]],ts[kvmd[0]])<ts[j]<ts[ready[0]] for j in (i,partners[0])):
                    result='STARTUP_CAUSAL';w=[nginx[0],kvmd[0],partners[0],ready[0]]+[j for j in success if ts[j]>ts[ready[0]]][:1]
            if kind=='reset' and ts[i]>max(ts[ready[0]],ts[nginx[0]]):
                left=[e for e in auth if ts[e[0]]<ts[i]];right=[e for e in auth if ts[e[0]]>ts[i]]
                if left and right:
                    lo,li=left[-1],right[0];rm=[j for j in removed if ts[lo[0]]<=ts[j]<ts[li[0]]]
                    if lo[1]=='out' and li[1]=='in' and lo[2]==li[2] and rm:result='LOGOUT_RESET_CAUSAL';w=[ready[0],lo[0],rm[0],li[0]]
        if offline_proof and i in offline_proof[1:3] and int(rows[i]['PRIORITY'])==3:
            result='EXPECTED_OFFLINE_TIMEOUT';w=offline_proof
        output.append((i,result,w))
        if result=='REJECTED':valid=False
    return valid,output
