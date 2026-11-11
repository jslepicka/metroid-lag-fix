"""The title screen line: LAG FIX 1.0, centered two rows under the copyright, in the text's blue.

The title screen is drawn from one block of PPU strings in bank 0 ($82F4), right after both name tables are
cleared to the blank tile $FF. Blank padding in that block therefore draws nothing, and it is where the room for
the new line comes from; the block keeps its exact size, so nothing else in the ROM moves:
  - the story screen's attribute entry ($27C0: 8 x $00 then 24 x $FF) becomes a repeat of 8 x $00,
  - the run of 15 blanks at $20A8, the leading blank of PUSH START BUTTON and its trailing blanks are dropped.

The title font draws letters in color 1 and digits in color 2, and the title's color cycle does not keep those
two equal. So the digits (and a period, which the font lacks) are drawn into empty, unused background tiles
from $90 in color 1, copied from the font's own digit shapes, and the whole line uses the text palette.
"""
TEXT, ROW, ENDCOL = 'LAG FIX 1.0', 21, 21
BLOCK = 0x02F4                                    # bank 0 offset of the title-screen PPU strings


def apply(prg):
    """prg: the 128K PRG (bytearray or memoryview), modified in place."""
    CH = {' ': 0xFF}
    CH.update({c: 0x0A + i for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ')})
    font = next(p for p in range(len(prg) - 160)       # the font's digit tiles: digits use plane 1 only
                if all(prg[p + t * 16 + y] == 0 for t in range(10) for y in range(8))
                and bytes(prg[p + 24:p + 31]) == bytes([0x18, 0x38, 0x18, 0x18, 0x18, 0x18, 0x7E]))
    glyphs = []; tile = 0x90
    for ch in dict.fromkeys(c for c in TEXT if c.isdigit() or c == '.'):
        rows = bytes([0, 0, 0, 0, 0, 0x18, 0x18]) if ch == '.' else bytes(prg[font + int(ch) * 16 + 8:font + int(ch) * 16 + 15])
        glyphs.append((tile, rows)); CH[ch] = tile; tile += 1
    structs, p = [], BLOCK
    while prg[p]:
        a = prg[p] << 8 | prg[p + 1]; n = prg[p + 2]
        if n & 0x40: structs.append([a, 'rep', n & 0x3F, prg[p + 3]]); p += 4
        else: structs.append([a, 'str', bytes(prg[p + 3:p + 3 + n])]); p += 3 + n
    size = p - BLOCK
    col = ENDCOL - len(TEXT) + 1
    add = [[0x2000 + ROW * 32 + col, 'str', bytes(CH[c] for c in TEXT)]]
    for t, rows in glyphs:                             # plane 0 only: color 1, like the letters
        r = rows.lstrip(b'\x00')
        add.append([0x1000 + t * 16 + len(rows) - len(r), 'str', r])
    need = sum(3 + len(s[2]) for s in add)
    for i, s in enumerate(structs):
        if s[0] == 0x27C0 and s[1] == 'str' and s[2] == bytes(8) + b'\xff' * 24:
            structs[i] = [0x27C0, 'rep', 8, 0x00]; need -= 31
    structs = [s for s in structs if not (s[1] == 'rep' and s[0] == 0x20A8 and s[3] == 0xFF)]; need -= 4
    for s in structs:
        if s[0] == 0x2227 and s[2][:1] == b'\xff': s[0] += 1; s[2] = s[2][1:]; need -= 1
    for s in structs:
        if s[0] == 0x2228 and need > 0:
            t = len(s[2]) - len(s[2].rstrip(b'\xff')); k = min(t, need); s[2] = s[2][:len(s[2]) - k]; need -= k
    assert need == 0, need
    for s in structs:                                  # attribute bits: the line's 2x2-tile blocks use the text palette
        if s[1] == 'str' and s[0] == 0x23E0:
            b = bytearray(s[2])
            for c in range(col, ENDCOL + 1):
                i = (ROW // 4) * 8 + c // 4 - 0x20
                sh = (2 if (c // 2) & 1 else 0) + (4 if (ROW // 2) & 1 else 0)
                b[i] = (b[i] & ~(3 << sh)) | (3 << sh)
            s[2] = bytes(b)
    blk = bytearray()
    for s in structs:
        blk += bytes([s[0] >> 8, s[0] & 0xFF]) + (bytes([s[2] | 0x40, s[3]]) if s[1] == 'rep' else bytes([len(s[2])]) + s[2])
        if s[0] == 0x2269:                             # the copyright line; the new entries follow it
            for t in add: blk += bytes([t[0] >> 8, t[0] & 0xFF, len(t[2])]) + t[2]
    assert len(blk) == size
    prg[BLOCK:BLOCK + size] = blk
