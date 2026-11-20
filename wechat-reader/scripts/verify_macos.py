"""Verify the pinned macOS archive without executing or extracting it."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile


def verify(archive):
    archive=Path(archive)
    expected=Path(str(archive)+'.sha256').read_text().split()[0].lower()
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=expected:raise ValueError('Archive SHA256 mismatch')
    with zipfile.ZipFile(archive) as z:
        names=z.namelist()
        if len(names)!=len(set(names)) or any('..' in PurePosixPath(n).parts or n.startswith('/') or '\\' in n or ':' in n for n in names):raise ValueError('Unsafe archive paths')
        prefix='wechat-cli-v2.0.2-darwin-arm64/'
        if not all(n.startswith(prefix) for n in names):raise ValueError('Unexpected archive root')
        m=json.loads(z.read(prefix+'release-manifest.json'))
        if m.get('version')!='2.0.2' or m.get('platform_arch')!='darwin-arm64' or m.get('source_repository')!='r266-tech/wx-cli':raise ValueError('Unexpected release identity')
        files={n[len(prefix):] for n in names if not n.endswith('/') and n!=prefix+'release-manifest.json'}
        if files!=set(m['artifacts']):raise ValueError('Manifest file set mismatch')
        for name,record in m['artifacts'].items():
            data=z.read(prefix+name)
            if len(data)!=record['bytes'] or hashlib.sha256(data).hexdigest()!=record['sha256']:raise ValueError('Artifact hash mismatch')
    return {'version':m['version'],'platform_arch':m['platform_arch'],'sha256':expected,
            'signing_mode':m['signing_mode'],'notarization_status':m['notarization_status'],
            'runtime_tested':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive',type=Path)
    print(json.dumps(verify(parser.parse_args().archive),indent=2))
