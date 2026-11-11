; Samus vs frozen enemies (SamusCollisionWithSolidEntities, $D976): a scan that returns at once when no enemy
; is frozen, then quick rejects before the original test, including pairs across the screen seam (SfX, and
; VFast for the enemy-hit test in vertical rooms). Instructions kept from the original come from the input ROM
; (.rom).

;@chunk HookSolid $D976
        JMP SolidFast           ; the loop at $D983 runs from SfDL, subroutines inline

;@chunk SolidFast
SolidFast: .rom $D976,13          ; SamusCollisionWithSolidEntities: setup
        LDA #$04                ; enemy status 4 = frozen; slots $50 down to $00 as the loop
        CMP $6B44
        BEQ SfAny
        CMP $6B34
        BEQ SfAny
        CMP $6B24
        BEQ SfAny
        CMP $6B14
        BEQ SfAny
        CMP $6B04
        BEQ SfAny
        CMP $6AF4
        BEQ SfAny
        LDX #$F0                ; as the loop leaves it: X=$F0, C=0, V=0
        CLC
        CLV
        JMP $D9A3
SfAny:  LDX #$50
        JMP SfDL

;@chunk SfDone
SfDone: JMP $D9A3               ; X, Y, C, V as the loop left them

;@chunk SfTest
SfTest: .rom $F152,13             ; GetEnemyXSlotPosition
        .rom $F17F,6              ; GetEnemyXSlotPosition, after its JMP $F17F
        LDA $0A
        EOR $0B
        BNE SfX
        LDA $6AF5,X
        .rom $F1E0,6              ; $F1E0 inline: CLC / ADC $0301,Y / STA $04
        .rom $F202,5              ; as $F202: LDA $07 / SEC / SBC $06
        BCS f1
        EOR #$FF
        ADC #$01
f1:     CMP $04
        BCC f1k
        JMP SfDS
f1k:
        LDA $6AF6,X
        .rom $F1D9,6              ; $F1D9 inline: CLC / ADC $0302,Y / STA $05
        .rom $F23A,5              ; as $F23A: LDA $09 / SEC / SBC $08
        BCS f2
        EOR #$FF
        ADC #$01
f2:     CMP $05
        BCS fx1
        JMP FBslow
fx1:    JMP SfDS
; Different nametables. $F1FA needs both |dy| < $04 and |dx| < $05; the axis the nametable doesn't
; split (x in a vertical room, y in a horizontal one) is the plain 8-bit difference there too, so a
; miss on that axis is the same reject. Anything else takes the full check.
SfX:    LDA $49
        AND #$02
        BNE SfXh
        LDA $6AF6,X               ; vertical room: x
        .rom $F1D9,6              ; $F1D9 inline: CLC / ADC $0302,Y / STA $05
        .rom $F23A,5              ; as $F23A: LDA $09 / SEC / SBC $08
        BCS f3
        EOR #$FF
        ADC #$01
f3:     CMP $05
        BCS fx2
        JMP FBslow
fx2:    JMP SfDS
SfXh:   LDA $6AF5,X               ; horizontal room: y
        .rom $F1E0,6              ; $F1E0 inline: CLC / ADC $0301,Y / STA $04
        .rom $F202,5              ; as $F202: LDA $07 / SEC / SBC $06
        BCS f4
        EOR #$FF
        ADC #$01
f4:     CMP $04
        BCS fx3
        JMP FBslow
fx3:    JMP SfDS

;@chunk SfSlow
; Close enough that the quick rejects can't decide: the original radius sums ($F1BF) and exact test
; ($F1FA), then the loop's hit handling, as at $D98D-$D99C.
FBslow: JSR $F1BF
        JSR $F1FA
        BCS SfDS
        .rom $D9BA,13             ; SamusCollisionWithSolidEntities: hit handling ($D9BA-$D9D2)
SfNo:   .rom $D9C7,12
SfE8:   BNE SfDS
        INC $7D
        JMP SfDone
SfDS:   .rom $F1F4,5              ; Xminus16 inline
        BMI SfOut
SfDL:   .rom $D983,5              ; LDA $6AF4,X / CMP #$04, as the loop at $D983
        BNE SfDS
        JMP SfTest
SfOut:  JMP SfDone

;@chunk CrossX
; FastHit's CrossNT (WRAM $76A8) jumps here: vertical rooms take VFast, horizontal ones carry on.
CrossX: LDA $49
        AND #$02
        BNE cx1
        JMP VFast
cx1:    JMP $76AE

;@chunk VTail
VTail:  BCS VT1                 ; C=1: reject (RTS to FastHit's caller); C=0: full check
        JMP $F140
VT1:    RTS

;@chunk VFast
; FastHit across the nametable seam, vertical room ($49 & 2 = 0). X = enemy, Y = object, $07/$09/$0B from
; $F152. Same accept test as $F1FA: W = 256*($0B-$0A) + ($07-$06), pass if 0 <= |W|-16 < $04 and
; |$09-$08| < $05, with $0A = 1-$0B on the other nametable. C=1 reject, C=0 full check at $F140.
VFast:  LDA $6AF5,X
        .rom $F1E0,6              ; $F1E0 inline: CLC / ADC $0301,Y / STA $04
        LDA $07
        SEC
        SBC $030D,Y
        STA $05
        LDA $0B
        BEQ vB
        BCC vA0
        LDA $05                 ; $0B=1, no borrow: |W|-16 = d+240, needs d < 16
        CMP #$10
        BCS vrej
        ADC #$F0
        CMP $04
        BCS vrej
        BCC vx
vA0:    LDA $05                 ; $0B=1, borrow: |W|-16 = d-16, needs d >= 16
        SEC
        SBC #$10
        BCC vrej
        CMP $04
        BCS vrej
        BCC vx
vB:     BCC vB0
        LDA #$F0                ; $0B=0, no borrow: |W|-16 = 240-d, needs d <= 240
        SEC
        SBC $05
        BCC vrej
        CMP $04
        BCS vrej
        BCC vx
vB0:    LDA $05                 ; $0B=0, borrow: |W|-16 = 496-d, needs d >= 241
        CMP #$F1
        BCC vrej
        LDA #$F0
        SEC
        SBC $05
        CMP $04
        BCS vrej
vx:     LDA $6AF6,X
        .rom $F1D9,6              ; $F1D9 inline: CLC / ADC $0302,Y / STA $05
        LDA $09
        SEC
        SBC $030E,Y
        BCS vx1
        EOR #$FF
        ADC #$01
vx1:    CMP $05
        BCS vrej
        CLC
        JMP VTail
vrej:   SEC
        JMP VTail

;@chunk CrossP $76A8
        JMP CrossX              ; (WRAM: FastHit's CrossNT, patched each time WLoad runs)
        NOP
        NOP
        NOP
