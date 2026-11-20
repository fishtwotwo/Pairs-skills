"""Local read-only WeChat entry point; no message storage unless --output is given."""
import argparse
import csv
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

ZONE = dt.timezone(dt.timedelta(hours=8), 'Asia/Shanghai')
SETTINGS = Path(__file__).resolve().parents[1] / 'references' / 'local-settings.json'


class ReaderError(Exception):
    def __init__(self, code, message, **details):
        self.payload = dict(code=code, message=message, **details)
        super().__init__(message)


def run(args, env, timeout=60):
    try:
        return subprocess.run([str(x) for x in args], env=env, capture_output=True,
                              encoding='utf-8', errors='replace', timeout=timeout,
                              creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0) if sys.platform=='win32' else 0)
    except subprocess.TimeoutExpired:
        raise ReaderError('timeout', '操作超时；停止自动重试。')
    except OSError:
        raise ReaderError('executable_unavailable', '运行文件缺失或不可访问。')


def call(cfg, env, *args, timeout=60):
    # Ordinary reads must not trigger native automatic key extraction/cache writes.
    flags = [] if args and args[0] == 'cache' else ['--strict-read-only']
    p = run([cfg['cli'], *flags, *args], env, timeout)
    try:
        result = json.loads(p.stdout)
    except (ValueError, TypeError):
        raise ReaderError('invalid_cli_output', 'CLI 未返回有效 JSON；原始日志未公开。')
    if not result.get('ok'):
        # Do not propagate raw error text: some underlying errors contain salts.
        code = result.get('error', {}).get('code', 'cli_failed')
        raise ReaderError(code, '微信读取失败；请先检查 status，必要时执行一次 repair。')
    return result.get('data', {})


def processes(env):
    if sys.platform == 'darwin':
        return sum(len(run(['pgrep','-x',name],env).stdout.splitlines()) for name in ('WeChat','Weixin'))
    p = run(['tasklist', '/FI', 'IMAGENAME eq Weixin.exe', '/FO', 'CSV', '/NH'], env)
    rows = list(csv.reader(p.stdout.splitlines()))
    found = [r for r in rows if len(r) > 1 and r[0].lower() in ('weixin.exe', 'wechat.exe')]
    if not found:
        p = run(['tasklist', '/FI', 'IMAGENAME eq WeChat.exe', '/FO', 'CSV', '/NH'], env)
        found = [r for r in csv.reader(p.stdout.splitlines()) if len(r)>1 and r[0].lower()=='wechat.exe']
    return len(found)


def status(cfg, env):
    snapshot = {'checked_at': dt.datetime.now(ZONE).isoformat(),
                'cli_exists': Path(cfg['cli']).is_file(),
                'platform': sys.platform,
                'dll_exists': Path(cfg['cli']).with_name('libWCDB.dylib' if sys.platform=='darwin' else 'libWCDB.dll').is_file(),
                'db_root': cfg['db_root'],
                'db_storage_exists': (Path(cfg['db_root'])/'db_storage').is_dir(),
                'wechat_process_count': processes(env)}
    if not snapshot['cli_exists'] or not snapshot['dll_exists']:
        snapshot.update(readiness='blocked', live_read_ok=False, blocked_by='runtime_missing')
        return snapshot
    data = call(cfg, env, 'status').get('status', {})
    for field in ('readiness', 'live_read_ok', 'blocked_by', 'warnings', 'account', 'wcdb', 'metadata_cache'):
        snapshot[field] = data.get(field)
    snapshot['cli_version'] = call(cfg, env, '--version').get('version')
    snapshot['wechat_version'] = None
    exe = Path(cfg.get('wechat_exe', ''))
    if sys.platform=='darwin' and exe.is_dir():
        plist=exe/'Contents'/'Info.plist'
        p=run(['/usr/libexec/PlistBuddy','-c','Print :CFBundleShortVersionString',str(plist)],env)
        snapshot['wechat_version']=p.stdout.strip() or None
    elif sys.platform=='win32' and exe.is_file():
        # The configured file path is quoted as literal PowerShell data.
        escaped = str(exe).replace("'", "''")
        p = run(['powershell', '-NoProfile', '-Command',
                 "(Get-Item -LiteralPath '"+escaped+"').VersionInfo.ProductVersion"], env)
        snapshot['wechat_version'] = p.stdout.strip() or None
    return snapshot


