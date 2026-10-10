; KEYFEED.COM - deterministic keyboard feeder + screen snapshotter for DOSBox ground-truth runs.
;
; Reads KEYS.BIN at install and goes resident, hooking INT 16h.  KEYS.BIN is a list of records:
;   01 nlo nhi ascii scan flags   key: becomes available after exactly n "no key" peeks (AH=1);
;                                 a blocking read (AH=0) gets it at once.  flags bit0: take a
;                                 snapshot (16 KB CGA memory + 256 bytes BIOS data area) right
;                                 before the key is first reported/returned.
;   00                            end of script: once all snapshots are written, the running
;                                 program is terminated (INT 21h/4Ch) so the test run ends
; Snapshots are copied to one of three buffers and written to Dnnnn.BIN as soon as an INT 16h
; call happens while DOS is not active (InDOS = 0).
;
; nasm -f bin keyfeed.asm -o KEYFEED.COM

        org 100h
start:  jmp install

old16   dd 0
indos   dd 0
sptr    dw script
peeks   dw 0
snapped db 0
dumpno  dw 0
NSLOT   equ 3
SLOTSZ  equ 16384+256
slotno  dw 0FFFFh, 0FFFFh, 0FFFFh        ; dump number held by each slot, FFFF = free
fname   db 'D0000.BIN', 0
busy    db 0

; ---------------------------------------------------------------- INT 16h handler
int16:  sti
        cmp ah, 0
        je  .read
        cmp ah, 10h
        je  .read
        cmp ah, 1
        je  .peek
        cmp ah, 11h
        je  .peek
.chain: jmp far [cs:old16]

.peek:  call flush
        push si
        mov si, [cs:sptr]
        cmp byte [cs:si], 1
        jne .peek_end
        mov ax, [cs:si+1]
        cmp [cs:peeks], ax
        jae .peek_avail
        inc word [cs:peeks]
        pop si
        xor ax, ax
        cmp ax, ax                      ; ZF=1: no key
        retf 2
.peek_avail:
        call snap
        mov ax, [cs:si+3]               ; al=ascii ah=scan
        pop si
        or si, si                       ; si never 0 here? clear ZF explicitly:
        push bx
        mov bx, 1
        or bx, bx                       ; ZF=0: key available
        pop bx
        retf 2
.peek_end:
        pop si
        jmp endscript

.read:  call flush
        push si
        mov si, [cs:sptr]
        cmp byte [cs:si], 1
        jne .read_end
        call snap
        mov ax, [cs:si+3]
        add word [cs:sptr], 6
        mov word [cs:peeks], 0
        mov byte [cs:snapped], 0
        pop si
        iret
.read_end:
        pop si
        jmp endscript

; ---------------------------------------------------------------- end of script
; All snapshots written and DOS idle: terminate the running program so the test run ends at once.
endscript:
        push bx
        push es
        les bx, [cs:indos]
        cmp byte [es:bx], 0
        pop es
        pop bx
        jne .wait
        cmp word [cs:slotno], 0FFFFh
        jne .wait
        cmp word [cs:slotno+2], 0FFFFh
        jne .wait
        cmp word [cs:slotno+4], 0FFFFh
        jne .wait
        mov ax, 4C00h
        int 21h
.wait:  jmp far [cs:old16]

; ---------------------------------------------------------------- snapshot (no DOS calls)
snap:   ; cs:si -> current key record
        test byte [cs:si+5], 1
        jz .ret
        cmp byte [cs:snapped], 0
        jne .ret
        mov byte [cs:snapped], 1
        push ax
        push bx
        push cx
        push si
        push di
        push ds
        push es
        ; find a free slot
        xor bx, bx
.find:  cmp word [cs:slotno+bx], 0FFFFh
        je .got
        add bx, 2
        cmp bx, NSLOT*2
        jb .find
        jmp .done                       ; no free slot: snapshot lost (reported as missing file)
.got:   mov ax, [cs:dumpno]
        mov [cs:slotno+bx], ax
        inc word [cs:dumpno]
        ; di = slots + (bx/2)*SLOTSZ
        mov ax, bx
        shr ax, 1
        mov cx, SLOTSZ
        mul cx
        add ax, slots
        mov di, ax
        push cs
        pop es
        mov ax, 0B800h
        mov ds, ax
        xor si, si
        mov cx, 16384/2
        cld
        rep movsw
        mov ax, 40h
        mov ds, ax
        xor si, si
        mov cx, 128
        rep movsw
.done:  pop es
        pop ds
        pop di
        pop si
        pop cx
        pop bx
        pop ax
.ret:   ret

; ---------------------------------------------------------------- write pending snapshots
flush:  cmp byte [cs:busy], 0
        jne .r0
        push ax
        push bx
        push cx
        push dx
        push si
        push di
        push ds
        push es
        les bx, [cs:indos]
        cmp byte [es:bx], 0
        jne .out
        mov byte [cs:busy], 1
        push cs
        pop ds
        xor si, si                      ; slot index * 2
.loop:  cmp word [slotno+si], 0FFFFh
        je .next
        ; file name Dnnnn.BIN from slot's dump number
        mov ax, [slotno+si]
        mov di, fname+4
        mov cx, 4
.dig:   xor dx, dx
        mov bx, 10
        div bx
        add dl, '0'
        mov [di], dl
        dec di
        loop .dig
        mov ah, 3Ch
        xor cx, cx
        mov dx, fname
        int 21h
        jc .free
        mov bx, ax
        mov ax, si
        shr ax, 1
        mov cx, SLOTSZ
        mul cx
        add ax, slots
        mov dx, ax
        mov cx, SLOTSZ
        mov ah, 40h
        int 21h
        mov ah, 3Eh
        int 21h
.free:  mov word [slotno+si], 0FFFFh
.next:  add si, 2
        cmp si, NSLOT*2
        jb .loop
        mov byte [cs:busy], 0
.out:   pop es
        pop ds
        pop di
        pop si
        pop dx
        pop cx
        pop bx
        pop ax
.r0:    ret

script: times 8192 db 0
slots:  ; NSLOT * SLOTSZ bytes follow (not part of the file)
resend  equ slots + NSLOT*SLOTSZ

; ---------------------------------------------------------------- installer (discarded)
install:
        mov ax, 3D00h
        mov dx, kname
        int 21h
        jc .nofile
        mov bx, ax
        mov ah, 3Fh
        mov cx, 8192
        mov dx, script
        int 21h
        mov ah, 3Eh
        int 21h
.nofile:
        mov ah, 34h
        int 21h
        mov [indos], bx
        mov [indos+2], es
        mov ax, 3516h
        int 21h
        mov [old16], bx
        mov [old16+2], es
        mov ax, 2516h
        mov dx, int16
        int 21h
        mov dx, (resend - $$ + 100h + 15) / 16
        mov ax, 3100h
        int 21h
kname   db 'KEYS.BIN', 0
