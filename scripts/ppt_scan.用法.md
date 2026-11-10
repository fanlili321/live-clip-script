# ppt_scan.swift —— 核对某个时间点直播画面里有没有 PPT

标红＝剪辑时全屏切 PPT。**问答环节通常没有 PPT**，标了也切不了。
拿到录屏（mp4）后用这个脚本扫一遍，确认标红时间点落在有 PPT 的区间里。

macOS 自带 swift + AVFoundation，**不需要装 ffmpeg**。

```bash
cd /Users/fanlili/Projects/视频切片/.agents/skills/live-clip-script/scripts
swiftc -O ppt_scan.swift -o ppt_scan
./ppt_scan "/path/to/录屏.mp4" 0 5400 20 > scan.csv    # 起点 终点 步长（秒）
```

输出 `sec,mean,whitefrac,satmean`。判据（螺丝钉的 PPT 是白底）：

- `whitefrac > 0.25` 或（`mean > 185` 且 `satmean < 0.2`）→ **PPT 画面**
- 否则 → 人物出镜

用 20 秒步长先扫全场找出 PPT 区间，再对可疑段用 10 秒步长复扫。
边界附近抽两帧肉眼确认（同目录 `grab.swift` 可抽帧存 jpg）。

**录屏时长和妙记文字稿时长可能差几十秒**（开录比开播晚）。
只要标红时间点离 PPT 结束点有几分钟以上余量，这点偏差不影响结论；
卡在边界上的，先用一页能认出来的 PPT 对齐时间轴。
