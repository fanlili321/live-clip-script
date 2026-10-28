#!/usr/bin/env python3
"""Preview or send the standard Minutes notification for a live episode."""

import argparse
import json
import subprocess
import sys

DEFAULT_CHAT_ID = "oc_d49775cef6a606b893cdec743875be02"  # 内容小分队
MENTIONS = (
    ('ou_e9a6dd9bd4ab1b8d65452635ef70c953', '汤爱学'),
    ('ou_ac59bb01b7e830ae90f51515e0b54a07', '郭凤强'),
)


def main() -> int:
    parser = argparse.ArgumentParser(description="通知群内本期直播妙记已生成")
    parser.add_argument("minute_token", help="飞书妙记 token")
    parser.add_argument("--ep", required=True, help="期数，例如 476")
    parser.add_argument("--chars", required=True, type=int, help="文字稿字数")
    parser.add_argument("--chat-id", default=DEFAULT_CHAT_ID, help="目标群 chat_id")
    parser.add_argument("--dry-run", action="store_true", help="仅打印将要发送的内容")
    args = parser.parse_args()

    url = f"https://epndqwwg0a.feishu.cn/minutes/{args.minute_token}"
    mentions = ' '.join(f'<at user_id="{uid}">{name}</at>' for uid, name in MENTIONS)
    message = f"{mentions} 第{args.ep}期直播文字稿已生成（{args.chars}字）：{url}"
    preview = {"chat_id": args.chat_id, "identity": "user", "text": message}

    if args.dry_run:
        print(json.dumps(preview, ensure_ascii=False))
        return 0

    command = [
        "lark-cli", "im", "+messages-send", "--chat-id", args.chat_id,
        "--text", message, "--as", "user",
    ]
    result = subprocess.run(command, text=True, capture_output=True)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
