"""Scope and preservation gates for the M8-B derivative package."""
import hashlib
from pathlib import Path
import re
import runpy
import unittest

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT/'build/kvmd-web'


class WebPackageTests(unittest.TestCase):
    def test_only_explicit_loopback_tls_listener(self):
        config = (WEB/'nginx.conf').read_text()
        listeners = re.findall(r'\blisten\s+([^;]+);', config)
        self.assertEqual(listeners, ['127.0.0.1:443 ssl'])
        self.assertIn('auth_request /auth_check;', config)
        self.assertIn('internal;', config)
        self.assertIn('proxy_pass http://kvmd/auth/check;', config)
        self.assertNotIn('include /etc/nginx/sites', config)

    def test_frozen_capture_implementation_is_not_patched(self):
        patch = (WEB/'web-auth.patch').read_text()
        changed = re.findall(r'^\+\+\+ b/(.+)$', patch, re.M)
        self.assertEqual(set(changed), {
            'kvmd/apps/kvmd/__init__.py', 'kvmd/apps/kvmd/server.py',
            'kvmd/apps/kvmd/info/__init__.py', 'web/share/js/index/main.js',
            'web/share/js/kvm/stream.js', 'web/share/js/kvm/session.js',
        })
        for line in patch.splitlines():
            if line.startswith('+') and not line.startswith('+++'):
                self.assertNotRegex(line, r'\b(HidApi|MsdApi|AtxApi|UserGpio|Switch)\(')
        self.assertIn('+        await check_request_auth(self.__auth, exposed, req)', patch)
        self.assertIn('+        self.__auth.start_ws_session(ws.token)', patch)

    def test_socket_paths_and_device_access(self):
        nginx = (WEB/'nginx.conf').read_text()
        for path in ('/run/kvmd/api/kvmd.sock', '/run/kvmd/ustreamer/ustreamer.sock'):
            self.assertIn('unix:'+path, nginx)
        service = (WEB/'kvmd-web.conf').read_text()
        self.assertNotIn('Group=', service)
        self.assertNotIn('/dev/', service)
        self.assertIn('setfacl', service)

    def test_patch_digest(self):
        pin = dict(line.split('=', 1) for line in (WEB/'versions.env').read_text().splitlines())
        self.assertEqual(pin['WEB_PATCH_SHA256'], hashlib.sha256((WEB/'web-auth.patch').read_bytes()).hexdigest())

    def test_private_overlay_encodes_owner_modes(self):
        newc = runpy.run_path(str(WEB/'provision.py'))['newc']
        data = newc([('etc/test-secret', b'example', 0o100600, 0, 0)])
        self.assertEqual(data[:6], b'070701')
        fields = [int(data[6+i*8:14+i*8], 16) for i in range(13)]
        self.assertEqual(fields[1:4], [0o100600, 0, 0])
        self.assertEqual(fields[6], 7)
        self.assertEqual(len(data) % 512, 0)


if __name__ == '__main__':
    unittest.main()
