import json,tarfile,shlex,hashlib
from pathlib import Path
records=[]
for i in range(1,4):
 name=f'minimal-{i:03d}'
 with tarfile.open(f'out/p3-h5r1/{name}.tar.gz') as t:
  read=lambda n:json.load(t.extractfile(n))
  r=read('controller/'+name+'/result.json')
  c=read('sealed/'+Path(r['leaf']).name+'/launch-contract.json')
  argv=shlex.split(r['generated_argv_lines'][0].split('<launching> ',1)[1])
  tmp=[a for a in argv if a.startswith('--user-data-dir=')]
  assert len(tmp)==1 and tmp[0].startswith('--user-data-dir=/tmp/playwright_chromiumdev_profile-')
  argv=[a for a in argv if not a.startswith('--user-data-dir=')]
  env=c['full_environment'].copy()
  ephemeral={k:env.pop(k) for k in ['DISPLAY','XAUTHORITY','H5R1_LEAF','H5R1_REQUIREMENTS','H5R1_NETNS_EXPECTED']}
  expected=json.loads(ephemeral['H5R1_NETNS_EXPECTED'])
  assert expected['netns']!=expected['host_netns'] and expected['sockets']==[]
  records.append({'name':name,'stable':{'contract':c['frozen_contract'],'argv':argv,'environment':env,'cwd':c['cwd'],'uid':c['uid'],'gid':c['gid'],'groups':c['groups']},'ephemeral_keys':list(ephemeral),'profile_flag_class':'--user-data-dir=/tmp/playwright_chromiumdev_profile-*'})
assert records[0]['stable']==records[1]['stable']==records[2]['stable']
print(json.dumps({'result':'THREE_MINIMAL_CONTRACTS_MATCH','runs':[x['name'] for x in records],
 'stable_sha256':hashlib.sha256(json.dumps(records[0]['stable'],sort_keys=True).encode()).hexdigest(),
 'stable_properties':['runtime identities','Playwright generated flags','uid/gid/groups','environment','cwd','Xvfb arguments'],
 'ephemeral_environment_keys':records[0]['ephemeral_keys'],'ephemeral_profile_flag':records[0]['profile_flag_class'],
 'qualification_credit':0},indent=2))
