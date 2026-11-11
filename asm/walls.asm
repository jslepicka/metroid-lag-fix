; The tile loop of the background collision checks ($E7DE-$E81D: entered from $E7DC and $E8BB with X/Y the
; step, (0,8) or (8,0)). Same tiles, calls, registers, flags and zero page at every exit. The room RAM pointer
; steps by a row (+32) or a column (+1) where the original rebuilds it with MakeRoomRAMPtr ($E96A) for each
; tile; where the original's step ($E98E) wraps, it runs $E98E's wrap and $E96A as before. $D651 inline; the
; area's $95C0 hook only in Tourian (bank 3: the other areas' $95C0 is an RTS).

;@chunk BGJ $E7DE
        JMP NewBG

;@chunk NewBG
nbs:    SEC
nbr:    RTS
NewBG:  BNE nbs
        .rom $E7E0,9              ; LE7DE+$2
nb1:    .rom $E7E9,6              ; LE7E6+$3
        BEQ nbd
        LDY $23
        CPY #$03
        BNE nb2
        LDY #$00
        JSR $95C0
nb2:    .rom $D651,10             ; $D651, the solid-tile test
nb3:    .rom $D65B,2
nb4:    BCC nbr                 ; solid: C=0
        CMP #$A0
        BCS nb5
        JMP $E9BE
nbd:    JMP $E81E
nb5:    LDY $55                 ; as $E800-$E812
        BEQ nb7
        .rom $E804,13             ; IsWalkableTile+$4
nb6:    .rom $E811,2
nb7:    .rom $E813,1
        BEQ nbs
        LDA $02                 ; the next tile
        CMP #$F0
        BCC nb8
        JMP nbw                 ; (y past the screen already: the original's step)
nb8:    LDA $06
        BEQ nbx
        CLC                     ; y += $06 (8)
        ADC $02
        STA $02
        CMP #$F0
        BCC nb9
        JMP nbw2
nb9:    LDA $04                 ; pointer += 32 (C=0)
        ADC #$20
        STA $04
        CLV                     ; (V as the original's step leaves it: its last ADC adds $07 = 0)
        BCC nb1
        INC $05
        JMP nb1
nbx:    .rom $E9A5,7              ; x += $07 (8); $02 + $06 = $02, below $F0
        BCC nb10
        JMP nbw3
nb10:   INC $04                 ; pointer += 1 (x/8 was at most 30)
        JMP nb1

;@chunk NewBGw
nbw:    JSR $E98E               ; the original's step and pointer
        JSR $E96A
        JMP nb1
nbw2:   ADC #$0F                ; y wrapped (C=1), as $E999-$E9A3; x + 0 needs nothing but V = 0
        STA $02
        CLV
        .rom $E935,4              ; CalculateFirstBGCollisionPoint+$26
        BNE nw2
        INC $0B
nw2:    JSR $E96A
        JMP nb1
nbw3:   .rom $E956,4              ; x carried, as $E9AE-$E9B4
        BEQ nw3
        INC $0B
nw3:    JSR $E96A
        JMP nb1
