#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把候选脚本写成飞书表格（含标红/删除线富文本、列宽、权限）。

用法：python3 build_sheet.py <候选定义.json> [--title "表格标题"]

候选定义.json 是一个数组，每条：
{
  "id":"465-01", "tag":"提交"|"备选", "zone":"知识"|"问答",
  "ep":"465期",
  "titles":["标题1","标题2","标题3"],
  "text":"正文全文（连续原文）",
  "t0":"00:01:10", "t1":"00:05:51",
  "red":[["红字起始片段","红字结束片段"], ...],      # 可空
  "strike":[["划线起始片段","划线结束片段或空串"], ...],# 可空
  "ppt":"P2 ... / P3 ...",
  "q":"真实问题原句", "gw":"归位句原文", "why":"入选理由",
  "risk":["额外风险项", ...]                        # 可空
}
脚本自动：按 tag+t0 排序 → 建表 → 写富文本 → 底部标记 → 列宽 → 冻结首行 → 开组织内可编辑。
"""
import json, sys, subprocess, re

RED = '#f54a45'
BLACK = '#000000'      # 普通正文必须显式给黑色——见 rich() 注释
HEAD = ['标题', '内容', '字数', '来源', '钉大反馈', '时间范围', '入选理由', '风险检查']
WIDTH = [('A:A', 220), ('B:B', 650), ('C:D', 50), ('E:E', 300), ('F:F', 110), ('G:H', 340)]
WRAP = 'auto-wrap'          # 全表自动换行
# 飞书云盘目标文件夹（2026-08-08 起换到新文件夹）。改成 '' 则建到云盘根目录。
FOLDER = 'WrrLfZW9plUxPidz8hkc6pj7nUf'

def lark(*args, **kw):
    r = subprocess.run(['lark-cli'] + list(args), capture_output=True, text=True)
    if kw.get('raw'): return r.stdout
    try: return json.loads(r.stdout)
    except Exception: raise SystemExit(r.stdout[:500] + r.stderr[:500])

OPEN_MIN_SEC = 5        # 开场至少这么多秒要有人物出镜，之后才允许切 PPT（2026-08-09 钉大定为 5 秒）

def _sec(hms):
    p = [int(x) for x in hms.split(':')]
    while len(p) < 3: p.insert(0, 0)
    return p[0] * 3600 + p[1] * 60 + p[2]

def red_floor(d):
    """红字起点的最小下标：既要过第一句，也要够 OPEN_MIN_SEC 秒的人物出镜。

    只满足「过了第一句」是不够的——467 期那条第一句仅 36 字≈4.7 秒，
    观感上仍然是「一上来就是 PPT」。所以再按本条自己的语速折算一道时间下限。
    下限 5 秒由钉大定（2026-08-09），此前暂定 10 秒。
    """
    t = d['text']
    ends = [m.end() for m in re.finditer(r'[。！？?!]', t)] or [0]
    floor_sent = ends[0]
    try:
        dur = _sec(d['t1']) - _sec(d['t0'])
        cps = len(t) / dur if dur > 0 else 0
    except Exception:
        cps = 0
    if not cps:
        return floor_sent, floor_sent, None
    need = OPEN_MIN_SEC * cps
    # 取第一个既过第一句、又过时间下限的句末
    floor = next((e for e in ends if e >= max(floor_sent, need)), ends[-1])
    return floor, floor_sent, cps

def segs_of(d):
    """把 red/strike 的片段锚点解析成 [start, end, kind] 下标区间。"""
    body, out = d['text'], []
    floor, floor_sent, cps = red_floor(d)
    for a, b in d.get('red', []):
        i = body.find(a)
        if i < 0: raise SystemExit(f"{d['id']} 标红起点未命中：{a[:30]}")
        j = body.find(b, i)
        if j < 0: raise SystemExit(f"{d['id']} 标红终点未命中：{b[:30]}")
        # 标红＝剪辑时全屏切到 PPT。开场必须先有人物出镜，否则视频一上来就没有脸。
        if i < floor:
            why = ('压到了开头第一句' if i < floor_sent
                   else f'开场人物出镜不足 {OPEN_MIN_SEC} 秒（约 {i/cps:.1f} 秒就切了 PPT）')
            raise SystemExit(
                f"{d['id']} 标红{why}（红字起点 {i} < 下限 {floor}）。\n"
                f"  应留白到：{body[:floor]}\n"
                f"  开场先给人物出镜，之后才允许切 PPT——第一句太短的，顺延到下一句。\n"
                f"  把红字起点挪到下限之后；若这条从第一句就在读图，说明起点该往前扩一句铺垫。")
        out.append([i, j + len(b), 'red'])
    for a, b in d.get('strike', []):
        i = body.find(a)
        if i < 0: raise SystemExit(f"{d['id']} 删除线起点未命中：{a[:30]}")
        j = (body.find(b, i) + len(b)) if b else i + len(a)
        out.append([i, j, 'strike'])
    return sorted(out)

def rich(d, segs):
    """生成富文本分段。

    ⚠️ 普通正文必须**显式**写 font_color=BLACK，不能留空。
    飞书会把整格的 cell_styles.font_color 设成首个 run 的颜色；留空的 run
    会**继承单元格级颜色**。467 期踩过：这一格首建时整段标红 → 单元格级
    font_color 被设成红；后来把红字起点往后挪，首段 run 没写颜色，于是
    继续继承单元格级的红——接口读出来 run 是「无色」，界面上却是红的。
    读接口时只看 run 级样式会漏掉这种情况，见 verify_red()。
    """
    t, out, cur = d['text'], [], 0
    base = {'font_size': 13, 'font_color': BLACK}
    for i, j, k in segs:
        if i > cur: out.append(dict(type='text', text=t[cur:i], style=dict(base)))
        st = dict(base)
        st.update({'font_color': RED} if k == 'red' else {'font_line': 'line-through'})
        out.append(dict(type='text', text=t[i:j], style=st)); cur = j
    if cur < len(t): out.append(dict(type='text', text=t[cur:], style=dict(base)))
    if any(k == 'red' for _, _, k in segs):
        out.append(dict(type='text', text='\n\n（标红部分插入PPT）',
                        style={'font_size': 13, 'font_color': RED}))
    return out


def verify_red(tok, sh, n):
    """回读校验：单元格级 font_color 不能是红色，且首段 run 必须显式非红。"""
    got = lark('sheets', '+cells-get', '--spreadsheet-token', tok, '--sheet-id', sh,
               '--range', f'B2:B{n+1}', '--include', 'value,style', '--format', 'json')
    bad = []
    for i, row in enumerate(got.get('data', {}).get('ranges', [{}])[0].get('cells', [])):
        if not row: continue
        c = row[0]
        if ((c.get('cell_styles') or {}).get('font_color') or '').lower() == RED:
            bad.append(f'B{i+2} 单元格级颜色是红的（首段会继承成红字）')
        runs = c.get('rich_text') or []
        if runs and (runs[0].get('style') or {}).get('font_color', '').lower() != BLACK:
            bad.append(f'B{i+2} 首段 run 没有显式黑色')
    return bad

def main():
    path = sys.argv[1]
    title = sys.argv[sys.argv.index('--title') + 1] if '--title' in sys.argv else None
    C = json.load(open(path, encoding='utf-8'))
    ep = C[0].get('ep', '')
    title = title or f'{ep} 切片脚本'
    C.sort(key=lambda x: (x.get('tag', '提交') != '提交', x['t0']))

    # ---- 交付量闸门（钉大 2026-08-09：10–15 条都是合理范围）----
    # 上限 15。**条数跟着内容走：合适就选，不合适不用硬凑。**
    # 8.5 私募版交 17 条、退回率 53%（历次最高），所以 15 以上仍然拦。
    n = len(C)
    if n > 15 and '--force-count' not in sys.argv:
        print(f'❌ {n} 条，超过上限 15 条。\n'
              f'   8.5 私募版交 17 条、退回 53%（历次最高），过量与退回率高度相关。\n'
              f'   先砍到 15 条以内——**只减条数，不缩边界**。\n'
              f'   同一场直播拆成多张表的，配额按整场算，不是每张表各 15 条。\n'
              f'   确实要交，加 --force-count 并在交付说明里写清理由。', file=sys.stderr)
        sys.exit(1)
    if n < 4:
        print(f'⚠️ 只有 {n} 条，低于下限 4 条——确认是内容确实不够，不是漏切。', file=sys.stderr)

    create = ['sheets', '+workbook-create', '--title', title, '--format', 'json']
    if FOLDER:
        create += ['--folder-token', FOLDER]
    wb = lark(*create)
    tok = wb['data']['spreadsheet']['spreadsheet_token']
    url = wb['data']['spreadsheet']['url']
    sh = lark('sheets', '+workbook-info', '--spreadsheet-token', tok,
              '--format', 'json')['data']['sheets'][0]['sheet_id']

    rows = [[dict(value=h, cell_styles={'font_weight': 'bold', 'font_size': 12,
                                        'background_color': '#F0EDE6', 'word_wrap': WRAP}) for h in HEAD]]
    for d in C:
        segs = segs_of(d)
        hasred = any(k == 'red' for _, _, k in segs)
        hasstk = any(k == 'strike' for _, _, k in segs)
        risk = ['PPT：' + d.get('ppt', '无') + ('　→ 已标红' if hasred else '　→ 不标红'),
                '删除线：' + ('已划掉合规/时效内容' if hasstk else '本条无需划线')]
        risk += d.get('risk', [])
        rows.append([
            dict(value='\n'.join(f'标题{i+1}：{x}' for i, x in enumerate(d['titles'])),
                 cell_styles={'font_size': 12, 'vertical_alignment': 'top', 'word_wrap': WRAP}),
            dict(rich_text=rich(d, segs),
                 cell_styles={'font_size': 13, 'vertical_alignment': 'top', 'word_wrap': WRAP}),
            dict(value=len(d['text']), cell_styles={'word_wrap': WRAP}),
            dict(value=d.get('ep', ''), cell_styles={'word_wrap': WRAP}),
            dict(value='', cell_styles={'word_wrap': WRAP}),
            dict(value=f"{d['t0']}—{d['t1']}", cell_styles={'word_wrap': WRAP}),
            dict(value=f"【{d.get('tag','提交')}·{d.get('zone','')}段】\n真实问题原句：{d.get('q','')}\n"
                       f"中心命题：{d['titles'][0]}\n归位句：{d.get('gw','')}\n判断：{d.get('why','')}",
                 cell_styles={'font_size': 11, 'vertical_alignment': 'top', 'word_wrap': WRAP}),
            dict(value='\n'.join(risk),
                 cell_styles={'font_size': 11, 'vertical_alignment': 'top', 'word_wrap': WRAP}),
        ])
    json.dump(rows, open('.rows.tmp.json', 'w'), ensure_ascii=False)
    r = lark('sheets', '+cells-set', '--spreadsheet-token', tok, '--sheet-id', sh,
             '--range', f'A1:H{len(rows)}', '--cells', '@.rows.tmp.json', '--format', 'json')
    if not r.get('ok'): raise SystemExit(json.dumps(r, ensure_ascii=False)[:600])

    # 再整体刷一次自动换行（cells-set 的样式偶有遗漏，这里兜底）
    lark('sheets', '+cells-set-style', '--spreadsheet-token', tok, '--sheet-id', sh,
         '--range', f'A1:H{len(rows)}', '--word-wrap', WRAP, '--format', 'json')

    for rng, w in WIDTH:
        lark('sheets', '+cols-resize', '--spreadsheet-token', tok, '--sheet-id', sh,
             '--range', rng, '--type', 'pixel', '--size', str(w), '--format', 'json')
    lark('sheets', '+dim-freeze', '--spreadsheet-token', tok, '--sheet-id', sh,
         '--dimension', 'row', '--count', '1', '--format', 'json')
    # 开链接权限：组织内获得链接的人可编辑。属 high-risk-write，本工作流已获授权，故带 --yes
    pr = lark('drive', 'permission.public', 'patch', '--token', tok, '--type', 'sheet',
              '--data', '{"link_share_entity":"tenant_editable"}', '--yes', '--format', 'json')
    if not pr.get('ok'):
        print('⚠️ 链接权限设置失败：', json.dumps(pr.get('error', {}), ensure_ascii=False)[:200], file=sys.stderr)
    got = lark('drive', 'permission.public', 'get', '--token', tok, '--type', 'sheet',
               '--format', 'json').get('data', {}).get('permission_public', {}).get('link_share_entity', '未知')

    sub = [d for d in C if d.get('tag', '提交') == '提交']
    for b in verify_red(tok, sh, len(C)):
        print('⚠️ 标红回读校验：' + b, file=sys.stderr)

    print(json.dumps(dict(url=url, 文件夹=('AI切片脚本' if FOLDER else '云盘根目录'),
                          条数=len(C), 提交=len(sub),
                          知识段=sum(1 for d in sub if d.get('zone') == '知识'),
                          问答段=sum(1 for d in sub if d.get('zone') == '问答'),
                          提交字数=sum(len(d['text']) for d in sub),
                          标红条数=sum(1 for d in C if d.get('red')),
                          删除线条数=sum(1 for d in C if d.get('strike')),
                          链接权限=got), ensure_ascii=False, indent=1))

if __name__ == '__main__':
    main()
