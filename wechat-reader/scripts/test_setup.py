import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import setup_local
from setup_local import configure


class SetupTests(unittest.TestCase):
    def test_apple_silicon_uses_native_runtime_without_windows_helpers(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);runtime=root/'mac-runtime';runtime.mkdir()
            for name in ('wechat-cli','libWCDB.dylib','wxkey'):(runtime/name).write_text('fixture')
            account=root/'account';(account/'db_storage').mkdir(parents=True)
            with mock.patch.object(setup_local.sys,'platform','darwin'),mock.patch.object(setup_local.platform,'machine',return_value='arm64'):
                configure(root,account,root/'settings.json',cli_dir=runtime)
            cfg=json.loads((root/'settings.json').read_text(encoding='utf-8'))
            self.assertEqual(Path(cfg['cli']),runtime/'wechat-cli')
            self.assertEqual(cfg['key_helper'],'')

    def test_intel_mac_refused_before_creating_configuration(self):
        with mock.patch.object(setup_local.sys,'platform','darwin'),mock.patch.object(setup_local.platform,'machine',return_value='x86_64'):
            with self.assertRaises(ValueError):configure('unused','unused','unused.json')

    def test_setup_uses_target_machine_and_preserves_previous_settings(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            for name in ('wechat-cli-installed/wechat-cli.exe','wechat-cli-installed/libWCDB.dll',
                         'wechat-cli-installed/wechat-key-check.exe','wechat-key-helper/check.py'):
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('fixture')
            account=root/'account';(account/'db_storage').mkdir(parents=True)
            settings=root/'local-settings.json';settings.write_text('{"previous":true}')
            configure(root,account,settings)
            result=json.loads(settings.read_text(encoding='utf-8'))
            self.assertEqual(Path(result['db_root']),account)
            self.assertTrue(json.loads((root/'local-settings.before-setup.json').read_text())['previous'])
            with self.assertRaises(ValueError): configure(root,account,settings)

    def test_incomplete_runtime_does_not_create_configuration(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);settings=root/'settings.json'
            with self.assertRaises(ValueError): configure(root,root,settings)
            self.assertFalse(settings.exists())
