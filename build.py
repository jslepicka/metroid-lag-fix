"""Build Metroid lag fix 1.0 from your own copy of Metroid (USA).

usage: python build.py "Metroid (USA).nes" [output.nes] [--bps DIR] [--repack] [--allow-mismatch]

The output keeps your file's 16-byte header (iNES or NES 2.0). Everything taken from the game, such as moved
code and rearranged tables, is read from the input ROM here, so nothing from the game is in these sources.
--bps writes the two release patches (for the iNES and the NES 2.0 header) into DIR.
"""
import os, sys, time, zlib, argparse
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lib'))
import asm6502, stage1, stage2, title, bps

PRG_CRC = 0x70080810          # Metroid (USA): 128K PRG, no CHR ROM
OUT_PRG_CRC = 0xB55720CE      # the released build, header excluded
DEFAULT_OUT = 'Metroid (USA) - Lag Fix 1.0.nes'
HEADERS = {                   # the two headers the release patches are made for
    'iNES header': bytes.fromhex('4E45531A080010000000000000000000'),
    'NES 2.0 header': bytes.fromhex('4E45531A080010080000070700000001'),
}


def read_rom(path):
    d = open(path, 'rb').read()
    if d[:4] == b'NES\x1A':
        if d[4] != 8 or d[5] != 0:
            raise SystemExit('%s: expected 128K PRG and no CHR ROM (header says %dK PRG, %dK CHR)' % (path, d[4] * 16, d[5] * 8))
        if d[6] & 4: raise SystemExit('%s has a trainer; use a copy without one' % path)
        header, prg = d[:16], d[16:16 + 0x20000]
    else:
        header, prg = HEADERS['iNES header'], d[:0x20000]
    if len(prg) != 0x20000 or zlib.crc32(prg) != PRG_CRC:
        raise SystemExit('%s is not Metroid (USA): ROM CRC32 is %08X, expected %08X' % (path, zlib.crc32(prg), PRG_CRC))
    return header, prg


def build(prg, repack=False):
    asm6502.ROM_READ = lambda bank, a: prg[stage2.off(bank, a)]   # .rom lines copy from the input ROM
    rom = bytearray(HEADERS['iNES header'] + prg)
    stage1.build(rom)
    used = stage2.build(rom, prg, repack)
    title.apply(memoryview(rom)[16:])
    return bytes(rom[16:]), used


def main():
    ap = argparse.ArgumentParser(description='Build Metroid lag fix 1.0 from Metroid (USA).')
    ap.add_argument('rom', help='Metroid (USA) ROM (.nes; iNES or NES 2.0 header, or none)')
    ap.add_argument('out', nargs='?', default=DEFAULT_OUT, help='output file (default: "%s")' % DEFAULT_OUT)
    ap.add_argument('--bps', metavar='DIR', help='also write the two release patches into DIR')
    ap.add_argument('--repack', action='store_true', help='search for a new code layout and rewrite lib/layout.py')
    ap.add_argument('--allow-mismatch', action='store_true',
                    help='write the output even if it differs from the released build (for modified sources)')
    a = ap.parse_args()
    t0 = time.time()
    header, prg = read_rom(a.rom)
    new, used = build(prg, a.repack)
    crc = zlib.crc32(new)
    if crc != OUT_PRG_CRC and not a.allow_mismatch:
        raise SystemExit('output ROM CRC32 %08X does not match the released build (%08X); nothing written' % (crc, OUT_PRG_CRC))
    if a.repack:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lib', 'layout.py')
        text = open(path).read()
        head = text[:text.index('LAYOUT = {')]
        body = ''.join("    %-12s (0x%04X, %3d),\n" % ("'%s':" % k, v[0], v[1]) for k, v in sorted(used.items(), key=lambda kv: kv[1][0]))
        open(path, 'w').write(head + 'LAYOUT = {\n' + body + '}\n')
    with open(a.out, 'wb') as f:
        f.write(header + new)
    print('Wrote %s (ROM CRC32 %08X, file CRC32 %08X) in %.1f s' % (a.out, crc, zlib.crc32(header + new), time.time() - t0))
    if a.bps:
        os.makedirs(a.bps, exist_ok=True)
        for name, h in HEADERS.items():
            patch, literal = bps.encode(h + prg, h + new)
            out = os.path.join(a.bps, 'Metroid (USA) - Lag Fix 1.0 (%s).bps' % name)
            open(out, 'wb').write(patch)
            print('Wrote %s (%d bytes, %d stored, the rest copied from the original)' % (out, len(patch), literal))


if __name__ == '__main__':
    main()
