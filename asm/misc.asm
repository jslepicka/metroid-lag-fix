; Skip dispatches that would only return, tighten the blasted-block loop ($0500), drop a dead call.
; NullDisp and ObjLoop live in WRAM after the HUD/OAM code.

; --- dispatch sites whose index 0 entry is $C45C (RTS): return directly for index 0
        .org $D7BA
        JSR NullDisp
        .org $D4D0
        JMP PrDisp              ; projectile status dispatch (table at $D4D3), see PrDisp
        .org $F36B
        JMP EnDisp              ; enemy status dispatch (table at $F36E), see EnDisp
        .bank 1
        .org $8B8C
        JSR NullDisp
        .bank 2
        .org $8B8C
        JSR NullDisp
        .bank 3
        .org $8B8C
        JSR NullDisp
        .bank 4
        .org $8B8C
        JSR NullDisp
        .bank 5
        .org $8B8C
        JSR NullDisp
        .bank -

; --- $0500 object loop
        .org $FE1B
        JMP ObjLoop

; Reset: enable NMI only once the vblank flag has been seen (and cleared by the $2002 read), so
; the extra power-on copy time can never put this write inside vblank, where it would fire an
; NMI in the middle of initialization. A = $90 from the original LDA at $C08A.
        .org $C08C
        JSR NmiOn               ; was STA $2000
        .org $FE1E              ; 9 bytes left free by the JMP at $FE1B
NmiOn:  BIT $2002
        BPL NmiOn
        STA $2000
        RTS

; --- enemy draw: $DE3D only computes $08, which $DE20 overwrites before any read
        .org $DC7F
        JMP FastObj             ; box test fast reject, see FastObj

        .org $DE0D
        BIT $DE3D               ; 3-byte no-op in place of JSR $DE3D

        .org $CB69              ; 10 fixed-bank bytes freed by the JMP at $CB66
; Index 0 at these sites dispatches to $C45C (RTS), i.e. return to the site
; routine's caller. Drop the inline-table return address and return. X/Y untouched,
; as $C27C would restore them; $C27C's scratch ($0C/$0D/$69/$6A) is not written.
NullDisp:
        CMP #$00
        BNE ND1
        PLA
        PLA
        RTS
ND1:    JMP $C27C

        .org WRAM_MISC
; Enemy status dispatch for $F36B: jump through the inline table at $F36E directly. X and Y reach
; the target untouched, as with $C27C; index 0 ($C45C, an RTS) returns to $F351's caller.
EnDisp: ASL A                   ; 2 * status; Z set for status 0
        BEQ EDnull
        CLC
        ADC #$6E
        STA EDl+1
        ADC #$01
        STA EDh+1
EDl:    LDA $F36E
        STA EDj+1
EDh:    LDA $F36F
        STA EDj+2
EDj:    JMP $C45C
EDnull: RTS

; Projectile status dispatch for $D4D0, same scheme as EnDisp (12-entry table at $D4D3).
PrDisp: ASL A
        BEQ EDnull
        CLC
        ADC #$D3
        STA PDl+1
        ADC #$01
        STA PDh+1
PDl:    LDA $D4D3
        STA PDj+1
PDh:    LDA $D4D4
        STA PDj+2
PDj:    JMP $C45C

; $DC7F box test (object X vs object Y): exact reject when both are on the same nametable;
; otherwise the original JSR $F186 / $DC82 path, which computes everything the callers read.
FastObj:
        LDA $030C,X
        EOR $030C,Y
        LSR A
        BCS FOslow
        LDA $0301,X
        CLC
        ADC $0301,Y
        STA $04
        LDA $030D,X
        SEC
        SBC $030D,Y
        BCS FO1
        EOR #$FF
        ADC #$01
FO1:    CMP $04
        BCS FOrej
        LDA $0302,X
        CLC
        ADC $0302,Y
        STA $05
        LDA $030E,X
        SEC
        SBC $030E,Y
        BCS FO2
        EOR #$FF
        ADC #$01
FO2:    CMP $05
        BCS FOrej
FOslow: JSR $F186
        JMP $DC82
FOrej:  RTS

; $FE1B: slots $C0..$10 skip empty ones without the $FE27/$F1F4 calls; slot 0 falls
; into $FE27 exactly as the original's fall-through does.
ObjLoop:
        LDX #$C0
OL:     STX $4B
        LDA $0500,X
        BEQ OS
        JSR $FE2E               ; the dispatch half of $FE27
        LDX $4B
OS:     TXA
        SEC
        SBC #$10
        TAX
        BNE OL
        JMP $FE27
