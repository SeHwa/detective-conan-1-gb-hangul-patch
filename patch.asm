CURRENT_PAGE_NUM: equ $C412
VAR_TEMP_CODE: equ $C4FC
VAR_IS_FIRST: equ $C4FE
VAR_TEXT_TYPE: equ $C4FF

    org $0062
Hook_quiz_tilemap_data:
    ld a, $43
    cp h
    jr nz, Hook_quiz_tilemap_data_fallback
    ld a, $68
    cp l
    jr nz, Hook_quiz_tilemap_data_fallback
    ld hl, $7F60
    ld a, (VAR_TEXT_TYPE)
    sla a
    sla a
    sla a
    add l
    ld l, a
Hook_quiz_tilemap_data_fallback:
    ld de, $C266
    jp $0A58

    db $77,$77,$77,$77

Hook_quiz_tilemap_index:
    ld a, $44
    cp h
    jr nz, Hook_quiz_tilemap_index_fallback
    ld a, $7D
    cp l
    jr z, Hook_quiz_tilemap_index_br1
    ld a, $80
    cp l
    jr nz, Hook_quiz_tilemap_index_fallback
    ld hl, $7F73
    jr Hook_quiz_tilemap_index_br2
Hook_quiz_tilemap_index_br1:
    ld hl, $7F70
Hook_quiz_tilemap_index_br2:
    ld a, (VAR_TEXT_TYPE)
    sla a
    sla a
    sla a
    sla a
    add l
    ld l, a
Hook_quiz_tilemap_index_fallback:
    ldi a, (hl)
    ld c, a
    ldi a, (hl)
    ret

    db $77,$77,$77,$77

Hook_quiz_tile_data:
    ld l, a
    ld c, $06

    ld a, $41
    cp d
    jr nz, Hook_quiz_tile_data_fallback
    ld a, $7A
    cp e
    jr nz, Hook_quiz_tile_data_fallback
    ld de, $7F90
    ld a, (VAR_TEXT_TYPE)
    sla a
    sla a
    sla a
    add e
    ld e, a
Hook_quiz_tile_data_fallback:
    jp $0730

    db $77,$77,$77,$77

Hook_quiz_print_font:
    push af
    ld a, $1F
    rst $18
    ld hl, $4F00
    ld a, (VAR_TEXT_TYPE)
    rrca
    rrca
    add l
    ld l, a
    pop af
    sla a
    add l
    ld l, a
    ldi a, (hl)
    ld (VAR_TEMP_CODE), a
    ld a, (hl)
    ld (VAR_TEMP_CODE+1), a
    ld a, ($C01D)
    rst $18

    ld a, $FF
    ld ($C2CA), a
    ld a, (VAR_TEMP_CODE)
    ld hl, $5421
    push hl
    ld hl, VAR_TEMP_CODE
    jp $230A

    db $88,$88,$88,$88

    org $3EF0
Hook_readcode:
    ld a, h
    and $F0
    cp $F0
    jr z, Hook_readcode_str_in_newbank
    ldi a, (hl)
    ld d, a
    ld a, (hl)
    ld e, a
Hook_readcode_str_in_newbank:
    ld a, $1F
    rst $18
    jp NEWBANK_Hook_readcode
    
    db $77,$77,$77,$77

Hook_calcfontaddr:
    push af
    ldi a, (hl)
    cp $E0
    jr c, Hook_calcfontaddr_fallback
    cp $EA
    jr nc, Hook_calcfontaddr_fallback
    sub $E0
    ld b, a
    ldi a, (hl)
    ld (de), a
    inc de
    ld a, b
    ld (de), a
    inc de
    jp $65F
Hook_calcfontaddr_fallback:
    push hl
    jp $642

    db $77,$77,$77,$77

Hook_printfont:
    push hl
    ldi a, (hl)
    ld c, a
    ld a, (hl)
    cp $0A
    jr nc, Hook_printfont_fallback
    sra a
    sra a
    add $10
    ld ($2100), a
    ld a, (hl)
    and 0b00000011
    swap a
    or $40
    ld h, a
    ld a, c
    and $F0
    swap a
    or h
    ld h, a
    ld a, c
    swap a
    and $F0
    jp $352
Hook_printfont_fallback:
    push af
    ld a, $0F
    ld ($2100), a
    pop af
    ld h, a
    ld a, c
    jp $352

    db $77,$77,$77,$77

Hook_load_tilemap_info:
    ld a, (CURRENT_PAGE_NUM)
    cp $77
    jr c, Hook_load_tilemap_info_fallback
    ld bc, $0128
    jp $999
Hook_load_tilemap_info_fallback:
    call $AF3
    jp $999

    db $77,$77,$77,$77

