#!/usr/bin/env python3
import random, pathlib, sys
from collections import defaultdict

# 参数
N = int(sys.argv[1]) if len(sys.argv) > 1 else 8   # incast 发送端数量
ROUNDS = 20                                        # burst 轮数
GAP = 0.10                                         # 两个 burst 之间的间隔
SEED = 1
random.seed(SEED)

# 拓扑规模（与你的 NED 匹配：4 个 leaf、每 leaf 3 台主机）
HOSTS_PER_LEAF = 3
LEAVES = 4
TOTAL = HOSTS_PER_LEAF * LEAVES

victim = 0                     # 所有 incast 都打到 host[0]
MICE = 512 * 1024              # 512KB 短流
ELEPHANT = 64 * 1024 * 1024    # 64MB 长流

by_host = defaultdict(list)
t = 0.0
for r in range(ROUNDS):
    # 选 N 个不同的发送端，避开 victim
    senders = set()
    while len(senders) < N:
        s = random.randrange(TOTAL)
        if s != victim:
            senders.add(s)
    senders = sorted(senders)
    # 让每个 sender 发一个 mice 到 victim；轻微错开启动时间
    for idx, s in enumerate(senders):
        tOpen = t + 0.000 * idx
        tSend = t + 0.010 * idx
        by_host[s].append((tOpen, tSend, victim, MICE))
    t += GAP

# 让一条 elephant 与 incast 重叠，观察短长流共存
src_ele = (victim + 1) % TOTAL
by_host[src_ele].append((0.0, 0.01, victim, ELEPHANT))

# 写 flows.inc：先写 numApps，再写每个 app 的参数
lines = ["# auto-generated incast by traffic_incast.py"]
for h, vec in by_host.items():
    lines.append(f"**.host[{h}].numApps = {len(vec)}")
for h, vec in by_host.items():
    for i, (tOpen, tSend, dst, bytes_) in enumerate(vec):
        base = f"**.host[{h}].app[{i}]"
        lines += [
            f'{base}.typename = "TcpSessionApp"',
            f"{base}.active = true",
            f'{base}.connectAddress = "host[{dst}]"',
            f"{base}.connectPort = 80",
            f"{base}.tOpen = {tOpen:.3f}s",
            f"{base}.tSend = {tSend:.3f}s",
            f"{base}.sendBytes = {bytes_}B",
            f"{base}.tClose = {tSend+3600:.3f}s",
        ]

out = pathlib.Path(__file__).resolve().parents[1] / "sim" / "flows.inc"
out.write_text("\n".join(lines))
print("wrote", out)
