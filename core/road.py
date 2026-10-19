"""「走过的路」几何计算 —— 与 App 端 packages/core/src/road.js 同源移植。

为什么要有它：用户要求「网页版视图和 app 必须一样」。App 首页的主体不是表单，
而是一条蜿蜒向下的路：写过的心里话是一支蜡烛，每周心里日记是一盏路灯，
还没走过的段位是暗点。网页版此前把这页做成了普通表单页，这就是"视图不一样"
的最大来源。本模块把 App 的 buildRoad / loadEntries / smoothPath 原样搬过来，
输出(px 坐标)供 views/companion.py 拼成同一张路。

坐标口径：App 是 750rpx 设计宽；网页版手机栏宽 PHONE_MAX(480px)，
换算系数 F = 480 / 750 = 0.64。本模块直接输出 px，调用方不再换算。

只做几何，不碰任何业务与云端 —— 与 road.js 一样是纯函数。
"""

import math

STAGE_W = 750.0                       # 设计宽（rpx，与 road.js 一致）
SLOT = 200                            # 每个站点的高度（rpx）
PATTERN = [34, 44, 54, 57, 47, 36]    # 站点水平位置循环，形成蜿蜒
MIN_SLOTS = 7                         # 路至少铺这么长
Y0 = 120                              # 第一个节点距容器顶部（rpx）
LEAD = 90                             # 首个节点上方多出的一段引路
TAIL = 220                            # 末尾多出的一段去路
STEP = 22                             # 曲线采样密度：越小越顺滑
ROAD_H = 16                           # 路的宽度（rpx）

# 网页手机栏 480px 对应 750rpx
F = 480.0 / 750.0


def _x_of(i):
    return STAGE_W * PATTERN[i % len(PATTERN)] / 100.0


def _catmull(p0, p1, p2, p3, t):
    """Catmull-Rom 插值（与 util.js 的 catmull 逐式一致）。"""
    t2 = t * t
    t3 = t2 * t

    def f(a, b, c, d):
        return 0.5 * ((2 * b) + (-a + c) * t + (2 * a - 5 * b + 4 * c - d) * t2
                      + (-a + 3 * b - 3 * c + d) * t3)
    return (f(p0[0], p1[0], p2[0], p3[0]), f(p0[1], p1[1], p2[1], p3[1]))


def _smooth_path(pts, step=STEP):
    """控制点序列 → 柔和曲线采样点（整数 rpx）。"""
    out = []
    n = len(pts)
    if n < 2:
        return out

    def P(i):
        return pts[max(0, min(n - 1, i))]

    for i in range(n - 1):
        p0, p1, p2, p3 = P(i - 1), P(i), P(i + 1), P(i + 2)
        dist = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
        seg = max(4, round(dist / step))
        for s in range(seg):
            out.append(_catmull(p0, p1, p2, p3, s / seg))
    out.append(pts[-1])
    return [(round(x), round(y)) for x, y in out]


def build_road(entries):
    """条目数组 → {nodes, links, stage_height}。

    entries: [{key, kind, ts, timeText, label, content}]（新的在前，见 load_entries）。
    输出的 left/top/len 均已换算成 px（rpx × F）。
    """
    count = max(len(entries), MIN_SLOTS)
    nodes = []
    for i in range(count):
        e = entries[i] if i < len(entries) else None
        nodes.append({
            "key": e["key"] if e else "v%d" % i,
            "kind": e["kind"] if e else "vacant",
            "label": e["label"] if e else ("还没走过的路" if i == len(entries) else ""),
            "left": _x_of(i) * F,
            "top": (Y0 + i * SLOT) * F,
        })

    pts = [(_x_of(0), Y0 - LEAD)]
    for i in range(count):
        pts.append((_x_of(i), Y0 + i * SLOT))
    pts.append((_x_of(count - 1), Y0 + (count - 1) * SLOT + TAIL))

    samples = _smooth_path(pts)
    # "已走过的路"下界：只有至少两条记录时才点亮第一段（与 road.js 同判定）
    walked_to = (Y0 + (len(entries) - 1) * SLOT) if len(entries) >= 2 else -1

    links = []
    for k in range(len(samples) - 1):
        ax, ay = samples[k]
        bx, by = samples[k + 1]
        dx, dy = bx - ax, by - ay
        length = math.hypot(dx, dy)
        if length < 0.6:
            continue
        links.append({
            "left": ax * F,
            "top": (ay - ROAD_H / 2) * F,
            "len": round(length * F) + 2,
            "angle": round(math.degrees(math.atan2(dy, dx))),
            "solid": (Y0 - 1) <= ay <= walked_to,
        })

    bottom = Y0 + (count - 1) * SLOT + TAIL
    return {"nodes": nodes, "links": links, "stage_height": (bottom + 60) * F}


def load_entries(candles):
    """网页版日记列表 → 路上条目（新的在前）。

    candles: [{id, ts, content, mood}]（_all_diaries 的输出即可直接传入）。
    App 端还有「路灯」(每周心里日记)；网页版的周记暂未落，路灯位由暗点补位 ——
    蜡烛部分与 App 完全同构。
    """
    entries = []
    for it in candles or []:
        ts = it.get("ts") or it.get("id") or 0
        entries.append({
            "key": "c%s" % (it.get("id") or ts),
            "kind": "candle",
            "ts": ts,
            "timeText": it.get("timeText") or "",
            "label": "",       # 模板层会补 monthDay
            "content": it.get("content") or "",
            "mood": it.get("mood") or "",
        })
    entries.sort(key=lambda e: -(e["ts"] or 0))
    return entries
