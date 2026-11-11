"""Stage 1: the HUD and sprite-clear unrolling, the dispatch shortcuts, the first quick collision test and the
Tourian cannon drawer (asm/hud_oam, misc, collide, turret, sprite_writer).

Their work-RAM code is a static image stored in blocks of the ROM that the game never reads; a copier hooked
into the reset code puts it in place at power-on, and a generator (Gen) writes the unrolled sprite clear
($7400) and HUD copy ($6C80) next to it.
"""
import os
from asm6502 import assemble

ASM = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'asm')
STATIC_BASE, WRAM_END = 0x74C0, 0x77EF       # static work-RAM image; $7400-$74BF is generated (the sprite clear)
GENERATED = [(0x7400, 0x74BF), (0x6C80, 0x6D4A)]
TABLE = 0x8206                                # bank 0, an unused intro routine: the copier's chunk table
TAIL = 0x9549                                 # bank 0, last bytes of $945F-$955F (unused routines and padding)
# unused, never-read blocks (bank, address, length), in copy order
FREE = [(4, 0x9280, 224), (5, 0x94B0, 176), (0, 0x945F, TAIL - 0x945F), (4, 0x98C9, 60),
        (1, 0x9965, 60), (0, 0x81EE, 24), (0, 0x828A, 24)]
BOOT_LO, BOOT_HI = 0xF0A0, 0xF0EC


def src(name, subst):
    s = open(os.path.join(ASM, name)).read()
    for k, v in subst.items(): s = s.replace(k, '$%04X' % v)
    return s


BOOT = """
        .org $C06D
        JSR Boot                ; was LDA #$0E / STA $25 (reset, right after the WRAM clear)
        NOP

        .org $F0A0
; Copy the static work-RAM image out of unused ROM blocks, then (in the bank-0 tail) generate the
; unrolled code and leave zero page, X and Y exactly as the reset code had them.
Boot:   LDY #$%02X
BT1:    LDA BTbl,Y              ; chunk table lives in bank 0, mapped at reset
        STA $10,Y
        DEY
        BPL BT1
        LDA #$%02X
        STA $02
        LDA #$%02X
        STA $03
        LDX #$00
BNext:  LDA $10,X
        BMI BDone
        JSR $C4FA               ; select PRG bank A at $8000 (the game's own MMC1 routine)
        LDA $11,X
        STA $00
        LDA $12,X
        STA $01
        LDY $13,X
BCopy:  DEY
        LDA ($00),Y
        STA ($02),Y
        TYA
        BNE BCopy
        LDA $02
        CLC
        ADC $13,X
        STA $02
        BCC BNoC
        INC $03
BNoC:   INX
        INX
        INX
        INX
        BNE BNext
BDone:  LDA #$00
        JSR $C4FA               ; back to bank 0, where the tail lives
        JMP BTail

        .bank 0
        .org $%04X
BTbl:
%s        .byte $FF
        .org $%04X
BTail:  JSR $%04X               ; Gen: build the unrolled sprite clear and HUD copy
        LDA #$00
        LDX #$2F
BT2:    STA $00,X               ; zero page was all zero here except $01
        DEX
        BPL BT2
        LDX #$5F
        STX $01
        LDY #$00
        LDA #$0E                ; the two instructions the hook displaced
        STA $25
        RTS
        .bank -
"""


def build(rom):
    """rom: bytearray, an iNES file of the original game (16-byte header). Applies stage 1 in place."""
    subst = {}
    end = max(a for a in assemble(src('hud_oam.asm', {}))[0] if STATIC_BASE <= a <= WRAM_END) + 1
    for name, key in [('misc.asm', 'WRAM_MISC'), ('collide.asm', 'WRAM_COLLIDE'), ('turret.asm', 'WRAM_TURRET')]:
        subst[key] = end
        tmp = {k: subst.get(k, 0x7400) for k in ('WRAM_MISC', 'WRAM_COLLIDE', 'WRAM_TURRET')}
        o = assemble(src(name, tmp))[0]
        end = max(a for a in o if 0x6000 <= a < 0x8000) + 1
    merged = {}; owner = {}; labels_all = {}
    for name in ['sprite_writer.asm', 'hud_oam.asm', 'misc.asm', 'collide.asm', 'turret.asm']:
        o, labels = assemble(src(name, subst))
        if name == 'hud_oam.asm': labels_all.update(labels)
        for a, v in o.items():
            if a in owner: raise SystemExit('overlap at %X: %s / %s' % (a, owner[a], name))
            owner[a] = name; merged[a] = v
    wram = {a: v for a, v in merged.items() if 0x6000 <= a < 0x8000}
    lo, hi = min(wram), max(wram)
    assert lo == STATIC_BASE and hi <= WRAM_END and len(wram) == hi - lo + 1, ('work-RAM image', hex(lo), hex(hi), len(wram))
    for g0, g1 in GENERATED: assert not any(g0 <= a <= g1 for a in wram), 'image overlaps a generated region'
    image = bytes(wram[a] for a in range(lo, hi + 1))
    chunks = []; pos = 0
    for bank, a, n in FREE:
        if pos >= len(image): break
        k = min(n, len(image) - pos)
        chunks.append((bank, a, k, image[pos:pos + k])); pos += k
    if pos < len(image): raise SystemExit('image %d bytes > free %d' % (len(image), sum(n for _, _, n in FREE)))
    tbl = ''.join('        .byte $%02X,$%02X,$%02X,$%02X\n' % (b, a & 255, a >> 8, n) for b, a, n, _ in chunks)
    tlen = 4 * len(chunks) + 1
    bo = assemble(BOOT % (tlen - 1, STATIC_BASE & 255, STATIC_BASE >> 8, TABLE, tbl, TAIL, labels_all['Gen'] & 0xFFFF))[0]
    top = max(a for a in bo if 0xF000 <= a < 0x10000)
    if top > BOOT_HI: raise SystemExit('boot copier ends at %04X, past %04X' % (top, BOOT_HI))
    b0 = sorted(a & 0xFFFF for a in bo if (a >> 16) == 1)
    assert max(a for a in b0 if a < 0x9000) <= 0x822C and max(a for a in b0 if a >= 0x9000) <= 0x955F
    assert tlen <= 0x30 - 0x10, 'table overflows zero-page scratch'
    for a, v in bo.items():
        if a in owner: raise SystemExit('boot overlaps %s at %X' % (owner[a], a))
        owner[a] = 'boot'; merged[a] = v
    def put(bank, a, v):
        rom[16 + bank * 0x4000 + a - (0xC000 if bank == 7 else 0x8000)] = v
    for a, v in merged.items():
        if a >= 0x10000: put((a >> 16) - 1, a & 0xFFFF, v)
        elif a >= 0xC000: put(7, a, v)
        elif 0x6000 <= a < 0x8000: pass
        else: raise SystemExit('stray byte at %X' % a)
    for bank, a, n, data in chunks:
        for i, v in enumerate(data): put(bank, a + i, v)
    return rom
