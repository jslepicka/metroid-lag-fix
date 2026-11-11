; Metasprite pipeline rewrite for the 128K build (fixed bank). Same game state and OAM output as
; the original DrawEnemy / AnimDrawObject / ObjDrawFrame; scratch $00-$11 and $0C/$0D differ.
;
; Placement tables are re-laid out by the build script: each bank's placement region is split
; into a y block and an x block (x = y + N), and the pointer tables point 3 bytes before the y
; entries. One index register then addresses the tile stream and both placement bytes:
;   tile = ($00),Y   y = ($02),Y   x = ($06),Y
; Control bytes that use frame bytes without a placement (FD, FC) advance the frame pointer
; instead of Y; FE advances Y (one frame byte and one placement entry).
;
; Zero page while drawing: $00/$01 frame pointer, $02/$03 y placements, $06/$07 x placements,
; $04 flip flags, $05 attribute base, $0A Y operand, $0B X operand, $0C/$0D Y/X masks (LU),
; $0F OAM attribute, $10/$0E screen Y/X base (from $DFDF), $11 place index (special test).
; L00: no flip (y = dy + Ybase-1; x = dx + Xbase). L01: H flip only (x = (Xbase-8) - dx).
; LU: V flip, with or without H: y = (dy ^ $0C) + $0A, x = (dx ^ $0D) + $0B.
; LS: tables with special (explosion) placement bytes, with the original per-byte logic.
;
; Chunks (;@chunk NAME [ADDR]) are placed by the build script; an address pins a chunk.

NOBJ = $NOBJ

;@chunk EnStub $DD8B
        LDX $4B
        .rom $DD8D,5              ; DrawEnemy+$2
        BNE EnS
        .rom $DD94,3              ; DrawEnemy+$9

;@chunk EnS $DDB0
EnS:    ASL A
        TAY
        .rom $DDB0,15             ; DrawEnemy_NotBlank
        BCS EnT2
        LDA ($41),Y
        STA $00
        INY
        LDA ($41),Y
        BCC EnT                 ; always (C still clear)
EnT2:   LDA ($43),Y
        STA $00
        INY
        LDA ($43),Y
EnT:    STA $01
        LDY #$00                ; frame header (as Hdr): $04 flips, $05 attributes, Y = place index * 2
        LDA ($00),Y
        TAX
        LDA $6B
        AND #$10
        ASL A
        ASL A
        EOR ($00),Y
        STA $04
        BIT $6B
        BMI eho
        TXA
        LSR A
        LSR A
        LSR A
        LSR A
        TAY
        LDA PalT,Y
        STA $05
ehi:    TXA
        AND #$0F
        ASL A
        .rom $DDD8,10             ; DrawEnemy_NotBlank+$28
        STY $11                 ; place index*2+1: 3 = explosion table
        CPY #$03
        BEQ enx
        JMP EnR
enx:    JMP EnX
eho:    LDA $6B                 ; object attributes override the frame's (as $E038)
        AND #$7F
        STA $05
        TXA
        AND #$C0
        ORA $05
        STA $05
        JMP ehi

;@chunk EnR
EnR:    LDX $4B
        LDY #$01
        LDA ($00),Y
        STA $6AF5,X             ; radius Y
        .rom $DE3D,3              ; ReduceYRadius
        BCS EnR1
        LDA #$00
EnR1:   STA $08
        .rom $DE10,8              ; radius X
        JSR $DFDF               ; on screen? X = 1/0, $10/$0E = screen Y/X
        LDY $4B
        LDA $0405,Y
        AND #$FD
        DEX
        BNE EnOff
        ORA #$02
        STA $0405,Y
        LDX $23                 ; current bank: its enemy placement N
        LDA NE,X
        LDY $11
        CPY #$03
        BNE EnD
        JMP DrS
EnD:    JMP Dr0
EnOff:  STA $0405,Y
        JMP $DF2D

;@chunk EnX
EnX:    .rom $DDE8,8              ; explosion bookkeeping, as $DDE8
        JSR XRot
        BNE EnXr
        LDY #$00
        JMP $DCF5               ; EnemyCompleteDeath
EnXr:   JMP EnR

;@chunk XRot_P
; A = explosion counter: new flip bits into $05 from $DC8B (as the original); Z=1 when A = $19.
XRot:   .rom $DDF0,16             ; DrawEnemy_NotBlank+$40
        RTS

;@chunk ObjD $DE47
        .rom $DE47,3              ; AnimDrawObject
ObjD:   .rom $DE4A,7              ; ObjDrawFrame
        BNE ob0
        .rom $DE53,3              ; ObjDrawFrame+$9
