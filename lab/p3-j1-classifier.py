#!/usr/bin/env python3
"""Pure causal journal classifier. Never grants qualification credit."""
import re

SIGNAL = re.compile(r'\bERROR\b|\bCRITICAL\b|Traceback|\[error\]|\[crit\]|segfault|EXT4-fs error|I/O error|Buffer I/O|Kernel panic|Oops:|checksum error')
READY = 'kvmd.htserver                     INFO --- ======== Running on http://unix:/run/kvmd/api/kvmd.sock: ========'
STARTS = {'nginx.service':'Started nginx.service - BliKVM loopback HTTPS Web UI.',
          'kvmd.service':'Started kvmd.service - BliKVM video-only kvmd.'}
PREFIX = r'\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[(?P<level>crit|error)\] (?P<worker>\d+#\d+): \*(?P<connection>\d+) '
TAIL = r', client: 192\.168\.88\.1, server: blikvm-v4\.lab, request: "GET / HTTP/1\.1"'
SOCKET = re.compile(PREFIX + re.escape('connect() to unix:/run/kvmd/api/kvmd.sock failed (2: No such file or directory) while connecting to upstream') + TAIL + re.escape(', subrequest: "/auth_check", upstream: "http://unix:/run/kvmd/api/kvmd.sock:/auth/check", host: "blikvm-v4.lab"'))
AUTH502 = re.compile(PREFIX + re.escape('auth request unexpected status: 502 while sending to client') + TAIL + re.escape(', host: "blikvm-v4.lab"'))
RESET = re.compile(PREFIX + re.escape('recv() failed (104: Connection reset by peer) while proxying upgraded connection, client: 192.168.88.1, server: blikvm-v4.lab, request: "GET /api/ws') + r'(?P<query>\?stream=false)?' + re.escape(' HTTP/1.1", upstream: "http://unix:/run/kvmd/api/kvmd.sock:/ws') + r'(?P=query)' + re.escape('", host: "blikvm-v4.lab"'))
# Optional empty captures need an explicit empty alternative for backreferences.
RESET = re.compile(RESET.pattern.replace(r'(?P<query>\?stream=false)?',r'(?P<query>\?stream=false|)'))
LOGIN = re.compile(r"kvmd\.apps\.kvmd\.auth +INFO --- Logged in user '([^']+)'; expire=INF, sessions_now=\d+")
LOGOUT = re.compile(r"kvmd\.apps\.kvmd\.auth +INFO --- Logged out user '([^']+)'; sessions_closed=\d+")
REMOVED = re.compile(r"kvmd\.apps\.kvmd\.server +INFO --- Removed client socket: WsSession\(id=\d+, \{'stream': (?:True|False)\}\); clients now: \d+")
SUCCESS = re.compile(r"aiohttp\.access +INFO --- \[[^\]\n]+\] 'GET /auth/check HTTP/1\.1' => 200; size=\d+ --- referer='[^'\n]*'; user_agent='[^'\n]*'")

OFFLINE = (
 ('init.scope', 'Starting systemd-networkd-wait-online.service - Wait for Network to be Online...'),
 ('systemd-networkd-wait-online.service', 'Timeout occurred while waiting for network connectivity.'),
 ('init.scope', 'Failed to start systemd-networkd-wait-online.service - Wait for Network to be Online.'),
 ('ssh.service', 'Server listening on 192.168.88.2 port 22.'),
 ('systemd-networkd.service', 'eth0: Gained carrier'),
)


