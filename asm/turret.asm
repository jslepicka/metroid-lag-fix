; Tourian turrets: draw the one-sprite turret frames directly instead of through the generic
; enemy metasprite path ($9C2B -> $803C -> $DD8B -> ... -> tile loop). Output matches the generic
; path: slot $E0 fields, $0405,X bit 1, the OAM entry, $5B and $6B=0; on-screen test via $DFDF.
; Falls back to the original code when $6B != 0 (the generic path's flip/palette modifiers).

        .bank 3
        .org $9C2B
        JMP Turret
        .bank -

        .org WRAM_TURRET
Turret: LDY $6BF9,X             ; original first instruction
        LDA $6B
        BNE TSlow
        LDA $9DC6,Y             ; frame id
        CMP #$06
        BCC TSlow
        CMP #$0E
        BCC TFast
TSlow:  JMP $9C2E               ; generic path, exactly as before
TFast:  .rom 3:$9C31,9            ; DrawCannon_Escape
        STA $0A
        LDA $6BF6,X
        STA $04E1
        STA $0B
        LDA $6BF7,X
        STA $6BDB
        STA $06
        LDA #$E0
        STA $4B
        LDA #$07
        STA $6BD5               ; radii from the frame header (all turret frames: 7, 7)
        STA $6BD6
        STA $09
        JSR $DFDF               ; on-screen test: X = 0/1, $10 = Y base, $0E = X base
        TXA
        ASL A
        STA $08
        LDA $04E5
        AND #$FD
        ORA $08
        STA $04E5
        LDA $08
        BEQ TOff
        LDY $6BD7               ; $DFDF used Y
        LDX $5B
        LDA TFY-6,Y
        CLC
        ADC $10
        SEC
        SBC #$01                ; generic path stores Y then DEC
        STA $0200,X
        LDA TTile-6,Y
        STA $0201,X
        LDA TAttr-6,Y
        STA $0202,X
        LDA TFX-6,Y
        CLC
        ADC $0E
        STA $0203,X
        INX
        INX
        INX
        INX
        STX $5B
TDone:  LDA #$00
        STA $6B
        RTS
TOff:   LDX #$E0                ; generic off-screen exit leaves X = $4B
        JMP TDone
TFY:    .byte $F1,$F3,$FC,$05,$07,$05,$FC,$F3
TFX:    .byte $FC,$F3,$F1,$F3,$FC,$05,$07,$05
TTile:  .byte $EA,$EB,$EC,$EB,$EA,$EB,$EC,$EB
TAttr:  .byte $22,$22,$22,$A2,$A2,$E2,$62,$62
