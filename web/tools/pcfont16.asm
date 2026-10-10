; PCFONT16.COM - write the VGA BIOS 8x16 character set of the machine it runs on to PCFONT16.BIN
; (4096 bytes: 256 glyphs x 16 rows, top row first, leftmost pixel = most significant bit),
; using INT 10h AX=1130h BH=06h (get pointer to the 8x16 font).
;   nasm -f bin pcfont16.asm -o PCFONT16.COM

        org 100h
        mov ax, 1130h
        mov bh, 06h
        int 10h                 ; ES:BP -> 8x16 font
        push es
        pop ds
        mov si, bp
        push cs
        pop es
        mov di, buf
        mov cx, 4096
        cld
        rep movsb
        push cs
        pop ds
        mov ah, 3Ch
        xor cx, cx
        mov dx, fname
        int 21h
        jc .done
        mov bx, ax
        mov ah, 40h
        mov cx, 4096
        mov dx, buf
        int 21h
        mov ah, 3Eh
        int 21h
.done:  mov ax, 4C00h
        int 21h
fname   db 'PCFONT16.BIN', 0
buf:
