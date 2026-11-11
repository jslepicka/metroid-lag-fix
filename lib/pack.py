"""Search for a stage 2 layout (build.py --repack): which free region each unpinned code piece goes in.

Fills one region at a time as fully as possible (subset sum), with randomized retries from a fixed seed, so the
result is repeatable; restricted pieces (work-RAM only, fixed-bank only) go first. If no attempt places every
piece, an exact depth-first search tries every assignment.
"""
import random


def pack(cs, size, free, fits, tries=300, max_nodes=3000000):
    """cs: [(name, pin, body, kind)]; size: {name: bytes}; free: [[lo, hi, region kind]];
    fits(name, kind, region kind) -> bool. Returns {name: address}."""
    org = {}
    free = [list(r) for r in free]
    for name, pin, body, kind in cs:                     # pinned pieces take their own addresses
        if pin is None: continue
        org[name] = pin
        for r in free:
            if r[0] <= pin <= r[1]:
                assert pin + size[name] - 1 <= r[1], ('pinned piece overflows', name)
                if pin == r[0]: r[0] = pin + size[name]
                else: raise SystemExit('pinned piece not at region start: ' + name)
                break
    items = [c for c in cs if c[1] is None]
    ok = lambda c, r: fits(c[0], c[3], r[2])
    rng = random.Random(7)
    best = None
    for attempt in range(tries):
        regs = [list(r) for r in free]
        order = sorted(range(len(regs)), key=lambda q: (regs[q][1] - regs[q][0]) * (-1 if attempt % 2 else 1) + (rng.random() * 40 if attempt > 1 else 0))
        if attempt:
            for _ in range(attempt % 7):
                a_, b_ = rng.randrange(len(order)), rng.randrange(len(order)); order[a_], order[b_] = order[b_], order[a_]
        left_items = list(items); og = {}
        bigfirst = attempt % 3 == 2                      # every third attempt: all pieces of 40+ bytes first, best fit
        for c in sorted([c for c in items if c[0].endswith('_W') or c[3] == 'fixed' or (bigfirst and size[c[0]] >= 40)], key=lambda c: -size[c[0]]):
            cand = [r for r in regs if ok(c, r) and r[1] - r[0] + 1 >= size[c[0]]]
            if not cand: break
            r = min(cand, key=lambda r: (r[1] - r[0] + 1 - size[c[0]]) + (rng.random() * 60 if attempt else 0))
            og[c[0]] = r[0]; r[0] += size[c[0]]; left_items.remove(c)
        for q in order:
            r = regs[q]; cap = r[1] - r[0] + 1
            cand = [c for c in left_items if ok(c, r) and size[c[0]] <= cap]
            if not cand: continue
            if attempt: rng.shuffle(cand)
            cand.sort(key=lambda c: (not c[0].endswith('_W'), c[3] != 'fixed'))
            reach = {0: []}
            for c in cand:
                n = size[c[0]]
                for s0, lst in list(reach.items()):
                    t = s0 + n
                    if t <= cap and t not in reach: reach[t] = lst + [c]
            for c in reach[max(reach)]:
                og[c[0]] = r[0]; r[0] += size[c[0]]; left_items.remove(c)
        if not left_items:
            best = og; break
    if best is None:
        its = sorted(items, key=lambda c: -size[c[0]])
        kinds_of = [tuple(k for k in ('pad', 'fixed', 'wram', 'wram_t') if ok(c, [0, 0, k])) for c in its]
        seen = set(); nodes = [0]; place_ = {}
        def dfs(i, caps):
            if i == len(its): return True
            nodes[0] += 1
            if nodes[0] > max_nodes: return False
            key = (i, tuple(sorted(caps)))
            if key in seen: return False
            n = size[its[i][0]]
            if sum(c for c, k, q in caps if k in kinds_of[i]) < n: seen.add(key); return False
            tried = set()
            for idx in sorted(range(len(caps)), key=lambda j: caps[j][0]):
                c, k, q = caps[idx]
                if k not in kinds_of[i] or c < n or (c, k) in tried: continue
                tried.add((c, k))
                caps2 = list(caps); caps2[idx] = (c - n, k, q)
                place_[its[i][0]] = (q, c)
                if dfs(i + 1, caps2): return True
            seen.add(key)
            return False
        if dfs(0, [(r[1] - r[0] + 1, r[2], qi) for qi, r in enumerate(free)]):
            used = {qi: free[qi][0] for qi in range(len(free))}
            best = {}
            for c in its:
                qi, cap = place_[c[0]]
                best[c[0]] = used[qi]; used[qi] += size[c[0]]
    if best is None:
        raise SystemExit('no layout found for %d bytes of unpinned code' % sum(size[c[0]] for c in items))
    org.update(best)
    return org
