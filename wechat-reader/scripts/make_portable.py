"""Build an allowlisted transfer kit without account data or local configuration."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile


def entries(skill, workspace):
    skill,workspace=Path(skill),Path(workspace)
    files={}
    allow=['SKILL.md','VERSION','CHANGELOG.md','agents/openai.yaml',
           'references/boundaries.md','references/setup.md','references/upgrades.md','references/macos.md',
           'scripts/reader.py','scripts/test_reader.py','scripts/test_setup.py','scripts/setup_local.py',
           'scripts/make_portable.py','scripts/verify_macos.py']
    for item in allow:
        files['wechat-reader/'+item]=(skill/item).read_bytes()
    files['wechat-reader/references/operations.md']=b'# Runtime limitations\n\nWindows x64 tested locally; macOS arm64 archive verified offline only. Image repair is Windows-only and unverified. See setup.md, macos.md and boundaries.md.\n'
    for item in ('wechat-cli-v2.0.2-darwin-arm64.zip','wechat-cli-v2.0.2-darwin-arm64.zip.sha256','source.json'):
        files['wechat-reader/assets/macos/'+item]=(skill/'assets/macos'/item).read_bytes()
    template={k:'' for k in ('workspace','cli','python','key_helper','image_helper','db_root','wechat_exe','card_template')}
    files['wechat-reader/references/local-settings.json']=json.dumps(template,indent=2).encode()
    for item in ('wechat-cli.exe','libWCDB.dll','wechat-key-check.exe','LICENSE','THIRD_PARTY_NOTICES.md','SECURITY.md'):
        files['wechat-cli-installed/'+item]=(workspace/'wechat-cli-installed'/item).read_bytes()
    for item in ('check.py','image_check.py','LICENSE','SOURCE.txt','wx4/__init__.py','wx4/key.py','wx4/common.py','wx4/media.py'):
        files['wechat-key-helper/'+item]=(workspace/'wechat-key-helper'/item).read_bytes()
    files['source/wechat-key-check/main.go']=(workspace/'wechat-cli-source/cmd/wechat-key-check/main.go').read_bytes()
    files['requirements-image.txt']=b'pycryptodomex==3.24.2\nPillow==13.0.0\n'
    return files


def build(skill,workspace,output):
    output=Path(output)
    if output.exists():raise ValueError('Refusing to overwrite an existing transfer kit')
    files=entries(skill,workspace)
    manifest={'skill_version':(Path(skill)/'VERSION').read_text().strip(),
              'runtime':'Windows x64 local preview 2.0.3-local.1 + official macOS arm64 2.0.2 (not runtime tested)',
              'source_base_commit':'00de55e7a87c4efe0527b06afffaf6e8b5c66143',
              'signature':'unsigned; hashes detect changes, not publisher identity',
              'files':{p:hashlib.sha256(data).hexdigest() for p,data in files.items()}}
    with zipfile.ZipFile(output,'x',zipfile.ZIP_DEFLATED) as archive:
        for path,data in files.items():archive.writestr(path,data)
        archive.writestr('package-manifest.json',json.dumps(manifest,indent=2))
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    manifest=build(Path(__file__).resolve().parents[1],args.workspace,args.output)
    print(json.dumps({'files':len(manifest['files']),'skill_version':manifest['skill_version'],'account_data_included':False}))
