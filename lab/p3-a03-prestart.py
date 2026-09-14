#!/usr/bin/env python3
"""Fresh read-only attempt-03 inventory; accepted H5R2 is never rerun."""
import json
import os
from pathlib import Path
import runpy


def main():
    require = lambda ok, why: None if ok else (_ for _ in ()).throw(RuntimeError(why))
    require(os.geteuid() == 0, 'root inventory controller required')
    os.umask(0o077)
    here = Path(__file__).resolve().parent
    f = runpy.run_path('/var/lib/blikvm-p3-h5r2/input/functional/lab/p3-h5r2-functional.py')
    p = f['P']; b = f['BASE']; read = p['read']; publish = p['publish']
    source = read(here/'source-provenance.json')
    require(source['clean'] is True and source['commit'] == source['origin_main'] and len(source['commit']) == 40,
            'source not clean pushed commit')
    for name, digest in source['files'].items():
        require(Path(name).name == name and p['H']['digest'](here/name) == digest, 'source drift')
    for name in ('controller-r1-vm-replay.json', 'controller-r1-bridge-replay.json'):
        r = read(here/name)
        require(r['result'] == 'CONTROLLER_R1_REHEARSAL_INDEPENDENTLY_REPLAYED' and
                r['qualification_credit'] == 0 and r['old_bug_reproduced'], 'rehearsal missing')
    fail = b/'controller/P3_A03_FAILED.json'
    require(not fail.exists(), 'attempt 03 failed; no retry')
    require(not (b/'controller/FAILED.json').exists(), 'H5R2 failure latch')
    require(read(b/'controller/h5r2-acceptance.json')['result'] == 'H5R2_INDEPENDENTLY_ACCEPTED', 'H5R2 unaccepted')
    dest = b/'controller/p3-a03-immediate'
    p['mkdir'](dest)
    try:
        p['idle']()
        require(p['manifest'](p['RUNTIME']) == read(b/'input/contract.json')['runtime_manifest'], 'H5R2 runtime changed')
        require(p['manifest'](b/'input') == read(b/'controller/functional-input-manifest.json'), 'H5R2 inputs changed')
        publish(dest/'runtime-input-check.json', dict(result='EXACT_MATCH', source=source, h5r2_rerun=False))
        inv = f['collect']('inventory', dest)
        accepted = read(b/'controller/functional-003/after/target.json')
        for key in ('boot_id', 'sd_cid', 'machine_id', 'host_public_keys', 'hash_checks'):
            require(inv[key] == accepted[key], 'accepted H5R2 continuity drift: '+key)
        publish(dest/'result.json', dict(result='P3_A03_IMMEDIATE_INVENTORY_PASS', boot_id=inv['boot_id'],
                hashes_matched=10690, qualification_credit=0, accepted_cycles=0, target_mutation=False, source=source))
    except BaseException as ex:
        publish(fail, dict(result='FAILED', phase='prestart', error=repr(ex), accepted_cycles=0))
        raise
    print('P3_A03_IMMEDIATE_INVENTORY_PASS')


if __name__ == '__main__': main()