def repair(cfg, env):
    before = status(cfg, env)
    if not before['db_storage_exists']:
        raise ReaderError('db_root_missing', '请选择直接包含 db_storage 的账号目录。')
    if before.get('blocked_by') == 'runtime_missing':
        raise ReaderError('runtime_missing', '缺少 CLI 或数据库 DLL；不自动重装。')
    if not before.get('live_read_ok'):
        if sys.platform=='darwin':
            raise ReaderError('mac_bootstrap_required','需要单独授权 Mac wxkey bootstrap；它可能重启微信并把经验证的管理员密码存入本机钥匙串。请先阅读 macos.md。')
        if not before['wechat_process_count']:
            raise ReaderError('wechat_not_running', '请登录电脑版微信并打开普通聊天窗口。')
        p = run([cfg['python'], cfg['key_helper'], '--save'], env, timeout=240)
        if p.returncode:
            raise ReaderError('key_refresh_failed', '新版密钥获取失败；确认账号目录、登录和聊天窗口后再诊断，不自动重复扫描。')
    call(cfg, env, 'cache', 'refresh', '--force', timeout=180)
    after = status(cfg, env)
    if not after.get('live_read_ok'):
        raise ReaderError('live_read_failed', '密钥处理后实时查询仍未通过，停止修复。')
    return {'before': before, 'after': after}


def time_range(period, start=None, end=None, now=None):
    now = now or dt.datetime.now(ZONE)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if start:
        begin = dt.datetime.fromisoformat(start)
        finish = dt.datetime.fromisoformat(end) if end else now
        begin = begin.replace(tzinfo=ZONE) if begin.tzinfo is None else begin.astimezone(ZONE)
        finish = finish.replace(tzinfo=ZONE) if finish.tzinfo is None else finish.astimezone(ZONE)
    elif period == 'yesterday':
        begin, finish = midnight-dt.timedelta(days=1), midnight
    else:
        begin, finish = midnight-dt.timedelta(days=2 if period=='last3days' else 0), now
    finish = min(finish, now)
    if begin >= finish:
        raise ReaderError('invalid_time_range', '起始时间必须早于截止时间，且不能全在未来。')
    return begin, finish