Hook_add_page_handler_table:
    ld a, (CURRENT_PAGE_NUM)
    cp $77
    jr c, Hook_add_page_handler_table_fallback
    jr nz, Hook_add_page_handler_table2
    ld hl, $2C33
    jp (hl)
Hook_add_page_handler_table2:
    ld hl, $2C39
    jp (hl)
Hook_add_page_handler_table_fallback:
    jp $2B1F

    db $77,$77,$77,$77

Hook_start_menu_next_page:
    ld hl, CURRENT_PAGE_NUM
    ld a, (hl)
    cp $03
    jr nz, Hook_start_menu_next_page_fallback
    ld a, (VAR_IS_FIRST)
    cp $01
    jr z, Hook_start_menu_next_page_fallback
    ld a, $01
    ld (VAR_IS_FIRST), a
    ld a, $77
    ld (hl), a
    ret
Hook_start_menu_next_page_fallback:
    jp $2B8A

    db $77,$77,$77,$77

Hook_get_text:
    add hl, bc
    ld a, (VAR_TEXT_TYPE)
    rrca
    ld c, a
    ld b, $00
    add hl, bc
    ld a, $12
    jp $19F4

    db $77,$77,$77,$77

Hook_set_cursor_sprite_pos:
    ld b, a
    ld a, (CURRENT_PAGE_NUM)
    cp $77
    ld a, b
    jr c, Hook_set_cursor_sprite_pos_fallback
    xor a
    ld ($C3F3), a
    ld a, $54
    jp $303E
Hook_set_cursor_sprite_pos_fallback:
    ld ($C3F3), a
    jp $3039

    db $77,$77,$77,$77

Hook_get_menu_text:
    ld a, (CURRENT_PAGE_NUM)
    cp $77
    jr c, Hook_get_menu_text_fallback
    ld hl, $76B7
    jp $7154
Hook_get_menu_text_fallback:
    ld hl, $7694
    jp $7154

    db $77,$77,$77,$77

Hook_get_text_address:
    ld hl, $C2C2
    ldi a, (hl)
    ld h, (hl)
    ld l, a
    ld a, h
    and $F0
    cp $F0
    jr nz, Hook_get_text_address_str_not_in_newbank
    ld a, h
    and $0F
    or $40
    ld h, a
    ld a, $1F
    rst $18
Hook_get_text_address_str_not_in_newbank:
    add hl, bc
    jp $1C80

    db $77,$77,$77,$77

Hook_deferred_restore_newbank:
    ld ($C2CD), a
    ld e, a
    ld a, ($C01D)
    rst $18
    ld a, e
    jp $1C98

    db $88,$88,$88,$88

    org $7F50
Hook_new_menu_select:
    ld a, (CURRENT_PAGE_NUM)
    cp $77
    ld a, (hl)
    jr c, Hook_new_menu_select_fallback
    inc a
    cp $02
    jp $663F
Hook_new_menu_select_fallback:
    inc a
    cp $03
    jp $663F

    db $77,$77,$77,$77

Hook_new_menu_select2:
    push af
    ld a, (CURRENT_PAGE_NUM)
    cp $77
    jr c, Hook_new_menu_select2_fallback
    pop af
    bit 7, a
    jp z, $664C
    ld a, $01
    jp $664C
Hook_new_menu_select2_fallback:
    pop af
    bit 7, a
    jp z, $664C
    ld a, $02
    jp $664C

    db $77,$77,$77,$77

Hook_new_menu_select3:
    push af
    ld a, (CURRENT_PAGE_NUM)
    cp $77
    jr c, Hook_new_menu_select3_fallback
    ld a, c
    ld (VAR_TEXT_TYPE), a
    ld h, $FF
    call Hook_readcode
    pop af
    jp $661F
Hook_new_menu_select3_fallback:
    pop af
    ld ($C2BB), a
    jp $661F

    db $77,$77,$77,$77

Hook_new_menu_select4:
    push af
    ld a, (CURRENT_PAGE_NUM)
    cp $77
    jr c, Hook_new_menu_select4_fallback
    pop af
    add a, $8
    ld de, $D42A
    jp $6655
Hook_new_menu_select4_fallback:
    pop af
    ld de, $D42A
    jp $6655

    db $77,$77,$77,$77

Hook_quiz_print_numbers1:
    ld hl, $5275
    ld a, (VAR_TEXT_TYPE)
    or a
    jr z, Hook_quiz_print_numbers1_type0
    ld hl, $548E
Hook_quiz_print_numbers1_type0:
    jp $523E

    db $77,$77,$77,$77

Hook_quiz_print_numbers2:
    ld hl, $5286
    ld a, (VAR_TEXT_TYPE)
    or a
    jr z, Hook_quiz_print_numbers2_type0
    ld hl, $549F
