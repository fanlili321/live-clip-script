#!/usr/bin/env python3
"""Open Minutes link to internet readers, then notify both fixed groups."""

import argparse
import json
import subprocess
import sys

GROUPS = (
    ('内容小分队', 'oc_d49775cef6a606b893cdec743875be02',
     'ou_ac59bb01b7e830ae90f51515e0b54a07', '郭凤强'),
    ('钉友会社群运营 专项沟通群', 'oc_dc7492847c1a7fd0668a6ea282730473',
     'ou_bef5c199d656dca51a61652aa85f16b0', '蒋优'),
)


def lark(*args):
    result = subprocess.run(['lark-cli', *args, '--format', 'json'],
                            text=True, capture_output=True)
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        raise RuntimeError((result.stderr or result.stdout)[:500])
    if result.returncode or not data.get('ok'):
        raise RuntimeError(json.dumps(data.get('error', data), ensure_ascii=False)[:700])
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="开放妙记互联网阅读并通知两个群")
    parser.add_argument("minute_token", help="飞书妙记 token")
    parser.add_argument("--ep", required=True, help="期数，例如 476")
    parser.add_argument("--chars", required=True, type=int, help="文字稿字数")
    parser.add_argument("--dry-run", action="store_true", help="仅打印将要发送的内容")
    args = parser.parse_args()

    url = f"https://epndqwwg0a.feishu.cn/minutes/{args.minute_token}"
    messages = []
    for group, chat_id, uid, name in GROUPS:
        message = (f'<at user_id="{uid}">{name}</at> '
                   f'第{args.ep}期直播文字稿已生成（{args.chars}字）：{url}')
        messages.append({'group': group, 'chat_id': chat_id, 'text': message,
                         'idempotency_key': f'minutes-{args.minute_token[-12:]}-{chat_id[-8:]}'})

    if args.dry_run:
        print(json.dumps({'identity': 'user', 'permission': 'anyone_readable',
                          'messages': messages}, ensure_ascii=False, indent=2))
        return 0

    permission = lark('drive', 'permission.public', 'get', '--token', args.minute_token,
                      '--type', 'minutes', '--as', 'user')['data']['permission_public']
    if permission.get('external_access') is not True or permission.get('link_share_entity') != 'anyone_readable':
        lark('drive', 'permission.public', 'patch', '--token', args.minute_token,
             '--type', 'minutes', '--data',
             '{"external_access":true,"link_share_entity":"anyone_readable"}',
             '--as', 'user', '--yes')
        permission = lark('drive', 'permission.public', 'get', '--token', args.minute_token,
                          '--type', 'minutes', '--as', 'user')['data']['permission_public']
    if permission.get('external_access') is not True or permission.get('link_share_entity') != 'anyone_readable':
        raise RuntimeError('互联网持链接可阅读权限未生效，未向群发送')

    for item in messages:
        result = lark('im', '+messages-send', '--chat-id', item['chat_id'],
                      '--text', item['text'], '--idempotency-key', item['idempotency_key'],
                      '--as', 'user')
        print(json.dumps({'group': item['group'],
                          'message_id': result.get('data', {}).get('message_id')},
                         ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f'未完成通知：{exc}', file=sys.stderr)
        raise SystemExit(1)