def collect(cfg, env, chat, begin, finish, media=False, max_pages=100, invoke=call):
    resolved = invoke(cfg, env, 'resolve-chat', chat).get('candidates', [])
    exact = [x for x in resolved if x.get('username') == chat]
    candidates = exact or resolved
    if len(candidates) != 1:
        raise ReaderError('ambiguous_chat' if candidates else 'chat_not_found',
                          '请根据候选选择唯一会话。', candidates=[{'name':x.get('display_name'),'id':x.get('username')} for x in candidates])
    chosen = candidates[0]
    messages, seen, cursors, warnings = [], set(), set(), set()
    cursor = None
    source_incomplete = False
    complete = False
    stop_reason = 'page_limit'
    latest = None
    pages = 0
    for _ in range(max_pages):
        args = ['timeline', chosen['username'], '--after', str(int(begin.timestamp())),
                '--before', str(int(finish.timestamp())), '--limit', '200',
                '--include-media-paths', str(media).lower()]
        if cursor:
            args += ['--before-message-token', cursor]
        try:
            page = invoke(cfg, env, *args)
        except ReaderError as error:
            stop_reason = error.payload['code']
            break
        pages += 1
        latest = latest or page.get('freshness', {}).get('last_message_time')
        for warning in page.get('warnings') or []:
            warnings.add(str(warning))
            source_incomplete = True
        freshness = page.get('freshness', {})
        if any(freshness.get(k) is False for k in ('complete','message_source_complete','source_complete')):
            source_incomplete = True
        page_messages = []
        for message in page.get('messages', []):
            token = message.get('id', {}).get('message_token')
            if not token:
                stop_reason = 'missing_message_token'
                continue
            if token in seen:
                continue
            seen.add(token)
            stamp = message.get('create_time')
            if stamp is None or not begin.timestamp() <= stamp < finish.timestamp():
                continue
            # Exclude raw system XML and all debug material from assistant output.
            allowed = ('time_iso','time','create_time','sender','sender_wxid','is_from_me','kind','text','images','videos','files','link','quote','voice','warnings')
            item = {k:message[k] for k in allowed if k in message}
            item['message_token'] = token
            if item.get('kind') == 'system' and '<sysmsg' in item.get('text',''):
                item['text'] = '[系统事件：结构化内容未展开]'
            page_messages.append(item)
        messages = page_messages + messages
        query = page.get('query', {})
        if not query.get('has_more'):
            complete = stop_reason != 'missing_message_token' and not source_incomplete
            stop_reason = ('source_incomplete' if source_incomplete else
                           'exhausted' if complete else stop_reason)
            break
        cursor = query.get('cursor', {}).get('next_before_message_token')
        if not cursor or cursor in cursors:
            stop_reason = 'cursor_missing_or_repeated'
            break
        cursors.add(cursor)
    # Preserve the CLI's within-second order; tokens are opaque, not sort keys.
    messages.sort(key=lambda m:m.get('create_time',0))
    images = [m for m in messages if m.get('kind')=='image']
    readable = 0
    for m in images:
        m['images'] = [i for i in (m.get('images') or []) if i.get('path') and Path(i['path']).is_file() and Path(i['path']).suffix.lower() != '.dat']
        readable += bool(m['images'])
    voices = [m for m in messages if m.get('kind')=='voice']
    missing_voice = sum(not (m.get('voice') or {}).get('transcript') for m in voices)
    warning_messages = sum(bool(m.get('warnings')) for m in messages)
    return {'chat':chosen, 'range':{'start':begin.isoformat(),'end_exclusive':finish.isoformat(),'timezone':'Asia/Shanghai'},
            'source':'live_message_db','local_latest_message_time':latest,
            'completeness':{'complete':complete,'stop_reason':stop_reason,'pages':pages,'messages':len(messages),
                            'images':len(images),'readable_image_paths':readable,'unreadable_images':len(images)-readable,
                            'images_checked':media,'untranscribed_voices':missing_voice,
                            'unparsed_system_events':sum(m.get('text')=='[系统事件：结构化内容未展开]' for m in messages),
                            'withdrawal_events':sum(m.get('kind')=='system' and '撤回' in m.get('text','') for m in messages),
                            'media_complete':media and readable==len(images) and missing_voice==0,
                            'message_warning_count':warning_messages,'warnings':sorted(warnings)},
            'messages':messages}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--settings', type=Path, default=SETTINGS)
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('status')
    sub.add_parser('repair')
    image = sub.add_parser('repair-images')
    image.add_argument('--chat', required=True)
    image.add_argument('--month', default=dt.datetime.now(ZONE).strftime('%Y-%m'))
    configure = sub.add_parser('configure')
    configure.add_argument('--db-root', required=True, type=Path)
    read = sub.add_parser('read')
    read.add_argument('--chat', required=True)
    read.add_argument('--period', choices=['today','yesterday','last3days'], default='today')
    read.add_argument('--start')
    read.add_argument('--end')
    read.add_argument('--media', action='store_true')
    read.add_argument('--max-pages', type=int, default=100)
    read.add_argument('--output', type=Path)
    for command in sub.choices.values():
        command.add_argument('--authorized', action='store_true',
                             help='Operator attests user authorization for this specific action and scope.')
    read.add_argument('--allow-export', action='store_true')
    args = parser.parse_args()
    if not args.authorized:
        raise ReaderError('authorization_required', '需要用户对本次操作及范围的明确授权；未访问微信或配置。')
    if args.action == 'read' and args.output and not args.allow_export:
        raise ReaderError('export_authorization_required', '保存正文需要用户明确授权输出文件；未读取消息。')
    cfg = json.loads(args.settings.read_text(encoding='utf-8'))
    env = dict(os.environ, WECHAT_CLI_DB_ROOT=cfg['db_root'], PYTHONIOENCODING='utf-8')
    if args.action == 'configure':
        directory = args.db_root.resolve()
        if not (directory/'db_storage').is_dir():
            raise ReaderError('invalid_db_root', '目录必须直接包含 db_storage；配置未修改。')
        cfg['db_root'] = str(directory)
        args.settings.write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding='utf-8')
        result = {'db_root':str(directory),'requires_status_check':True}
    elif args.action == 'status':
        result = status(cfg, env)
        snapshot = Path(cfg['workspace'])/'wechat-reader-status.json'
        snapshot.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    elif args.action == 'repair-images':
        if sys.platform!='win32':
            raise ReaderError('image_repair_not_ported','此图片修复适配器目前只支持 Windows，不在 Mac 自动运行。')
        candidates=call(cfg,env,'resolve-chat',args.chat).get('candidates',[])
        if len(candidates)!=1:
            raise ReaderError('ambiguous_chat','请选择唯一的群聊后再进行图片修复。')
        p=run([cfg['python'],cfg['image_helper'],'--chatroom',candidates[0]['username'],'--month',args.month],env,timeout=110)
        try: result=json.loads(p.stdout)
        except ValueError: raise ReaderError('image_scan_failed','图片扫描没有返回有效结果，不自动重复。')
        if not result.get('ok'):
            raise ReaderError('image_key_unavailable','尚未校验出图片密钥；保持目标图片打开，暂将加密图片标为缺失。',statistics=result)
    elif args.action == 'repair':
        result = repair(cfg, env)
    else:
        if args.max_pages < 1 or (args.end and not args.start):
            raise ReaderError('invalid_arguments', '分页上限至少为 1；指定截止时间时也需指定起始时间。')
        begin, finish = time_range(args.period, args.start, args.end)
        result = collect(cfg, env, args.chat, begin, finish, args.media, args.max_pages)
        metadata = {k:v for k,v in result.items() if k != 'messages'}
        metadata['checked_at'] = dt.datetime.now(ZONE).isoformat()
        (Path(cfg['workspace'])/'wechat-reader-last-read.json').write_text(
            json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
        if args.output:
            args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'ok':True,'data':result},ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except ReaderError as error:
        print(json.dumps({'ok':False,'error':error.payload},ensure_ascii=False))
        sys.exit(1)
    except (ValueError, OSError, KeyError):
        print(json.dumps({'ok':False,'error':{'code':'configuration_error','message':'检查本机路径配置与文件权限；未输出原始异常。'}},ensure_ascii=False))
        sys.exit(1)