Hook_quiz_print_numbers2_type0:
    jp $5247

    db $77,$77,$77,$77

Hook_quiz_answer_check1:
    ld de, $C475
    ld a, (VAR_TEXT_TYPE)
    or a
    jr z, Hook_quiz_answer_check1_type0
    ld a, ($7FFC)
    ld c, a
    ret
Hook_quiz_answer_check1_type0:
    ld a, ($7FFB)
    ld c, a
    ret

    db $77,$77,$77,$77

Hook_quiz_answer_check2:
    ld de, $C48C
    ld a, (VAR_TEXT_TYPE)
    or a
    jr z, Hook_quiz_answer_check2_type0
    ld a, ($7FFE)
    ld c, a
    ret
Hook_quiz_answer_check2_type0:
    ld a, ($7FFD)
    ld c, a
    ret

    db $88,$88,$88,$88

Hook_print_from_string_table1:
    ld hl, $5252
    ld a, (VAR_TEXT_TYPE)
    or a
    jr z, Hook_print_from_string_table1_type0
    ld hl, $5262
Hook_print_from_string_table1_type0:
    jp $4EE4

    db $77,$77,$77,$77

Hook_print_from_string_table2:
    ld hl, $770F
    ld a, (VAR_TEXT_TYPE)
    or a
    jr z, Hook_print_from_string_table2_type0
    ld hl, $7729
Hook_print_from_string_table2_type0:
    jp $7478

    db $88,$88,$88,$88

Hook_ending_print_text1:
    ld hl, $43DA
    ld a, (VAR_TEXT_TYPE)
    or a
    jr z, Hook_ending_print_text1_type0
    ld hl, $43E4
Hook_ending_print_text1_type0:
    jp $431D

    db $77,$77,$77,$77

Hook_ending_print_text2:
    ld a, ($C0CF)
    ldh ($FB), a
    ld a, ($C2D3)
    sla c
    jp $432F

    db $88,$88,$88,$88

Hook_print_from_string_table3:
    ld hl, $468B
    ld a, (VAR_TEXT_TYPE)
    or a
    jr z, Hook_print_from_string_table3_type0
    ld hl, $46A3
Hook_print_from_string_table3_type0:
    jp $1EB4

    db $88,$88,$88,$88

    org $7000
NEWBANK_Hook_readcode:
    ld a, h
    cp $FF
    jr nz, NEWBANK_Hook
NEWBANK_Init:
    push bc
    push de
    push hl
    ld hl, $C500
    ld de, $4E00
    ld c, $40
    ld a, (VAR_TEXT_TYPE)
    rrca
    rrca
    ld e, a
NEWBANK_Init_loop:
    ld a, (de)
    ldi (hl), a
    inc de
    dec c
    jr nz, NEWBANK_Init_loop

    pop hl
    pop de
    pop bc
    ld a, ($C01D)
    jp $0018
    ret
NEWBANK_Hook:
    and $F0
    cp $F0
    jr nz, NEWBANK_Hook_readcode_str_not_in_newbank
    ld a, h
    and $0F
    or $40
    ld h, a
    ldi a, (hl)
    ld d, a
    ld a, (hl)
    ld e, a
NEWBANK_Hook_readcode_str_not_in_newbank:
    push hl
    ld hl, $0000
    add hl, sp
    inc hl
    inc hl
    inc hl
    inc hl
    ld a, (hl)
    cp $2C
    pop hl
    jr z, NEWBANK_Hook_readcode_call_from_2129_and_ROM02_541E
    cp $21
    jr z, NEWBANK_Hook_readcode_call_from_2129_and_ROM02_541E
    pop af
    ld d, a
    push af
NEWBANK_Hook_readcode_call_from_2129_and_ROM02_541E:
    ld a, d
    cp $E0
    jr c, NEWBANK_Hook_readcode_fallback
    cp $EA
    jr nc, NEWBANK_Hook_readcode_fallback
    ld hl, $C2D3
    ld c, (hl)
    ld b, 0
    inc (hl)
    inc (hl)
    ld hl, $C0CF
    inc (hl)
    ld hl, $C0D4
    add hl, bc
    inc hl
    ld a, e
    ldd (hl), a
    ld a, d
    ld (hl), a

    ld hl, $C2CA
    inc (hl)

    pop af
    ld a, d
    push af

    ld hl, $2153
    push hl
    ld a, ($C01D)
    jp $0018
NEWBANK_Hook_readcode_fallback:
    ld hl, $C2D3
    ld c, (hl)
    ld b, $00
    inc (hl)
    ld hl, $C0CF
    inc (hl)
    ld hl, $C0D4
    add hl, bc
    ld (hl), a

    pop af
    ld a, d
    push af

    ld hl, $2153
    push hl
    ld a, ($C01D)
    jp $0018