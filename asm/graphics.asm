;@chunk GfxJ $C7AB
        JMP LGfx                ; LoadGFX: the table now lives in bank 6

;@chunk LGfx
; LoadGFX with the GFXInfo table moved to bank 6 at GFXT (7-byte entries, as the original).
LGfx:   LDA #$FF
LG1:    .rom $C7AD,4              ; LoadGFX+$2
        BPL LG1
        PHA
        LDY #$06
        JSR $C4EF               ; BankSwitch to 6 (Y kept)
        PLA
        TAY
        LDX #$06
LG2:    LDA GFXT,Y
        .rom $C7B9,4              ; LoadGFX+$E
        BPL LG2
        .rom $C7BF,22             ; the graphics' bank; CopyGFXBlock; back to the current bank

;@chunk LoadList
; The pattern-table set-ups (were LDY #id / JSR LoadGFX sequences at $C5D7-$C6DF): X = list offset in
; GLIST (bank 6). $FE: load the next id only if Samus has no suit ($69B3); $FF: end. Ends like the
; originals: current bank mapped, A = Y = bank, X = $FF.
LoadList: TXA
        PHA
        LDY #$06
        JSR $C4EF
        JSR WLOADA              ; (bank 6) the WRAM code, every time graphics are set up
        PLA
        TAX
ll0:    LDY #$06
        JSR $C4EF
        LDA GLIST,X
        INX
        CMP #$FF
        BEQ ll9
        CMP #$FE
        BNE ll2
        LDA GLIST,X
        INX
        LDY $69B3
        BEQ ll0
ll2:    TAY
        TXA
        PHA
        JSR $C7AB
        PLA
        TAX
        JMP ll0
ll9:    LDX #$FF
        LDY $23
        JMP $C4EF

;@chunk GTitle
GTitle:  LDX #$00
        JMP LoadList

;@chunk GTitle2
GTitle2:  LDX #$01
        JMP LoadList

;@chunk GBrin
GBrin:  LDX #$0A
        JMP LoadList

;@chunk GNorf
GNorf:  LDX #$11
        JMP LoadList

;@chunk GTour
GTour:  LDX #$19
        JMP LoadList

;@chunk GKraid
GKraid:  LDX #$24
        JMP LoadList

;@chunk GRidl
GRidl:  LDX #$2D
        JMP LoadList

;@chunk GEnd
GEnd:  LDX #$35
        JMP LoadList

;@chunk GC6D6
GC6D6:  LDX #$3A
        JMP LoadList

;@chunk PC54C $C54C
        JSR GTitle
;@chunk PC572 $C572
        JSR GBrin
;@chunk PC58A $C58A
        JSR GNorf
;@chunk PC5A2 $C5A2
        JSR GTour
;@chunk PC5BD $C5BD
        JSR GKraid
;@chunk PC5CA $C5CA
        JSR GRidl
;@chunk PC5D4 $C5D4
        JMP GEnd

;@chunk HookNtF $E5BF
        JSR NtF                 ; was JSR SeparateControlBits

;@chunk NtF
; UpdateNameTable's data, in place of JSR SeparateControlBits (A = control byte, X = VRAM buffer index,
; Y = 0). When the control byte and the whole column or row fit in the buffer, copy all but the last
; byte here (the original loop costs ~70 cycles a byte) and leave $00/$01 where the original would be
; with one byte to go: the original loop does the last byte and ends with its own registers, flags
; and zero page. Otherwise SeparateControlBits and the original loop run exactly as before (including
; the buffer-full exit, which drops UpdateNameTable's return address).
NtF:    PHP
        PHA
        AND #$3F
        STA $05                 ; the count (SeparateControlBits stores the same)
        TXA
        CLC
        ADC $05
        CMP #$4E
        PLA
        BCS nfo
        PLP
        JSR $C3C6               ; cannot fill the buffer now
        LDA $05
        SEC
        SBC #$01
        STA $06                 ; bytes to copy here ($06 ends 0 in the original too)
        BIT $04
        BMI nfc
nfr:    LDA ($00),Y             ; a row: stride 1
        STA $07A1,X
        INX
        INY
        CPY $06
        BNE nfr
        BEQ nfe
nfc:    LDA ($00),Y             ; a column: stride 32
        STA $07A1,X
        INX
        TYA
        CLC
        ADC #$20
        TAY
        BCC nfc1
        INC $01
nfc1:   DEC $06
        BNE nfc
nfe:    .rom $C2A8,6              ; $00/$01 += what Y covered ($01 already carried)
        BCC nfe1
        INC $01
nfe1:   LDA #$01
        STA $05
        LDY #$00
        RTS
nfo:    PLP
        JMP $C3C6

;@chunk PBoot $C06D
        JSR FixFF               ; was LDA #$0E / STA $25 (stage 1 hooked its power-on copier here)
        NOP

;@chunk FixFF
; $FF (the PPUCTRL copy) = 0 first: ClearNameTables ($C084) writes $2000 from $FF before $C08F sets it,
; and an uninitialized $FF can turn NMI on in the middle of the start-up code.
FixFF:  LDA #$00
        STA $FF
        LDA #$0E
        STA $25
        RTS
