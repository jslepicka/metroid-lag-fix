"""The game's room drawing (SetupRoom from $EA3F up to EndOfRoomObjects $EACA or EndOfRoom $EAF4), done in
Python, reproducing the 1K image (name table + attribute table) and every zero-page byte the drawing writes,
with the same 8-bit wraparound and carries as the 6502 code. The build uses it to find, for every room, the
rows its structures cover completely, which the new room fill skips (stage2.fill_tables). Routine names and
addresses follow the m1disasm disassembly.

Zero page used by the drawing:
  $00/$01 room RAM pointer     $02/$03 attribute pointer     $0E object position / metatile counter
  $10 structure index          $11 metatile index            $33/$34 RoomPtr      $35/$36 StructPtr
  $37/$38 RoomRAMWorkPtr       $39/$3A RoomRAMPtr            $67 ObjectPalette    $68 RoomPalette
"""
import frames

AREA_BANKS = (1, 2, 3, 4, 5)
AREA_POINTERS = 0x959A                 # in each area bank: RoomPtrTable, StructPtrTable, MetatileDefs
TILE_POS = (0x21, 0x20, 0x01, 0x00)    # TilePosTable $EF9A: lower right, lower left, upper right, upper left
ATTR_MASK = (0xFC, 0xF3, 0xCF, 0x3F)   # UpdateAttrib's mask table $EFF4
ATTR_FILL = (0x00, 0x55, 0xAA, 0xFF)   # InitTables' fill table $F018
END_OBJECTS, END_ROOM = 0xEACA, 0xEAF4


class Draw:
    def __init__(self, bank, room, half):
        self.bank = bank
        self.zp = {}                    # zero-page bytes written: address -> final value
        self.wram = {}                  # room RAM bytes written
        self.half = half
        self.a = self.x = self.y = 0
        rd16 = lambda a: frames.rd(bank, a) | frames.rd(bank, a + 1) << 8
        self.room_tab, self.struct_tab, self.meta = rd16(AREA_POINTERS), rd16(AREA_POINTERS + 2), rd16(AREA_POINTERS + 4)
        self.run(room)

    # memory
    def rom(self, a): return frames.rd(self.bank, a & 0xFFFF)
    def z(self, a): return self.zp[a]
    def sz(self, a, v): self.zp[a] = v & 0xFF
    def ptr(self, a): return self.zp[a] | self.zp[a + 1] << 8
    def ind(self, a, y): return self.rom(self.ptr(a) + y)          # LDA (zp),Y from ROM
    def put(self, addr, v):                                           # STA into room RAM
        addr &= 0xFFFF
        if not (self.half << 8 <= addr < (self.half << 8) + 0x400):
            raise ValueError('write outside the room RAM block: %04X' % addr)
        self.wram[addr] = v & 0xFF
    def get(self, addr): return self.wram[addr & 0xFFFF]
    def add16(self, lo, v):                                           # CLC / ADC lo / STA lo / BCC + / INC lo+1
        s = self.z(lo) + v
        self.sz(lo, s)
        if s > 0xFF: self.sz(lo + 1, self.z(lo + 1) + 1)

    def run(self, room):
        # SetupRoom from $EA3F
        y = room * 2 & 0xFF
        self.sz(0x33, self.rom(self.room_tab + y)); self.sz(0x34, self.rom(self.room_tab + ((y + 1) & 0xFF)))
        self.sz(0x68, self.ind(0x33, 0))
        self.add16(0x33, 1)
        self.sz(0x39, 0); self.sz(0x3A, self.half)                     # SelectRoomRAM
        self.init_tables()
        # DrawRoom
        while True:
            self.y = 0
            self.a = self.ind(0x33, 0)
            if self.a == 0xFF: self.end = END_ROOM; return
            if self.a == 0xFE: raise ValueError('empty room object placeholder')
            if self.a == 0xFD: self.end = END_OBJECTS; return
            self.draw_object()
            self.add16(0x33, 3)

    def init_tables(self):
        # InitTables $EFF8 / FillRoomRAM $F01C: fill the 1K block with $FF from the top page down
        hi = self.z(0x3A)
        self.sz(0x01, hi + 3); self.sz(0x00, 0)
        for _ in range(4):
            for lo in range(256): self.put(self.z(0x01) << 8 | lo, 0xFF)
            self.sz(0x01, self.z(0x01) - 1)
        self.sz(0x01, self.z(0x01) + 4)
        self.x = self.z(0x68)
        for y in range(0xC0, 0x100): self.put(self.ptr(0x00) + y, ATTR_FILL[self.x])
        self.y = 0

    def draw_object(self):
        # DrawRoomObject $EA60 (A = position byte %yyyyxxxx)
        self.sz(0x0E, self.a)
        self.sz(0x37, self.z(0x39)); self.sz(0x38, self.z(0x3A))
        for _ in range(self.z(0x0E) >> 4): self.add16(0x37, 0x40)
        self.add16(0x37, (self.z(0x0E) & 0x0F) << 1)
        self.x = self.ind(0x33, 1)
        self.sz(0x67, self.ind(0x33, 2))
        y = self.x << 1 & 0xFF
        self.sz(0x35, self.rom(self.struct_tab + y)); self.sz(0x36, self.rom(self.struct_tab + ((y + 1) & 0xFF)))
        self.y = y + 1 & 0xFF
        self.draw_struct()

    def draw_struct(self):
        # DrawStruct $EF8C / DrawStructRow $EF13 / DrawMetatile $EF2B / AdvanceRow $EF78
        while True:
            self.y = 0
            self.sz(0x10, 0)
            self.a = self.ind(0x35, 0)
            if self.a == 0xFF: return
            n = self.a & 0x0F
            self.sz(0x0E, n or 0x10)
            s = ((self.ind(0x35, 0) >> 4) << 1) + self.z(0x37)
            self.sz(0x00, s); self.sz(0x01, self.z(0x38) + (s > 0xFF))
            while True:
                hi, lo = self.z(0x01), self.z(0x00)
                if hi in (0x63, 0x67):
                    if lo >= 0xA0: self.a = lo; return           # would reach the attribute table
                elif hi > 0x67:
                    self.a = hi; return                             # past room RAM
                self.sz(0x10, self.z(0x10) + 1)
                self.y = self.z(0x10)
                self.sz(0x11, self.ind(0x35, self.y) << 2)
                for x in (3, 2, 1, 0):
                    self.y = self.z(0x11)
                    v = self.rom(self.meta + self.y)
                    self.sz(0x11, self.z(0x11) + 1)
                    self.y = TILE_POS[x]
                    self.put(self.ptr(0x00) + self.y, v)
                self.x = 0xFF
                self.update_attrib()
                self.y = 2
                self.add16(0x00, 2)
                if self.z(0x00) & 0x1F == 0:                       # end of the name table row: skip the rest
                    a = ((self.z(0x10) + self.z(0x0E)) & 0xFF) - 1 & 0xFF
                    break
                self.sz(0x0E, self.z(0x0E) - 1)
                if self.z(0x0E) == 0:
                    a = self.z(0x10)
                    break
            s = self.z(0x35) + a + 1                                # SEC / ADC StructPtr
            self.sz(0x35, s)
            if s > 0xFF: self.sz(0x36, self.z(0x36) + 1)
            self.add16(0x37, 0x40)

    def update_attrib(self):
        # UpdateAttrib $EF9E
        self.a = self.z(0x67)
        if self.a == self.z(0x68): return
        lo, hi = self.z(0x00), self.z(0x01)
        p = lo
        c, hi2 = hi & 1, hi >> 1; p = p >> 1 | c << 7                # LSR A / ROR $02, twice
        c, hi2 = hi2 & 1, hi2 >> 1; p = p >> 1 | c << 7
        self.sz(0x02, p)
        self.sz(0x03, p & 7)
        self.sz(0x02, ((p >> 2) & 0x38) | self.z(0x03) | 0xC0)
        self.sz(0x03, 0x63)
        x = 2 if lo & 0x40 else 0
        if lo & 0x02: x += 1
        self.sz(0x03, (hi & 0x04) | self.z(0x03))
        self.y = 0
        addr = self.ptr(0x02)
        self.put(addr, ATTR_MASK[x] & self.get(addr))
        a = self.z(0x67)
        while True:
            x = x - 1 & 0xFF
            if x & 0x80: break
            a = a << 2
            c = a & 0x100; a &= 0xFF
            if c: break
        self.x = x
        self.a = a | self.get(addr)
        self.put(addr, self.a)


def record(bank, room):
    """Image and end state for one room, in the form gen_roomcode expects."""
    d = [Draw(bank, room, h) for h in (0x60, 0x64)]
    a, b = d
    base = lambda dd: dd.half << 8
    imgs = [bytes(dd.wram[base(dd) + i] for i in range(0x400)) for dd in d]
    if imgs[0] != imgs[1] or a.end != b.end or (a.a, a.x, a.y) != (b.a, b.x, b.y) or set(a.zp) != set(b.zp):
        raise ValueError('room %d/%02X draws differently in the two halves' % (bank, room))
    hi4 = sorted(k for k in a.zp if a.zp[k] != b.zp[k])
    if any(b.zp[k] != a.zp[k] + 4 for k in hi4):
        raise ValueError('room %d/%02X: halves differ by more than the room RAM page' % (bank, room))
    return dict(end=a.end, img=imgs[0], regs=dict(sorted(a.zp.items())), x=a.x, y=a.y, a=a.a, hi4=hi4)


def generate():
    """{(area bank, room): record} for every room in each area's room table. frames.load() must be called first."""
    res = {}
    for bank in AREA_BANKS:
        rd16 = lambda a: frames.rd(bank, a) | frames.rd(bank, a + 1) << 8
        n = (rd16(AREA_POINTERS + 2) - rd16(AREA_POINTERS)) // 2  # the room table ends where the structure table starts
        for room in range(n):
            res[(bank, room)] = record(bank, room)
    return res
