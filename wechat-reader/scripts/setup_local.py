"""Configure this skill copy using target-machine paths; never access WeChat."""
import argparse
import json
from pathlib import Path
import struct
import platform
import sys


def configure(bundle, db_root, settings_path, wechat_exe='', cli_dir=None):
    if sys.platform not in ('win32','darwin') or struct.calcsize('P') != 8:
        raise ValueError('Requires 64-bit Windows or Apple Silicon macOS')
    if sys.platform=='darwin' and platform.machine().lower()!='arm64':
        raise ValueError('Requires native Apple Silicon Python; Intel/Rosetta is not supported')
    bundle, db_root = Path(bundle).resolve(), Path(db_root).resolve()
    required = ['wechat-cli-installed/wechat-cli.exe', 'wechat-cli-installed/libWCDB.dll',
                'wechat-cli-installed/wechat-key-check.exe', 'wechat-key-helper/check.py']
    runtime=Path(cli_dir).expanduser().resolve() if cli_dir else Path.home()/'.local/share/wechat-cli'
    available=(all((runtime/p).is_file() for p in ('wechat-cli','libWCDB.dylib','wxkey')) if sys.platform=='darwin'
               else all((bundle/p).is_file() for p in required))
    if not available:
        raise ValueError('Runtime files missing; skill files alone are insufficient')
    if not (db_root / 'db_storage').is_dir():
        raise ValueError('Account directory must directly contain db_storage')
    cfg = {'workspace': str(bundle), 'cli': str(bundle/'wechat-cli-installed/wechat-cli.exe'),
           'python': sys.executable, 'key_helper': str(bundle/'wechat-key-helper/check.py'),
           'image_helper': str(bundle/'wechat-key-helper/image_check.py'),
           'db_root': str(db_root), 'wechat_exe': wechat_exe, 'card_template': ''}
    if sys.platform=='darwin':
        cfg.update(cli=str(runtime/'wechat-cli'),key_helper='',image_helper='',platform='darwin-arm64')
    settings_path = Path(settings_path)
    if settings_path.exists():
        backup = settings_path.with_name('local-settings.before-setup.json')
        if backup.exists():
            raise ValueError('Existing setup backup found; review it before overwriting settings')
        backup.write_bytes(settings_path.read_bytes())
    settings_path.write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle-root',required=True,type=Path)
    parser.add_argument('--db-root',required=True,type=Path)
    parser.add_argument('--wechat-exe',default='')
    parser.add_argument('--cli-dir',type=Path)
    parser.add_argument('--confirm-setup',action='store_true')
    args=parser.parse_args()
    if not args.confirm_setup:
        parser.error('Explicit setup authorization is required; nothing changed')
    try:
        configure(args.bundle_root,args.db_root,Path(__file__).resolve().parents[1]/'references/local-settings.json',args.wechat_exe,args.cli_dir)
        print('Configured local paths only; WeChat has not been accessed')
    except (ValueError,OSError):
        print('Setup not completed: check platform, required files, directory and backup',file=sys.stderr)
        sys.exit(1)
