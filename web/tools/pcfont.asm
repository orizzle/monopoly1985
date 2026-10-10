; PCFONT.COM - write the BIOS 8x8 character set of the machine it runs on to PCFONT.BIN
; (2048 bytes: 256 glyphs x 8 rows, top row first, leftmost pixel = most significant bit).
; Characters 0..127 come from the BIOS table at F000:FA6E (IBM PC/XT/AT and compatibles,
; including DOSBox), characters 128..255 from the table that the INT 1Fh vector points to
; (zero-filled if that vector is not set).
;   nasm -f bin pcfont.asm -o PCFONT.COM

        org 100h
        push ds
        pop es
        mov di, buf
        mov ax, 0F000h
        mov ds, ax
        mov si, 0FA6Eh
        mov cx, 1024
        cld
        rep movsb
        xor ax, ax
        mov ds, ax
        lds si, [1Fh*4]
        mov ax, ds
        or ax, si
        jz .noupper
        mov cx, 1024
        rep movsb
        jmp .write
.noupper:
        push es
        pop ds
        xor al, al
        mov cx, 1024
        rep stosb
.write:
        push cs
        pop ds
        mov ah, 3Ch
        xor cx, cx
        mov dx, fname
        int 21h
        jc .done
        mov bx, ax
        mov ah, 40h
        mov cx, 2048
        mov dx, buf
        int 21h
        mov ah, 3Eh
        int 21h
.done:  mov ax, 4C00h
        int 21h
fname   db 'PCFONT.BIN', 0
buf:
