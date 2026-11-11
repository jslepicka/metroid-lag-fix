; Sound engine (NMI, every frame): the routine at $B4BD in the code banks 0-5 share. With A = a channel
; group's request bits and X = its table ($B200+X: four bytes to $E0-$E3, one to $065C), it finds the first
; request bit and leaves its handler pointer in $E2/$E3 (or the table's default). The original copies with
; ($E4),Y and finds the bit by shifting $064D in memory eight times, ~265 cycles with no request, about ten
; times a frame. Same exits: no request: A = 0, Y = $10, C = 1, Z = 1, N = 0; request: Y = 2i+1, A = the
; request bits, C = 1; $E0-$E5, $064D and $065C as the original; X and V kept. $B4EE must stay an RTS: the
; handler tables point at it (and nothing reads these bytes as data in banks 0-5, checked by watching every read).

;@chunk SndJ $B4BD
        STA $064D
        STX $E4
        LDA #$B2
        STA $E5
        LDA $B200,X
        STA $E0
        LDA $B201,X
        STA $E1
        LDA $B202,X
        STA $E2
        LDA $B203,X
        STA $E3
        LDA $B204,X
        .rom 0:$B4D5,8            ; CopyMap+$B97
        BEQ sn0
        BNE sw
sn0:    LDY #$10                ; (the RTS stays at $B4EE: the tables' default handler)
        LDA #$00
        SEC
        RTS
sw:     PHA
sl:     ASL A
        BCS sf
        INY
        INY
        BNE sl
sf:     JMP SndF

;@chunk SndF_P
SndF:   .rom 0:$B4EF,9            ; as $B4EF-$B4F6, then $B4EA-$B4EE ($064D was never changed)
        PLA
        RTS

;@chunk PadJ $C228
; The joypad bit loop (NMI, both controllers, every frame): the original keeps the result in A through PHA/PLA
; and ORs bits 0 and 1 through $00, 28 cycles a bit. Same eight reads of $4016,X; A = the result as before.
; $00 is overwritten right after (STY $00 at $C23D) and the carry left here is dead (the next carry use is the
; CMP at $C257).
        LDY #$08
pl:     LDA $4016,X
        AND #$03
        CMP #$01                ; C = bit 0 or bit 1
        ROL $00
        DEY
        BNE pl
        LDA $00
        NOP
