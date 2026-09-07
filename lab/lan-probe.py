#!/usr/bin/env python3
"""Direct bridge probes: exact path, source filtering and normal TLS verification."""
import argparse
import hashlib
import json
from pathlib import Path
import socket
import ssl
import subprocess
import time

p=argparse.ArgumentParser()
p.add_argument('--known-hosts',required=True)
p.add_argument('--private-dir',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args(); a.output.mkdir(exist_ok=False,parents=True)
ssh=['ssh','-i','/home/user/.local/share/blikvm-m7/id_ed25519','-o','BatchMode=yes',
     '-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+a.known_hosts,'blikvm@192.168.88.2']
r={'result':'failed','path':'bridge enp1s0 192.168.88.1 -> target eth0 192.168.88.2',
   'tunnel':False,'probes':[],'tls':[]}
added=False

def target(command):
    return subprocess.check_output(ssh+[command],text=True,timeout=30)

def counters():
    return json.loads(target('sudo -n nft -j list ruleset'))

def drops(value):
    return sum(e['counter']['packets'] for item in value['nftables'] if 'rule' in item
               for e in item['rule']['expr'] if 'counter' in e
               and any('drop' in x for x in item['rule']['expr']))

def probe(source,port,expect):
    with socket.socket() as s:
        s.settimeout(2);s.bind((source,0));start=time.monotonic()
        rc=s.connect_ex(('192.168.88.2',port))
        r['probes'].append({'source':source,'destination':'192.168.88.2','port':port,
                            'errno':rc,'seconds':time.monotonic()-start})
        assert (rc==0)==expect,r['probes'][-1]
try:
    r['host_interfaces']=subprocess.check_output(['ip','-br','addr'],text=True)
    r['route']=subprocess.check_output(['ip','route','get','192.168.88.2'],text=True)
    before=counters()
    for port in (22,80,443,8000,8080):probe('192.168.88.1',port,port in (22,443))
    # Temporary denied address has an ordinary return route; a timeout alone is insufficient.
    subprocess.run(['ip','addr','add','192.168.88.99/32','dev','enp1s0'],check=True)
    added=True
    unauthorized_before=counters()
    probe('192.168.88.99',443,False)
    unauthorized_after=counters()
    assert drops(unauthorized_after)>drops(unauthorized_before), 'no firewall drop evidence'
    # Target loopback is not an approved HTTPS ingress interface.
    local=target("python3 -c 'import socket; s=socket.socket(); s.settimeout(2); print(s.connect_ex((\"192.168.88.2\",443)))'")
    assert int(local.strip())!=0
    r['target_loopback_denial_errno']=int(local.strip())
    r['firewall_before']=before;r['firewall_after']=counters()
    assert drops(r['firewall_after'])>drops(before)
    pem=(a.private_dir/'server.crt').read_text()
    expected=hashlib.sha256(ssl.PEM_cert_to_DER_cert(pem)).hexdigest()
    for version in (ssl.TLSVersion.TLSv1_2,ssl.TLSVersion.TLSv1_3):
        for identity in ('blikvm-v4.lab','192.168.88.2'):
            ctx=ssl.create_default_context(cafile=str(a.private_dir/'ca.crt'))
            ctx.minimum_version=ctx.maximum_version=version
            with socket.create_connection(('192.168.88.2',443),timeout=5) as raw:
                with ctx.wrap_socket(raw,server_hostname=identity) as s:
                    cert=s.getpeercert();digest=hashlib.sha256(s.getpeercert(binary_form=True)).hexdigest()
                    assert digest==expected
                    assert ssl.cert_time_to_seconds(cert['notBefore'])<=time.time()<ssl.cert_time_to_seconds(cert['notAfter'])
                    r['tls'].append({'identity':identity,'version':s.version(),'sha256':digest,'certificate':cert,
                                     'source':s.getsockname(),'verified':True})
    for label,identity,ca in [('wrong-name','wrong.blikvm-v4.lab',str(a.private_dir/'ca.crt')),
                              ('untrusted','blikvm-v4.lab',None)]:
        ctx=ssl.create_default_context(cafile=ca)
        try:
            with socket.create_connection(('192.168.88.2',443),timeout=5) as raw:
                with ctx.wrap_socket(raw,server_hostname=identity): pass
        except ssl.SSLCertVerificationError as e:
            r['tls'].append({'negative':label,'rejected':True,'reason':e.verify_message})
        else: raise AssertionError(label+' accepted')
    r['result']='passed'
except Exception as e:r['error']=str(e)
finally:
    if added:subprocess.run(['ip','addr','del','192.168.88.99/32','dev','enp1s0'],check=True)
    (a.output/'result.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps({'result':r['result'],'error':r.get('error')}))
raise SystemExit(r['result']!='passed')
