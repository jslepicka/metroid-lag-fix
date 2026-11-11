; Stage 1's enemy-hit loop (replaced in stage 2 by hit_loop.asm) and FastHit, the exact quick reject that
; hit_loop.asm still calls. Runs from work RAM.
;
; FastHit (X = enemy slot, Y = object slot) returns C=1 for a pair the original $F140
; would reject, without touching anything but $04/$05. Pairs on different nametables
; or that might hit go to the original $F140, which computes every output the hit
; handlers read.
;   same nametable  <=> bit0($030C,Y) == bit0($6AFB,X)   ($0A/$0B in the original)
;   $04 = $6AF5,X + $0301,Y,  reject if |$07 - $030D,Y| >= $04
;   $05 = $6AF6,X + $0302,Y,  reject if |$09 - $030E,Y| >= $05

        .org $F09D
        JMP NewC

        .org WRAM_COLLIDE       ; work RAM
NewC:   LDY #$D0                ; once per pass: which of Samus's shots can hit enemies
NC1:    LDX #$00
        LDA $0300,Y
        BEQ NC3
        .rom $F060,14             ; the shot-status test; its branches go to NC2 just below the BNE
        BNE NC3
NC2:    INX
NC3:    TXA
        STA $6E50,Y             ; flags at $6F20/$6F30/$6F40 (spare WRAM)
        TYA
        CLC
        ADC #$10
        TAY
        BNE NC1
        LDX #$50
EL:     LDA $6AF4,X
        BEQ ENext
        CMP #$03
        BEQ ENext
        .rom $F0A8,8              ; enemy position -> $07/$09/$0B
        BEQ ESam
        LDA $6F20               ; shot $D0
        BEQ S1
        LDY #$D0
        JSR FastHit
        BCS S1
        JSR $F2CA
S1:     LDA $6F30               ; shot $E0
        BEQ S2
        LDY #$E0
        JSR FastHit
        BCS S2
        JSR $F2CA
S2:     LDA $6F40               ; shot $F0
        BEQ ESam
        LDY #$F0
        JSR FastHit
        BCS ESam
        JSR $F2CA
ESam:   .rom $F0D4,4              ; enemy vs Samus
        BNE ENext
        .rom $F0DA,3              ; CollisionDetection+$A6
        BEQ ENext
        JSR FastHit
        JSR $F282
ENext:  TXA
        SEC
        SBC #$10
        TAX
        BPL EL
        JMP $F0ED

FastHit:
        LDA $030C,Y
        EOR $6AFB,X
        LSR A
        BCS CrossNT             ; different nametables
        LDA $6AF5,X
        CLC
        ADC $0301,Y
        STA $04
        LDA $07
        SEC
        SBC $030D,Y
        BCS FH1
        EOR #$FF
        ADC #$01                ; C=0 here: A = -A
FH1:    CMP $04
        BCS Rej
        LDA $6AF6,X
        CLC
        ADC $0302,Y
        STA $05
        LDA $09
        SEC
        SBC $030E,Y
        BCS FH2
        EOR #$FF
        ADC #$01
FH2:    CMP $05
        BCS Rej
Full:   JMP $F140
Rej:    RTS

; Pair straddles the nametable seam. In a vertically scrolling room ($49&2 == 0) the
; original adjusts dy by the 240-line gap: leave that to $F140. In a horizontal room dy
; is plain and dx is 16-bit: hi = $0B - $0A - borrow, $0B = ~bit0($6AFB,X), $0A = ~bit0($030C,Y).
CrossNT:
        LDA $49
        AND #$02
        BEQ Full
        LDA $6AF5,X
        CLC
        ADC $0301,Y
        STA $04
        LDA $07
        SEC
        SBC $030D,Y
        BCS CN1
        EOR #$FF
        ADC #$01
CN1:    CMP $04
        BCS Rej
        LDA $6AF6,X
        CLC
        ADC $0302,Y
        STA $05
        LDA $6AFB,X
        LSR A
        BCS CNB
        LDA $09                 ; enemy on NT0 ($0B=1): hi = 1 - borrow
        SEC
        SBC $030E,Y
        BCS Rej                 ; no borrow: |dx| >= 256
        CMP $05
        BCS Rej
        JMP $F140
CNB:    LDA $09                 ; enemy on NT1 ($0B=0): hi = -1 - borrow
        SEC
        SBC $030E,Y
        BCC RejSet              ; borrow: |dx| > 256 (C=0 here, so set it)
        BEQ Rej                 ; exactly -256 (C=1)
        EOR #$FF
        ADC #$00                ; C=1: A = -A
        CMP $05
        BCS Rej
        JMP $F140
RejSet: SEC
        RTS

; FastBox: exact reject for JSR $F1BF / JSR $F1FA with positions already in $06-$0B.
FastBox:
        LDA $0A
        EOR $0B
        BNE FBslow
        LDA $6AF5,X
        CLC
        ADC $0301,Y
        STA $04
        LDA $07
        SEC
        SBC $06
        BCS FB1
        EOR #$FF
        ADC #$01
FB1:    CMP $04
        BCS FBrej
        LDA $6AF6,X
        CLC
        ADC $0302,Y
        STA $05
        LDA $09
        SEC
        SBC $08
        BCS FB2
        EOR #$FF
        ADC #$01
FB2:    CMP $05
        BCS FBrej
FBslow: JSR $F1BF
        JMP $F1FA
FBrej:  RTS

; Samus vs frozen (status 4) enemies, in place at $D976 (same size; $D9A3 on unchanged)
        .org $D976
        .rom $D976,13             ; SamusCollisionWithSolidEntities
DL:     .rom $D983,5              ; SamusCollisionWithSolidEntities+$D
        BNE DS
        JSR $F152
        JSR FastBox
        BCS DS
        .rom $D995,3              ; SamusCollisionWithSolidEntities+$1F
        BNE DS
        INC $7D
        BNE DX
DS:     TXA
        SEC
        SBC #$10
        TAX
        BPL DL
        NOP
DX:
