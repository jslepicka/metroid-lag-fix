; Faster metasprite -> OAM loop for Metroid (USA), fixed bank. Size-neutral.
; Rewrites $DEDC-$DFDE except the 5-byte exit at $DF2D; $DFDF/$E038 untouched.
; Zero page (as in the original): $00/$01 tile stream, $02/$03 placement stream,
; $04 flip flags (b7 V, b6 H), $05 attribute base, $0E X base, $0F placement index,
; $10 Y base, $11 tile stream index, $6B sprite control.
; New: $FB = precomputed attribute (unused by the game). $10 holds Ybase-1 while the
; loop runs (folds the original STA+DEC $0200,X) and is restored on exit.

        .org $DEDC
        BEQ $DF2D               ; was BEQ $DEE3 (JMP $DF2D)
        LDX $5B                 ; $DEDE entry (called from $DE32)
        DEC $10
        JMP Recalc
        NOP                     ; $DEE5 spare

; ---------------- region 1: $DEE6-$DF2C ----------------
        .org $DEE6
Loop:   LDY $11
Loop1:  LDA ($00),Y             ; tile or control byte
        CMP #$FC
        BCC Body
        JMP Ctrl
Body:   STA $0201,X
        INY
        STY $11
        LDA $FB                 ; precomputed attribute
        STA $0202,X
        LDY $0F
        LDA ($02),Y             ; Y placement
        BPL Yok
        CMP #$90
        BCC YSpec
Yok:    BIT $04
        BMI YFlip
Yadd:   CLC
        ADC $10                 ; Ybase-1
        STA $0200,X
        INY
        LDA ($02),Y             ; X placement
        BPL Xok
        CMP #$90
        BCC XSpec
Xok:    BIT $04
        BVS XFlip
Xadd:   CLC
        ADC $0E
        STA $0203,X
        INY
        STY $0F
        INX
        INX
        INX
        INX
        JMP Loop

; ---------------- $DF2D: original exit, untouched ----------------
        .org $DF2D
        LDA #$00
        STA $6B
        RTS

; ---------------- region 2: $DF32-$DFDE ----------------
        .org $DF32
YFlip:  EOR #$FF
        SEC
        ADC #$F8
        JMP Yadd

XFlip:  EOR #$FF
        SEC
        ADC #$F8
        JMP Xadd

; special Y placement ($80-$8F), as original $DF7B
YSpec:  .rom $DF7C,9              ; ExplodeYDisplace+$1
        BNE YS1
        LDY $4B
        ADC $0406,Y
        .byte $2C               ; BIT abs: skips ADC $65 (C and A unaffected)
YS1:    .rom $DF8F,12             ; ExplodeYDisplace+$14
        TAY
        PLA
        .rom $DF9D,3              ; ExplodeYDisplace+$22
        LDY $0F
        JMP Yok

; special X placement ($80-$8F), as original $DFB8
XSpec:  STY $0F
        LSR A                   ; C = direction bit of the special byte
        PHP
        .rom $DFB8,7              ; ExplodeXDisplace
        BEQ XS1
        LDA $65
XS1:    ASL A
        PLP
        BCS XS2
        .rom $DFCD,4              ; C=0 here
XS2:    .rom $DFD1,6              ; ExplodeXDisplace+$19
        TAY
        PLA
        .rom $DFD9,3              ; ExplodeXDisplace+$21
        LDY $0F
        JMP Xok

Ctrl:   BEQ CtrlFC
        CMP #$FD
        BEQ CtrlFD
        LSR A                   ; $FE -> C=0, $FF -> C=1 (exit C matches original)
        BCC CtrlFE
        STX $5B                 ; $FF: end
        INC $10
        JMP $DF2D

CtrlFE: INC $0F                 ; skip one placement entry
        INC $0F
        INC $11
        JMP Loop

CtrlFC: .rom $DF51,8              ; move origin by (dy, dx)
        INY
        LDA ($00),Y
        CLC
        ADC $0E
        STA $0E
        INY
        STY $11
        JMP Loop1

CtrlFD: .rom $DF3B,3              ; attribute / palette control
        BCC FDa
        .rom $DF40,3              ; GetNewControlByte+$5
        BNE FDb
FDa:    .rom $DF45,6              ; GetNewControlByte+$A
FDb:    .rom $DF4B,3              ; GetNewControlByte+$10
Recalc: .rom $DEFC,8              ; WriteSpriteRAM+$16
        STA $FB
        JMP Loop

; ---------------- $DCC3: metasprite header decode, in place (49 of 50 bytes) ----------------
; Same outputs as the original ($0F=0, $04, $05, the $6B/$E038 handling, X=A=(hdr&$0F)*2, Y=0):
; the 4 x LSR helper at $C2BF is inlined, and $04 is built with EOR ($00),Y instead of a
; store-then-EOR of the header byte.
        .org $DCC3
        LDY #$00
        STY $0F
        LDA ($00),Y             ; header byte
        TAX
        LSR A
        LSR A
        LSR A
        LSR A
        .rom $DCCF,19             ; GetSpriteCntrlData+$C
        EOR ($00),Y
        .rom $DCE4,4              ; GetSpriteCntrlData+$21
        BPL HD1
        .rom $DCEA,5              ; GetSpriteCntrlData+$27
HD1:    .rom $DCEF,6              ; GetSpriteCntrlData+$2C
        NOP                     ; $DCF4 spare