ob0:    CMP #$07
        BNE Ob1
        LDA $6B
        AND #$EF
        STA $6B
        LDA #$07
Ob1:    ASL A
        TAY
        .rom $DE60,15             ; LDE60
        LDA $860B,Y
        STA $00
        LDA $860C,Y
        STA $01
        LDY #$00                ; frame header (as Hdr): $04 flips, $05 attributes, Y = place index * 2
        LDA ($00),Y
        TAX
        LDA $6B
        AND #$10
        ASL A
        ASL A
        EOR ($00),Y
        STA $04
        BIT $6B
        BMI oho
        TXA
        LSR A
        LSR A
        LSR A
        LSR A
        TAY
        LDA PalT,Y
        STA $05
ohi:    TXA
        AND #$0F
        ASL A
        TAY
        LDA $86DF,Y
        STA $02
        LDA $86E0,Y
        STA $03
        CPY #$0E
        BEQ ObX
ObR:    STY $11
        LDX $4B
        LDY #$01
        LDA ($00),Y
        STA $0301,X
        .rom $DE3D,3              ; ReduceYRadius
        BCS ObR1
        LDA #$00
ObR1:   STA $08
        .rom $DEC7,8              ; LDEBC+$B
        JSR $DFDF
        LDY $4B
        TXA
        STA $030B,Y             ; on-screen flag (Z from TXA)
        BEQ ObOff
        LDA #NOBJ
        LDY $11
        CPY #$0E
        BNE ObDr
        JMP DrS
ObDr:   JMP Dr0
ObOff:  JMP $DF2D
ObX:    LDA $55                 ; Samus exploding? (as $DE8B)
        BEQ ObR
        LDX $4B
        INC $65
        LDA $65
        JSR XRot
        BNE ObX1
        .rom $DEAB,17             ; LDE60+$4B
ObX1:   LDY #$0E
        JMP ObR
oho:    LDA $6B                 ; object attributes override the frame's (as $E038)
        AND #$7F
        STA $05
        TXA
        AND #$C0
        ORA $05
        STA $05
        JMP ohi

;@chunk Dr0
; Set up and enter a loop. In: A = N (x block offset).
Dr0:
        CLC                     ; as DrC: x placement pointer, Ybase-1 / Xbase, OAM attribute, X, Y
        ADC $02
        STA $06
        LDA $03
        ADC #$00
        STA $07
        LDA $10
        ADC #$FF
        STA $0A
        LDA $0E
        STA $0B
        .rom $DEFC,8              ; WriteSpriteRAM+$16
        STA $0F
        LDX $5B
        LDY #$03
        BIT $04
        BMI DrV
        BVS DrH
        JMP L00
DrH:    LDA $0B                 ; H only: x = (Xbase-8) - dx
        SEC
        SBC #$08
        STA $0B
        JMP L01
DrV:    LDA #$FF                ; y = (dy ^ $FF) + (Ybase-8)
        STA $0C
        LDA $0A
        SEC
        SBC #$07
        STA $0A
        LDA #$00
        BIT $04
        BVC DrV1
        LDA $0B                 ; x = (dx ^ $FF) + (Xbase-7)
        SEC
        SBC #$07
        STA $0B
        LDA #$FF
DrV1:   STA $0D
        JMP LU
DrS:    JSR DrC
        JMP LS

;@chunk DrC
; Common set-up: x placement pointer, Ybase-1 / Xbase operands, OAM attribute, X, Y.
DrC:    CLC
        ADC $02
        STA $06
        LDA $03
        ADC #$00
        STA $07                 ; C=0
        LDA $10
        ADC #$FF                ; Ybase-1 (folds the original DEC of OAM y)
        STA $0A
        LDA $0E
        STA $0B
        .rom $DEFC,8              ; WriteSpriteRAM+$16
        STA $0F
        LDX $5B
        LDY #$03
        RTS

;@chunk L00
L00:    LDA ($00),Y
        CMP #$FC
        BCS K00
        STA $0201,X
        LDA ($02),Y
        ADC $0A
        STA $0200,X
        LDA ($06),Y
        CLC
        ADC $0B
        STA $0203,X
        LDA $0F
        STA $0202,X
        INY
        INX
        INX
        INX
        INX
        JMP L00
K00:    CMP #$FF                ; end of frame
        BEQ K00E
        JSR Ctl
        JMP L00
K00E:   STX $5B
        JMP $DF2D

;@chunk L01
L01:    LDA ($00),Y
        CMP #$FC
        BCS K01
        STA $0201,X
        LDA ($02),Y
        ADC $0A
        STA $0200,X
        LDA $0B
        SEC
        SBC ($06),Y
        STA $0203,X
        LDA $0F
        STA $0202,X
        INY
        INX
        INX
        INX
        INX
        JMP L01
K01:    CMP #$FF                ; end of frame
        BEQ K01E
        JSR Ctl
        JMP L01
K01E:   STX $5B
        JMP $DF2D

;@chunk LU
LU:     LDA ($00),Y
        CMP #$FC
        BCS KU
        STA $0201,X
        LDA ($02),Y
        EOR $0C
        ADC $0A
        STA $0200,X
        LDA ($06),Y
        EOR $0D
        CLC
        ADC $0B
        STA $0203,X
        LDA $0F
        STA $0202,X
        INY
        INX
        INX
        INX
        INX
        JMP LU
KU:     CMP #$FF                ; end of frame
        BEQ KUE
        JSR Ctl
        JMP LU
KUE:    STX $5B
        JMP $DF2D

;@chunk Ctl
; Control bytes $FC-$FE (the loops handle $FF). Returns to the loop.
Ctl:    CMP #$FD
        BCC CFC
        BNE CFE
        INY                     ; $FD: new attribute byte
        LDA $6B
        BMI CFDo
        LDA ($00),Y
        STA $05
        JMP CFDa
CFDo:   AND #$7F                ; object attributes override (as $E038)
        STA $05
        LDA ($00),Y
        AND #$C0
        ORA $05
        STA $05
CFDa:   DEY
        .rom $DEFC,8              ; WriteSpriteRAM+$16
        STA $0F
        LDA #$02
        BNE Adv
CFE:    INY                     ; skip a placement
        RTS
CFC:    INY                     ; move the origin by (dy, dx)
        LDA ($00),Y
        CLC
        ADC $0A
        STA $0A
        INY
        LDA ($00),Y
        CLC
        ADC $0B
        STA $0B
        DEY
        DEY
        LDA #$03
Adv:    .rom $C2A9,5              ; frame bytes without a placement: move the frame pointer
        BCC Adv1
        INC $01
Adv1:   RTS

;@chunk LS
LS:     LDA ($00),Y
        CMP #$FC
        BCS KS
        STA $0201,X
        LDA $0F
        STA $0202,X
        LDA ($02),Y
        JSR SpY
        ADC $0A
        STA $0200,X
        LDA ($06),Y
        JSR SpX
        ADC $0B
        STA $0203,X
        INY
        INX
        INX
        INX
        INX
        JMP LS
KS:     CMP #$FF                ; end of frame
        BEQ KSE
        JSR Ctl
        JMP LS
KSE:    STX $5B
        JMP $DF2D

;@chunk Sp
; Placement byte in A, Y = entry. Returns the displacement (flip applied) with C=0, as the
; original YDisplacement / XDisplacement, including the explosion bytes ($80-$8F).
SpY:    STY $11
        PHA
        AND #$F0
        CMP #$80
        BEQ SpY1
        PLA
SpYf:   BIT $04
        BMI SpNeg
        CLC
        RTS
SpY1:   PLA
        .rom $DF7C,9              ; ExplodeYDisplace+$1
        BNE SpY2
        .rom $DF87,5              ; ExplodeYDisplace+$C
        JMP SpY3
SpY2:   ADC $65
SpY3:   TAY
        LDA $E04B,Y
        JSR Sp6
        ADC ($02),Y
        LDY $11
        JMP SpYf
SpNeg:  EOR #$FF
        SEC
        ADC #$F8
        CLC
        RTS
SpX:    STY $11
        PHA
        AND #$F0
        CMP #$80
        BEQ SpX1
        PLA
SpXf:   BIT $04
        BVS SpNeg
        CLC
        RTS
SpX1:   PLA
        LSR A
        PHP
        .rom $DFB8,7              ; ExplodeXDisplace
        BEQ SpX2
        LDA $65
SpX2:   ASL A
        PLP
        BCS SpX3
        EOR #$FF
        ADC #$01
SpX3:   JSR Sp6
        ADC ($06),Y
        LDY $11
        JMP SpXf
; Y = entry six on (the explosion base placement), with A kept and C=0.
Sp6:    PHA
        LDA $11
        CLC
        ADC #$06
        TAY
        PLA
        CLC
        RTS

;@chunk PalT
PalT:   .byte $20,$21,$22,$23,$60,$61,$62,$63,$A0,$A1,$A2,$A3,$E0,$E1,$E2,$E3

;@chunk NE_P
NE:     .byte $NE0,$NE1,$NE2,$NE3,$NE4,$NE5,$NE6,$NE7