def classify(journal, *, offline=False):
    """Return every candidate and exact witness indices. Unknowns fail closed."""
    def fail(reason):return {'result':'REJECTED','reason':reason,'records':[],'qualification_credit':0}
    if not journal:return fail('empty journal')
    try:
        stamps=[int(e['__MONOTONIC_TIMESTAMP']) for e in journal]
        boots={e['_BOOT_ID'] for e in journal}
        if len(boots)!=1 or not re.fullmatch('[0-9a-f]{32}',next(iter(boots))):return fail('mixed/invalid boot')
        if stamps!=sorted(stamps) or min(stamps)<0:return fail('invalid causal order')
        if any(not isinstance(e.get('MESSAGE'),str) or not 0<=int(e['PRIORITY'])<=7 for e in journal):return fail('invalid message/priority')
    except (KeyError,ValueError,TypeError):return fail('missing trusted journal fields')
    def msg(i):return journal[i]['MESSAGE']
    def unit(i,u):return journal[i].get('_SYSTEMD_UNIT')==u
    def witness(i):return {'index':i,'timestamp_us':stamps[i],'unit':journal[i].get('_SYSTEMD_UNIT'),'message':msg(i)}
    def indices(u,pattern):return [i for i in range(len(journal)) if unit(i,u) and pattern.fullmatch(msg(i))]
    starts={u:[i for i in range(len(journal)) if unit(i,'init.scope') and msg(i)==m] for u,m in STARTS.items()}
    ready=[i for i in range(len(journal)) if unit(i,'kvmd.service') and msg(i)==READY]
    problems=[]
    if any(len(x)!=1 for x in starts.values()) or len(ready)!=1:problems.append('missing/duplicate unit-start or readiness witness')
    for u in STARTS:
        invocations={e['_SYSTEMD_INVOCATION_ID'] for e in journal if e.get('_SYSTEMD_UNIT')==u and '_SYSTEMD_INVOCATION_ID' in e}
        if len(invocations)>1:problems.append('service invocation changed: '+u)
    for e in journal:
        m=e['MESSAGE']
        if e.get('_SYSTEMD_UNIT')=='init.scope' and re.search(r'(?:nginx|kvmd)\.service',m) and re.search(r'Stopping |Stopped |Failed|Main process exited|Scheduled restart|Deactivated',m):problems.append('service lifecycle recovery')
    successes=indices('kvmd.service',SUCCESS);logins=indices('kvmd.service',LOGIN)
    if len(ready)==1:
        if len(starts['kvmd.service'])==1 and stamps[starts['kvmd.service'][0]]>=stamps[ready[0]]:problems.append('kvmd readiness precedes service start')
        if not any(stamps[i]>stamps[ready[0]] for i in successes):problems.append('no subsequent auth/check 200')
        if not any(stamps[i]>stamps[ready[0]] for i in logins):problems.append('no subsequent login')
    offline_matches=[[i for i,e in enumerate(journal) if e.get('_SYSTEMD_UNIT')==u and e['MESSAGE']==m] for u,m in OFFLINE]
    offline_witnesses=[]
    if offline and all(len(x)==1 for x in offline_matches):
        possible=[x[0] for x in offline_matches]
        if all(stamps[x]<stamps[y] for x,y in zip(possible,possible[1:])):offline_witnesses=possible
    candidates=[i for i,e in enumerate(journal) if SIGNAL.search(e['MESSAGE']) or int(e['PRIORITY'])<=3]
    records=[];auth=sorted(logins+indices('kvmd.service',LOGOUT));removed=indices('kvmd.service',REMOVED)
    for i in candidates:
        m=msg(i);s=SOCKET.fullmatch(m);a=AUTH502.fullmatch(m);r=RESET.fullmatch(m)
        kind='REJECTED';why='unknown error/high-severity record';ws=[]
        if offline_witnesses and i in offline_witnesses[1:3] and int(journal[i]['PRIORITY'])==3:
            kind='EXPECTED_OFFLINE_TIMEOUT';why='inherited offline timeout before SSH bind and first Ethernet carrier';ws=offline_witnesses
        elif unit(i,'nginx.service') and (s or a):
            match=s or a
            expected_level='crit' if s else 'error'
            peers=[]
            for j in candidates:
                other=(AUTH502 if s else SOCKET).fullmatch(msg(j))
                if unit(j,'nginx.service') and other and all(other[k]==match[k] for k in ('worker','connection')) and (stamps[i]<=stamps[j] if s else stamps[j]<=stamps[i]):peers.append(j)
            if len(ready)==1 and all(len(x)==1 for x in starts.values()) and match['level']==expected_level and len(peers)==1:
                bracket=[v[0] for v in starts.values()];end=ready[0];j=peers[0]
                if all(stamps[b]<stamps[i]<stamps[end] and stamps[b]<stamps[j]<stamps[end] for b in bracket):
                    kind='STARTUP_CAUSAL';why='exact paired ENOENT/auth error between both unit starts and kvmd listener readiness';ws=bracket+[j,end]+[x for x in successes if stamps[x]>stamps[end]][:1]
                else:why='startup class outside causal readiness bracket'
            else:why='startup unit/pair/level/readiness witnesses incomplete'
        elif unit(i,'nginx.service') and r and r['level']=='error':
            before=[x for x in auth if stamps[x]<stamps[i]];after=[x for x in auth if stamps[x]>stamps[i]]
            if before and after and len(ready)==1 and len(starts['nginx.service'])==1 and max(stamps[ready[0]],stamps[starts['nginx.service'][0]])<stamps[i]:
                lo,li=before[-1],after[0];lom=LOGOUT.fullmatch(msg(lo));lim=LOGIN.fullmatch(msg(li))
                rm=[x for x in removed if stamps[lo]<=stamps[x]<stamps[li]]
                if lom and lim and lom[1]==lim[1] and rm:
                    kind='LOGOUT_RESET_CAUSAL';why='exact websocket reset bracketed by same-user logout/login and kvmd removed-socket witness';ws=[ready[0],lo,rm[0],li]
                else:why='missing logout/reauth/removed-socket causal witness'
            else:why='missing logout/reauth/readiness causal bracket'
        records.append({**witness(i),'classification':kind,'reason':why,'witnesses':[witness(x) for x in ws]})
    if any(x['classification']=='REJECTED' for x in records):problems.append('unexplained candidate; no partial journal acceptance')
    return {'result':'REJECTED' if problems else 'JOURNAL_ELIGIBLE','reason':'; '.join(problems) or 'all candidates causally explained; downstream functional gates still mandatory','records':records,'qualification_credit':0}


def require_qualification(journal, *, https_passed, auth_passed, core_passed, generations_unchanged, offline=False):
    result=classify(journal,offline=offline)
    if result['result']!='JOURNAL_ELIGIBLE' or not all(x is True for x in (https_passed,auth_passed,core_passed,generations_unchanged)):
        raise ValueError('journal or downstream qualification prerequisite failed')
    return result
