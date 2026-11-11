"""BPS patches (the beat patch format) that carry no bytes of the original game.

Every byte of the target that comes from the original is encoded as a copy from the source file instead of as
data: unchanged bytes (SourceRead), runs of 4 or more bytes found anywhere in the original (SourceCopy: moved code
and tables), the tables the build rearranges (every 2nd, 3rd or 4th byte of an original table: placement tables,
metatile tables), and single values the build takes from the original (the graphics load lists' block numbers,
the cannon frames' tiles and offsets), each copied from its exact place. Only new code and computed values are
stored in the patch itself. decode() is an independent reader used to check every patch written.
"""
import zlib
import frames
from stage2 import PLACE_EN, PLACE_OBJ, GLIST, GFX_CODE, off

H = 16


def vlq(n):
    out = bytearray()
    while True:
        x = n & 0x7F; n >>= 7
        if n == 0: out.append(0x80 | x); return bytes(out)
        out.append(x); n -= 1


def derived_bytes(src, tgt):
    """{target offset: source offset} for single bytes the build takes from the original game."""
    d = {}
    for bank, (ptab, slots, lo, hi) in list(PLACE_EN.items()) + [(b, PLACE_OBJ) for b in range(1, 6)]:
        base = H + off(bank, lo); n = (hi - lo) // 2       # placement tables: y bytes, then x bytes
        for k in range(n):
            d[base + k] = base + 2 * k
            d[base + n + k] = base + 2 * k + 1
    ops = [H + off(7, a) + 1 for a in range(GFX_CODE[0], GFX_CODE[1])    # LDY #id operands of the load sequences
           if src[H + off(7, a)] == 0xA0 and src[H + off(7, a) + 2] in (0x20, 0x4C) and src[H + off(7, a) + 3:H + off(7, a) + 5] == bytes([0xAB, 0xC7])]
    t, k = H + off(6, GLIST), 0
    while k < len(ops):
        if tgt[t] not in (0xFE, 0xFF): d[t] = ops[k]; k += 1
        t += 1
    frames.load(src[H:H + 0x20000])                       # Tourian cannon frames 6-13: tile and unflipped offsets
    ptrs = {i: (fp, pp) for i, fp, pp in frames.frame_ptrs(3)}
    b3 = lambda a: H + off(3, a)
    cols = {'y': [], 'x': [], 't': []}
    for fr in range(6, 14):
        fp, pp = ptrs[fr]; hdr = src[b3(fp)]; i, j = 3, 0
        while True:
            c = src[b3(fp) + i]
            if c == 0xFC: i += 3; continue
            if c == 0xFD: i += 2; continue
            if c == 0xFE: i += 1; j += 2; continue
            break
        cols['t'].append((c, b3(fp) + i))
        cols['y'].append((src[b3(pp) + j], None if hdr & 0x80 else b3(pp) + j))
        cols['x'].append((src[b3(pp) + j + 1], None if hdr & 0x40 else b3(pp) + j + 1))
    for vals in cols.values():
        hit = next(t for t in range(H, len(tgt) - 8) if tgt[t:t + 8] != src[t:t + 8] and
                   all(tgt[t + i] == v for i, (v, q) in enumerate(vals) if q is not None))
        for i, (v, q) in enumerate(vals):
            if q is not None: d[hit + i] = q
    return {t: s for t, s in d.items() if tgt[t] == src[s]}


