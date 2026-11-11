"""Tiny two-pass 6502 assembler for the patch sources.

Source: one statement per line. `label:` defines a label; `NAME = value` defines a constant;
`.org $XXXX` sets the PC; `.bank N` / `.bank -` places the following `.org`s in 16K bank N of the game.
`.byte $xx,...` emits bytes. `.rom $XXXX,n` (fixed bank) or `.rom B:$XXXX,n` (16K bank B) emits n bytes
of the original game's code from that address, read from the input ROM through ROM_READ.
Operands: #$xx / #<label / #>label, $xx (zp), $xxxx, label, ($xx),Y, ($xx,X), ($xxxx), with ,X / ,Y
suffixes (zp operands must be numeric). `;` starts a comment.
"""
import re
from dis6502 import OPS, SIZE

REV = {}
for code, (mn, md) in OPS.items():
    REV[(mn, md)] = code

ROM_READ = None        # fn(bank, addr) -> byte of the original game; set by the builder

def parse_num(s, labels, pc, final):
    s = s.strip()
    lo = hi = False
    if s.startswith('<'): lo = True; s = s[1:]
    elif s.startswith('>'): hi = True; s = s[1:]
    m = re.fullmatch(r'([A-Za-z_][\w]*)\s*([+-]\s*\$?[0-9A-Fa-f]+)?', s)
    if m and not re.fullmatch(r'\$[0-9A-Fa-f]+', s):
        name = m.group(1)
        if name not in labels:
            if final: raise KeyError(name)
            v = pc
        else:
            v = labels[name] & 0xFFFF      # operand: CPU address (bank bits only place bytes)
        if m.group(2):
            off = m.group(2).replace(' ', '')
            sign = -1 if off[0] == '-' else 1
            off = off[1:]
            v += sign * (int(off[1:], 16) if off.startswith('$') else int(off))
        is_label = True
    else:
        v = int(s[1:], 16) if s.startswith('$') else int(s)
        is_label = False
    if lo: v &= 0xFF
    if hi: v = (v >> 8) & 0xFF
    return v, is_label and not (lo or hi), len(s.lstrip('$')) <= 2 and not is_label

def rom_args(arg):
    """'$F152,13' or '3:$9C31,9' -> (bank or None, address, length)."""
    m = re.fullmatch(r'(?:(\d+):)?\$([0-9A-Fa-f]{4}),(\d+)', arg.replace(' ', ''))
    if not m: raise ValueError('bad .rom operand: ' + arg)
    bank = int(m.group(1)) if m.group(1) else None
    addr, n = int(m.group(2), 16), int(m.group(3))
    if addr < 0x8000 or (bank is None and addr < 0xC000) or (bank is not None and addr >= 0xC000) or n < 1:
        raise ValueError('bad .rom operand: ' + arg)
    return bank, addr, n

def assemble(src, origin=None, listing=None):
    """Returns ({address: byte}, labels). listing: optional list that receives (line index, start, end)."""
    labels = {}
    for final in (False, True):
        out = {}; pc = origin; bank = None
        for ln, raw in enumerate(src.splitlines()):
            start = pc
            line = raw.split(';')[0].strip()
            if not line: continue
            m = re.fullmatch(r'([A-Za-z_]\w*)\s*=\s*(\S+)', line)
            if m:                                  # NAME = value (absolute constant)
                labels[m.group(1)] = parse_num(m.group(2), labels, pc, final)[0]; continue
            while True:
                m = re.match(r'([A-Za-z_]\w*):\s*(.*)', line)
                if not m: break
                labels[m.group(1)] = pc; line = m.group(2).strip()
            if not line: continue
            if line.startswith('.bank'):
                arg = line.split()[1]
                bank = None if arg == '-' else int(arg); continue
            if line.startswith('.org'):
                pc = int(line.split()[1].lstrip('$'), 16)
                if bank is not None: pc |= (bank + 1) << 16
                continue
            if line.startswith('.byte'):
                for b in line[5:].split(','):
                    out[pc] = parse_num(b, labels, pc, final)[0] & 0xFF; pc += 1
            elif line.startswith('.rom'):
                rb, ra, n = rom_args(line[4:])
                for i in range(n):
                    out[pc + i] = ROM_READ(rb, ra + i) if final else 0
                pc += n
            else:
                pc = instruction(line, labels, pc, final, out)
            if final and listing is not None: listing.append((ln, start, pc))
    return out, labels

def instruction(line, labels, pc, final, out):
    parts = line.split(None, 1)
    mn = parts[0].upper(); arg = parts[1].replace(' ', '') if len(parts) > 1 else ''
    if mn in ('BPL', 'BMI', 'BVC', 'BVS', 'BCC', 'BCS', 'BNE', 'BEQ'):
        t, _, _ = parse_num(arg, labels, pc, final)
        off = (t & 0xFFFF) - ((pc & 0xFFFF) + 2)
        if final and not -128 <= off <= 127: raise ValueError(f'branch out of range at {pc:04X}: {line}')
        out[pc] = REV[(mn, 'rel')]; out[pc + 1] = off & 0xFF; return pc + 2
    if arg == '':
        md = 'acc' if (mn, 'acc') in REV and (mn, 'imp') not in REV else 'imp'
        out[pc] = REV[(mn, md)]; return pc + 1
    if arg.upper() == 'A':
        out[pc] = REV[(mn, 'acc')]; return pc + 1
    if arg.startswith('#'):
        v, _, _ = parse_num(arg[1:], labels, pc, final)
        out[pc] = REV[(mn, 'imm')]; out[pc + 1] = v & 0xFF; return pc + 2
    m = re.fullmatch(r'\((.+)\),Y', arg, re.I)
    if m:
        v, _, _ = parse_num(m.group(1), labels, pc, final)
        out[pc] = REV[(mn, 'izy')]; out[pc + 1] = v; return pc + 2
    m = re.fullmatch(r'\((.+),X\)', arg, re.I)
    if m:
        v, _, _ = parse_num(m.group(1), labels, pc, final)
        out[pc] = REV[(mn, 'izx')]; out[pc + 1] = v; return pc + 2
    m = re.fullmatch(r'\((.+)\)', arg)
    if m:
        v, _, _ = parse_num(m.group(1), labels, pc, final)
        out[pc] = REV[(mn, 'ind')]; out[pc + 1] = v & 0xFF; out[pc + 2] = v >> 8; return pc + 3
    idx = ''
    m = re.fullmatch(r'(.+),([XY])', arg, re.I)
    if m: arg, idx = m.group(1), m.group(2).upper()
    v, is_label, short = parse_num(arg, labels, pc, final)
    zp = short and v < 0x100
    md = {('', True): 'zp', ('', False): 'abs', ('X', True): 'zpx', ('X', False): 'abx',
          ('Y', True): 'zpy', ('Y', False): 'aby'}[(idx, zp)]
    if (mn, md) not in REV and md in ('zp', 'zpx', 'zpy'):
        md = {'zp': 'abs', 'zpx': 'abx', 'zpy': 'aby'}[md]
    code = REV[(mn, md)]
    out[pc] = code
    if SIZE[md] == 2: out[pc + 1] = v & 0xFF
    else: out[pc + 1] = v & 0xFF; out[pc + 2] = v >> 8
    return pc + SIZE[md]
