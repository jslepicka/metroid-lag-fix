; Unrolled HUD copy and unused-OAM clear. The long unrolled runs are generated at power-on
; (Gen, called by the power-on copier), so ROM only holds this static part.
;   OSEQ  $7400-$74BF  64 x STA $0200+4i                 (generated; page-aligned)
;   HFAST $6C80-$6D4A  40 x LDA #tpl / STA $0200+i,X, JMP HudTail   (generated)
        .org $CB66
        JMP OamClr              ; was LDX $5B / LDA #$F4 / loop via $E193
        .org $E0C7
        JSR HudCopy             ; was 40-byte LDA $E1B9,Y / STA $0200,X loop
        JMP $E0D3

        .org $74C0              ; static part starts right after OSEQ, which falls into OTail
OTail:  PLP                     ; C/V as the original left them
        LDX #$00                ; original exits with X=0, Z=1, N=0
        RTS
OTmp:   .byte $00
; Clear Y of every OAM entry from $5B to the end: jump into OSEQ at entry $5B/4.
OamClr: PHP
        LDA $5B
        LSR A
        LSR A
        STA OTmp
        ASL A
        CLC
        ADC OTmp                ; 3 * index (<= 189: stays in OSEQ's page)
        STA OJmp+1
        LDA #$F4
OJmp:   JMP $7400

HudCopy:
        CPX #$D9
        BCS HudSlow             ; would wrap past $02FF: keep the original byte loop
        JMP $6C80               ; HFAST
HudTail:
        TXA
        PHP                     ; keep V as the original loop leaves it
        CLC
        ADC #$28
        TAX
        PLP
        LDA #$28                ; original exits with A = last template byte
        LDY #$28
        CPY #$28                ; N=0 Z=1 C=1, as the original loop's last CPY
        RTS
HudSlow:
        LDY #$00
HS1:    .rom $E0C7,10             ; DisplayHUD+$6
        BNE HS1
        RTS

; Power-on generator for OSEQ and HFAST.
Gen:    LDY #$00
        LDX #$00
G1:     LDA #$8D                ; STA abs
        STA $7400,Y
        INY
        TXA                     ; low byte: 4 * entry
        STA $7400,Y
        INY
        LDA #$02
        STA $7400,Y
        INY
        INX
        INX
        INX
        INX
        BNE G1
        LDY #$00
        LDX #$00
G2:     LDA #$A9                ; LDA #imm
        STA $6C80,Y
        INY
        LDA $E1B9,X
        STA $6C80,Y
        INY
        LDA #$9D                ; STA abs,X
        STA $6C80,Y
        INY
        TXA
        STA $6C80,Y
        INY
        LDA #$02
        STA $6C80,Y
        INY
        INX
        CPX #$28
        BNE G2
        LDA #$4C                ; JMP HudTail
        STA $6D48
        LDA #<HudTail
        STA $6D49
        LDA #>HudTail
        STA $6D4A
        RTS