def encode(src, tgt, meta=b''):
    assert len(src) == len(tgt)
    derived = derived_bytes(src, tgt)
    K = 4
    idx = {}
    for i in range(len(src) - K + 1): idx.setdefault(src[i:i + K], []).append(i)
    sidx = {}
    for st in (2, 3, 4):
        dd = sidx[st] = {}
        for q in range(len(src) - 3 * st): dd.setdefault(bytes((src[q], src[q + st], src[q + 2 * st], src[q + 3 * st])), []).append(q)
    out = bytearray(b'BPS1') + vlq(len(src)) + vlq(len(tgt)) + vlq(len(meta)) + meta
    st_ = dict(srel=0, lit=bytearray(), literal=0)
    def flush():
        if st_['lit']:
            out.extend(vlq(((len(st_['lit']) - 1) << 2) | 1)); out.extend(st_['lit'])
            st_['literal'] += len(st_['lit']); st_['lit'] = bytearray()
    def scopy(at, length):
        flush()
        out.extend(vlq(((length - 1) << 2) | 2))
        dlt = at - st_['srel']
        out.extend(vlq((abs(dlt) << 1) | (1 if dlt < 0 else 0)))
        st_['srel'] = at + length
    i = 0
    while i < len(tgt):
        if tgt[i] == src[i]:                              # unchanged
            j = i
            while j < len(tgt) and tgt[j] == src[j]: j += 1
            flush(); out.extend(vlq(((j - i - 1) << 2) | 0)); i = j; continue
        best, at = 0, 0
        for p in idx.get(tgt[i:i + K], ())[:4000]:        # moved: the longest run found in the original
            L = K
            while i + L < len(tgt) and p + L < len(src) and tgt[i + L] == src[p + L] and tgt[i + L] != src[i + L]: L += 1
            if L > best or (L == best and abs(p - st_['srel']) < abs(at - st_['srel'])): best, at = L, p
        if best >= K:
            scopy(at, best); i += best; continue
        if i + 6 <= len(tgt):                             # rearranged tables: every 2nd, 3rd or 4th original byte
            bs = None
            for st in (4, 2, 3):
                for p in sidx[st].get(tgt[i:i + 4], ())[:2000]:
                    L = 4
                    while i + L < len(tgt) and p + st * L < len(src) and tgt[i + L] == src[p + st * L] and tgt[i + L] != src[i + L]: L += 1
                    if L >= 6 and (bs is None or L > bs[2] or (L == bs[2] and abs(p - i) < abs(bs[1] - i))): bs = (st, p, L)
            if bs:
                st, p, L = bs
                for k in range(L): scopy(p + st * k, 1)
                i += L; continue
        if i in derived:                                  # a single value taken from the original
            scopy(derived[i], 1); i += 1; continue
        st_['lit'].append(tgt[i]); i += 1
    flush()
    out += zlib.crc32(src).to_bytes(4, 'little') + zlib.crc32(tgt).to_bytes(4, 'little')
    out += zlib.crc32(bytes(out)).to_bytes(4, 'little')
    patch = bytes(out)
    assert decode(patch, src) == tgt, 'patch does not reproduce the target'
    return patch, st_['literal']


def decode(p, s):
    assert p[:4] == b'BPS1'
    pos = 4
    def rd():
        nonlocal pos
        data, shift = 0, 1
        while True:
            x = p[pos]; pos += 1
            data += (x & 0x7F) * shift
            if x & 0x80: return data
            shift <<= 7; data += shift
    ss, ts, ms = rd(), rd(), rd(); pos += ms
    assert ss == len(s) and zlib.crc32(s) == int.from_bytes(p[-12:-8], 'little'), 'wrong source file'
    assert zlib.crc32(p[:-4]) == int.from_bytes(p[-4:], 'little'), 'damaged patch'
    t = bytearray(); sr = tr = 0
    while pos < len(p) - 12:
        d = rd(); cmd, n = d & 3, (d >> 2) + 1
        if cmd == 0: t += s[len(t):len(t) + n]
        elif cmd == 1: t += p[pos:pos + n]; pos += n
        elif cmd == 2:
            o = rd(); sr += -(o >> 1) if o & 1 else (o >> 1); t += s[sr:sr + n]; sr += n
        else:
            o = rd(); tr += -(o >> 1) if o & 1 else (o >> 1)
            for _ in range(n): t.append(t[tr]); tr += 1
    assert len(t) == ts and zlib.crc32(bytes(t)) == int.from_bytes(p[-8:-4], 'little'), 'wrong result'
    return bytes(t)
