; Samus's shots and Samus against each enemy (the loop at $F09D; replaces stage 1's loop in collide.asm). Same
; calls of FastHit ($7669, collide.asm), $F2CA and $F282 with the same registers and flags, so the same state:
;   - shot flags once per pass, as in collide.asm ($6F20/$6F30/$6F40): the hit handlers never change a shot's status
;   - whether Samus can be hit ($70 = 0 and $CE84: status not 7, 8 or $FF) once per pass, and again after
;     any hit handler runs; $CE84 only reads
;   - $F282 only when FastHit passes (on a reject it returns at once: BCS to an RTS)
;   - the enemy position ($F152, $F17F) inline

SOK  = $6F21                    ; 1: Samus can be hit

;@chunk HitJ $F09D
        JMP HitLoop

;@chunk HitLoop
HitLoop:
        LDY #$D0                ; shot flags
hl0:    LDX #$00
        LDA $0300,Y
        BEQ hl2
        .rom $F060,14             ; the shot-status test; its branches go to hl1 just below the BNE
        BNE hl2
hl1:    INX
hl2:    TXA
        STA $6E50,Y
        TYA
        CLC
        ADC #$10
        TAY
        BNE hl0
        JSR SamOK
        LDX #$50
EL:     LDA $6AF4,X
        BEQ EN
        CMP #$03
        BEQ EN
        .rom $F152,13             ; enemy position, as $F152: $07, $09, $0B
        EOR $FF
        AND #$01
        STA $0B
        LDA $6AF4,X
        CMP #$05
        BEQ ES
        LDA $6F20
        BEQ s2
        LDY #$D0
        JSR $7669
        BCS s2
        JSR ShotHit
s2:     LDA $6F30
        BEQ s3
        LDY #$E0
        JSR $7669
        BCS s3
        JSR ShotHit
s3:     LDA $6F40
        BEQ ES
        LDY #$F0
        JSR $7669
        BCS ES
        JSR ShotHit
ES:     LDY #$00
        LDA SOK
        BEQ EN
        JSR $7669
        BCS EN
        JSR $F282
        JSR SamOK
EN:     TXA
        SEC
        SBC #$10
        TAX
        BPL EL
        JMP $F0ED

;@chunk HitSub
ShotHit:
        JSR $F2CA
SamOK:  LDY $70                 ; (X kept; nothing after a call needs A, Y or the flags)
        BNE so0
        JSR $CE84               ; (leaves A = Samus's status)
        BEQ so0
        LDA #$01
        BNE so1
so0:    LDA #$00
so1:    STA SOK
        RTS

;@chunk CrossH $76D0
; As first written, FastHit across the seam in a horizontal room took the enemy's side from bit 0 of $6AFB,X, which is only
; right when bit 0 of $FF is 1; the side is $0B (bit 0 of $6AFB,X EOR $FF), which the loop has just set.
        LDA $0B
        NOP
        LSR A
        BCC $76E5               ; $0B = 0: hi = -1 - borrow; $0B = 1: carry on at $76D6 (hi = 1 - borrow)
