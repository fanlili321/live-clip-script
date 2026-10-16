#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""直播转写稿解析与锚点切分。兼容飞书妙记导出的两种格式。

用法：
  python3 transcript.py index <稿件>              # 打印分块索引（序号/时间/字数/首句）
  python3 transcript.py show  <稿件> <起> [止]     # 打印第 起..止 块全文
  python3 transcript.py cut   <稿件> <起锚> <止锚> # 按锚点切分，输出 JSON
  python3 transcript.py stat  <稿件>              # 总字数、块数
锚点可跨段落边界（内部按"去掉换行"的连续文本检索），不必担心接缝。
"""
import re, sys, json

PATTERNS = [
    r'\[(\d\d:\d\d:\d\d)\.\d+\]\s*\S*\s*\n(.*?)(?=\n\[\d\d:\d\d:\d\d|\Z)',      # [00:00:19.630] 王磊
    r'(?:Speaker \d+|王磊|螺丝钉)\s+(\d\d:\d\d:\d\d)\.\d+\s*\n(.*?)(?=\n(?:Speaker \d+|王磊|螺丝钉)\s+\d\d:|\Z)',
]

def load(path):
    txt = open(path, encoding='utf-8').read()
    for p in PATTERNS:
        b = [(m.group(1), m.group(2).strip()) for m in re.finditer(p, txt, re.S)]
        if len(b) >= 5:
            return b
    raise SystemExit('无法识别转写稿格式：' + path)

class Doc:
    """把分块拼成一条连续文本，并保留 位置→时间 的映射。
    FLAT 去掉了块间换行，锚点跨段也能命中。"""
    def __init__(self, blocks):
        self.blocks = blocks
        self.FLAT = ''
        self.marks = []                      # (起始下标, 时间)
        for t, b in blocks:
            self.marks.append((len(self.FLAT), t))
            self.FLAT += b
    def time_at(self, i):
        cur = self.marks[0][1]
        for p, t in self.marks:
            if p <= i: cur = t
            else: break
        return cur
    def find(self, anchor, frm=0):
        a = re.sub(r'\s+', '', anchor)
        i = re.sub(r'\s+', '', self.FLAT).find(a, frm) if False else self.FLAT.find(a, frm)
        if i < 0:                            # 容错：锚点里可能带了原文没有的空格
            flat_ns = self.FLAT.replace(' ', '')
            j = flat_ns.find(anchor.replace(' ', ''))
            if j < 0: return -1, -1
            # 映射回原下标
            cnt = 0
            for k, ch in enumerate(self.FLAT):
                if ch != ' ':
                    if cnt == j: i = k; break
                    cnt += 1
            return i, len(anchor)
        return i, len(a)
    def cut(self, start_anchor, end_anchor):
        i, _ = self.find(start_anchor)
        if i < 0: raise SystemExit('起点锚点未命中：' + start_anchor[:40])
        j, n = self.find(end_anchor, i)
        if j < 0: raise SystemExit('终点锚点未命中：' + end_anchor[:40])
        j += n
        text = self.FLAT[i:j]
        return dict(text=text, chars=len(text), t0=self.time_at(i), t1=self.time_at(j-1),
                    pos=i, end=j)

def norm(s):
    """对齐用归一化：只保留中日文、字母、数字、百分号。"""
    return re.sub(r'[^\u4e00-\u9fff0-9a-zA-Z%]', '', s)

def main():
    if len(sys.argv) < 3: print(__doc__); sys.exit(1)
    cmd, path = sys.argv[1], sys.argv[2]
    d = Doc(load(path))
    if cmd == 'index':
        for i, (t, b) in enumerate(d.blocks):
            print(f'{i:3d} {t} {len(b):4d} {b[:70]}')
    elif cmd == 'stat':
        print(json.dumps(dict(blocks=len(d.blocks), chars=len(d.FLAT)), ensure_ascii=False))
    elif cmd == 'show':
        a = int(sys.argv[3]); b = int(sys.argv[4]) if len(sys.argv) > 4 else a
        for i in range(a, min(b+1, len(d.blocks))):
            print(f'--{i} {d.blocks[i][0]}--'); print(d.blocks[i][1]); print()
    elif cmd == 'cut':
        print(json.dumps(d.cut(sys.argv[3], sys.argv[4]), ensure_ascii=False, indent=1))
    else:
        print(__doc__)

if __name__ == '__main__':
    main()
