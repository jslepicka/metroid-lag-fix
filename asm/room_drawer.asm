; Room drawer (SetupRoom from $EA3F to EndOfRoomObjects / EndOfRoom). Same room RAM, the same
; zero page left behind and the same A/X/Y as the original, checked for every room against the original.
;   - the build splits each area's metatile table (4 bytes per metatile) into four tables M apart (top left,
;     top right, bottom left, bottom right); only the room drawer reads it (checked by watching every read)
;   - fill: 15 name-table stores and the attribute store per pass over 64 offsets (a copy per half)
;   - metatiles: Y = metatile, X = position in the page; the four stores go through absolute,X addresses whose
;     high byte is set once per row; the structure byte through a self-modified address; the loop ends at
;     the row's end position (clipped at the end of the line once per row)
;   - attributes (objects whose palette differs from the room's): after the row's tiles, one pass over the
;     row's attribute bytes, two metatiles per read-modify-write where they share a byte; exact, since
;     (b & M0 | S0) & M1 | S1 = b & (M0 & M1) | (S0 & M1 | S1), in the original's order
;   - what the original leaves in $00/$01, $0E, $10, $11 after the last row is worked out once, at the end
; Chunks ending in _W run from WRAM (self-modified).

SHP  = $6FF0                    ; object palette shifted for the four attribute quadrants (as UpdateAttrib)
PV   = $6FF4                    ; fill: the attribute value (read only by the fill, before any object)
PVT  = $6FF4                    ; RowEndA pair values, per object: +0 upper half, +2 lower half of an attribute block
RCNT = $6FF7                    ; RowEndA / DEnd: metatile count
TB   = $74FE                    ; this area's fill table (48 bytes, one per room), copied by WLoad
TBTAG = $752E                   ; the area bank it was copied for

;@chunk RJ $EA3F
        JMP FD
;@chunk RJ2 $EA5D
        JMP DR                  ; SetupRoom's $FE path (no room uses the placeholder)

;@chunk FD
FD:     .rom $EA3F,19             ; SetupRoom+$14
        INC $33
        BNE fd1
        INC $34
fd1:    JSR $EA05               ; SelectRoomRAM: $39/$3A
AfterSel:
        LDX $23                 ; area bank: the four tile tables are M apart
        LDA $3F
        STA T0+1
        CLC
        ADC MTab-1,X
        STA T1+1
        LDA $40
        STA T0+2
        ADC #$00
        STA T1+2
        LDA T1+1
        ADC MTab-1,X
        STA T2+1
        LDA T1+2
        ADC #$00
        STA T2+2
        LDA T2+1
        ADC MTab-1,X
        STA T3+1
        LDA T2+2
        ADC #$00
        STA T3+2
        LDX $68
        LDA $F018,X             ; InitTables' attribute fill for the room palette
        STA PV
        LDA #$00                ; name-table rows the room's objects cover at the top and bottom: skip their
        LDX $23                 ;  fill (TB: this area's table, copied by WLoad; byte offset of the first
        CPX TBTAG               ;  store to run, 45 = none)
        BNE fd6
        LDX $5A
        LDA TB,X
fd6:    SEC
        SBC #$3A                ; the loop's branch back to that store (it ends 58 bytes on)
        LDY #$FF                ; (the loop's INY makes it 0)
        LDX $3A
        CPX #$64
        BEQ fd7
        STA FAB+1
        LDA #$FF
        JMP FAI
fd7:    STA FBB+1
        LDA #$FF
        JMP FBI
MTab:   .byte $MT1,$MT2,$MT3,$MT4,$MT5

;@chunk FillA_W
; Half $6000 (B: $6400): name table to $FF, attribute table to the room fill. The rows go outside in, so
; the covered top and bottom rows the table skips are the first stores; entered at the INY (Y = $FF) with
; the branch back patched to the first store to run.
FA0:    STA $6000,Y
        STA $6380,Y
        STA $6040,Y
        STA $6340,Y
        STA $6080,Y
        STA $6300,Y
        STA $60C0,Y
        STA $62C0,Y
        STA $6100,Y
        STA $6280,Y
        STA $6140,Y
        STA $6240,Y
        STA $6180,Y
        STA $6200,Y
        STA $61C0,Y
        LDA PV
        STA $63C0,Y
        LDA #$FF
FAI:    INY
        CPY #$40
FAB:    BNE FA0
        JMP FillE

;@chunk FillB_W
FB0:    STA $6400,Y
        STA $6780,Y
        STA $6440,Y
        STA $6740,Y
        STA $6480,Y
        STA $6700,Y
        STA $64C0,Y
        STA $66C0,Y
        STA $6500,Y
        STA $6680,Y
        STA $6540,Y
        STA $6640,Y
        STA $6580,Y
        STA $6600,Y
        STA $65C0,Y
        LDA PV
        STA $67C0,Y
        LDA #$FF
FBI:    INY
        CPY #$40
FBB:    BNE FB0
        JMP FillE

;@chunk FillE
; As InitTables leaves it: $00 = 0, $01 = page + 3 (X and Y are set again before they matter).
FillE:  LDA #$00
        STA $00
        LDA $3A
        CLC
        ADC #$03
        STA $01
        JMP DR

;@chunk DR
DR:     LDY #$00
        LDA ($33),Y
        CMP #$FD
        BCC DRO
        BEQ de0                 ; $FD: end of the objects
        CMP #$FE
        BNE de0                 ; $FF: end of the room
        JMP $EABC
de0:    JMP DEnd
DRO:    STA $0E                 ; position %yyyyxxxx
        ASL A
        ASL A
        AND #$C0
        STA $37
        LDA $0E
        AND #$0F
        ASL A
        ORA $37
        STA $37
        LDA $0E
        ASL A
        ROL A
        ROL A
        AND #$03
        CLC
        ADC $3A
        STA $38
        LDY #$01
        LDA ($33),Y
        .rom $EA97,11             ; DrawRoomObject+$37
        LDY #$02
        LDA ($33),Y
        STA $67
        CMP $68
        BEQ dro1
        STA SHP                 ; palette differs: as UpdateAttrib's shifts, and attributes after each row
        ASL A
        ASL A
        STA SHP+1
        BCS c1
        ASL A
        ASL A
        STA SHP+2
        BCS c2
        ASL A
        ASL A
        STA SHP+3
        JMP c3
c1:     STA SHP+2
c2:     STA SHP+3
c3:     LDA SHP                 ; pair values for RowEndA: (S0 & M1) | S1 and (S2 & M3) | S3
        AND #$F3
        ORA SHP+1
        STA PVT
        LDA SHP+2
        AND #$3F
        ORA SHP+3
        STA PVT+2
        LDA #<RowEndA
        STA MX+1
        LDA #>RowEndA
        STA MX+2
        JMP dro2
dro1:   LDA #<RowEnd
        STA MX+1
        LDA #>RowEnd
        STA MX+2
dro2:   JSR DS
        LDA $33
        CLC
        ADC #$03
        STA $33
        BCC d3
        INC $34
d3:     JMP DR

;@chunk DS
; The object's structure rows. Per row, as the original: $0E = n, $00/$01 = row start; stop at $FF or where
; the row would reach the attribute table. RowEnd (after a row) falls into DS.
RowEnd: LDA $0E                 ; structure += n + 1
        SEC
        ADC $35
        STA $35
        BCC re1
        INC $36
        CLC
re1:    LDA $37                 ; row base += $40
        .rom $EA75,4              ; DrawRoomObject+$15
        BCC DS
        INC $38
DS:     LDY #$00
        LDA ($35),Y
        CMP #$FF
        BNE ds0
        RTS
ds0:    TAX
        .rom $EF13,6              ; n = low nibble, 0 means 16
ds1:    .rom $EF19,2
        ASL A
        STA $11                 ; 2n (scratch: $11 is set at the end)
        TXA
        AND #$F0
        LSR A
        LSR A
        LSR A                   ; 2 * x offset, carry clear
        ADC $37
        STA $00
        TAX                     ; X = position in the page
        LDA $38
        ADC #$00
        STA $01
        CMP S0+2                ; the stores' page (the same for most rows; harmless if the row then stops)
        BEQ ok
        STA S0+2
        STA S1+2
        STA S2+2
        STA S3+2
ok:     AND #$03                ; the half's last page: stop at the attribute table
        CMP #$03
        BNE ok2
        CPX #$A0
        BCC ok2
        RTS
ok2:    TXA                     ; end position: start + 2n, or the end of the line if the row reaches it
        ORA #$E0
        CLC
        ADC $11
        BCS clip
        TXA
        ADC $11
ce:     STA CE+1
        LDA $35                 ; metatile bytes from ($35)+1
        SEC
        ADC #$00
        STA SF+1
        LDA $36
        ADC #$00
        STA SF+2
        JMP Mt
clip:   TXA                     ; (when it ends exactly there, both give start + 2n)
        ORA #$1F
        ADC #$00                ; (carry set: +1)
        JMP ce

;@chunk Mt_W
Mt:
SF:     LDY $FFFF               ; metatile (self-modified address, stepped below)
        INC SF+1
        BNE m1
        INC SF+2
m1:
T0:     LDA $FFFF,Y
S0:     STA $FF00,X
T1:     LDA $FFFF,Y
S1:     STA $FF01,X
T2:     LDA $FFFF,Y
S2:     STA $FF20,X
T3:     LDA $FFFF,Y
S3:     STA $FF21,X
        INX
        INX
CE:     CPX #$00
        BNE Mt
MX:     JMP RowEnd              ; RowEnd, or RowEndA for an object whose palette differs

;@chunk RowEndA
; The row's attribute updates (palette SHP) for the metatiles from $00 to the end position, in the original's
; order per byte. Leaves $02/$03 at the last metatile's attribute byte, as UpdateAttrib does.
RowEndA:
        LDA $00                 ; attribute row: lo = $C0 | ((hi&3)<<1 | lo>>7) << 3, hi = (hi & 4) | $63
        ASL A
        LDA $01
        AND #$03
        ROL A
        ASL A
        ASL A
        ASL A
        ORA #$C0
        STA $02
        LDA $3A
        ORA #$03
        .rom $EFC4,6              ; quadrant pair: 2 in the lower half of the attribute block
        BVC ra1
        LDX #$02
ra1:    LDA CE+1                ; metatiles in the row
        SEC
        SBC $00
        LSR A
        STA RCNT
        LDA $00                 ; first byte; C = odd first column
        AND #$1F
        LSR A
        LSR A
        TAY
        BCC ra2
        LDA $EFF5,X             ; odd first column: the byte's second quadrant alone
        AND ($02),Y
        ORA SHP+1,X
        STA ($02),Y
        INY
        DEC RCNT
        BEQ rad
ra2:    LSR RCNT                ; pairs in one byte
        BEQ ra3
ra5:    LDA ($02),Y
        AND PMC,X
        ORA PVT,X
        STA ($02),Y
        INY
        DEC RCNT
        BNE ra5
ra3:    LDA #$02                ; the last column even (bit 1 of the end position): its quadrant alone
        BIT CE+1
        BEQ rad
        LDA $EFF4,X
        AND ($02),Y
        ORA SHP,X
        STA ($02),Y
        INY
rad:    DEY                     ; $02 = the last metatile's byte
        TYA
        ORA $02
        STA $02
        JMP RowEnd
PMC:    .byte $F0,$00,$0F

;@chunk DEnd
; End of the objects. Unless the last row looked at stopped at the attribute table (then the zero page is as
; the original leaves it), leave what the original leaves after that row: $00/$01 = start + 2 * drawn,
; $0E = n - drawn + 1 if it stopped at the end of the line, else 0. $11 = 4m + 4 of the last metatile drawn,
; $10 = 0. Then A = the marker, X = $FF, Y = 0.
DEnd:   PHA
        LDA $01
        AND #$03
        CMP #$03
        BNE dn1
        LDA $00
        CMP #$A0
        BCS dn3
dn1:    LDA CE+1
        SEC
        SBC $00
        LSR A
        STA RCNT                ; drawn
        LDA CE+1
        CMP $00                 ; below the start: the row ended at the end of the page
        STA $00
        BCS dn2
        INC $01
dn2:    AND #$1F
        BNE dn2a
        LDA $0E
        SEC
        SBC RCNT
        CLC
        ADC #$01
        BNE dn2b
dn2a:   LDA #$00
dn2b:   STA $0E
dn3:    LDA SF+1                ; the last metatile drawn is just before the metatile address
        SEC
        SBC #$01
        STA $10
        LDA SF+2
        SBC #$00
        STA $11
        LDY #$00
        LDA ($10),Y
        ASL A
        ASL A
        CLC
        ADC #$04
        STA $11
        STY $10
        PLA
        LDX #$FF
        CMP #$FD
        BEQ de1
        JMP $EAF4               ; EndOfRoom
de1:    JMP $EACA               ; EndOfRoomObjects
