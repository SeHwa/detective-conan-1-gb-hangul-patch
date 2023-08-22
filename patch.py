import sys
import struct
import codecs
from functools import reduce
from PIL import Image

p8 = lambda x: struct.pack("<B", x)
p16 = lambda x: struct.pack("<H", x)
u16 = lambda x: struct.unpack("<H", x)[0]
ub16 = lambda x: struct.unpack(">H", x)[0]
pb16 = lambda x: struct.pack(">H", x)

def patch(data, offset, patch_data):
    return data[:offset] + patch_data + data[offset + len(patch_data):]

def gb_checksum1(data):
    checksum = 0
    for i in range(0x134, 0x14D):
        checksum += (data[i] + 1)
    checksum = 0x100 - (checksum % 0x100)
    return checksum

def gb_checksum2(data):
    checksum = 0
    for i in range(len(data)):
        if i == 0x14E or i == 0x14F: continue
        checksum += data[i]
    checksum %= 0x10000
    return checksum

def get_title(img):
    X = 160
    Y = 144
    img = img.crop( (48, 40, 48+X, 40+Y) )

    pal = {(248, 232, 216): 0,
           (176, 160, 144): 1,
           (104, 88, 72): 2,
           (40, 24, 8): 3}

    img_2bpp = [ [0]*X for _ in range(Y) ]
    for i in range(Y):
        for j in range(X):
            p = img.getpixel((j, i))
            t = list(map(lambda x: abs(x[0]-p[0]), pal))
            img_2bpp[i][j] = t.index(min(t))

    tile_idx = 1
    tiles_k = {"0"*64: 0}
    tiles = b"\x00"*16
    tilemap = []
    for i in range(Y // 8):
        for j in range(X // 8):
            a = ""
            for k in range(8):
                for l in range(8):
                    a += str(img_2bpp[i*8+k][j*8+l])
            
            if (a in tiles_k) == False:
                tiles_k[a] = tile_idx
                tilemap.append(tile_idx)
                tile_idx += 1

                lb = 0
                hb = 0
                for m in range(len(a)):
                    color = int(a[m])
                    lb |= ((color & 0b10) >> 1) << (7 - (m % 8))
                    hb |= (color & 0b01) << (7 - (m % 8))
                    if m % 8 == 7:
                        tiles += p8(hb) + p8(lb)
                        lb = 0
                        hb = 0
            else:
                tilemap.append(tiles_k[a])

    tilemap_shuffle = []
    for i in range(len(tilemap) // ((X // 8) * 2)):
        skip = [0, 0, 4, 0, 0, 4, 22, 0, 2]
        for j in range(X // 8):
            if skip[i] != 0:
                if j < skip[i]: continue
            for k in range(2):
                idx = i * (X // 8) * 2 + j + k + ((j % 2) * (X // 8)) - (j % 2)
                tilemap_shuffle.append(tilemap[idx])

    return tiles, b"".join(list(map(lambda x: p8(x), tilemap_shuffle)))

def get_sgb_border(img):
    W = 256
    H = 224
    GB_X = 48
    GB_Y = 40
    GB_W = 160
    GB_H = 144
    SPLIT = 40

    const_palette = [11, 12, 14, 13, 9, 6, 3, 2, 1, 5, 4, 7, 9, 8, 10]
    pal1 = {}
    pal_cnt = 0
    img_4bpp = [ [0]*W for _ in range(H) ]
    for i in range(H - SPLIT):
        for j in range(W):
            p = img.getpixel((j, i))
            if i >= GB_Y and i < GB_Y + GB_H and j >= GB_X and j < GB_X + GB_W:
                img_4bpp[i][j] = 0
            else:
                if (p in pal1) == False:
                    pal1[p] = const_palette[pal_cnt]
                    pal_cnt += 1
                img_4bpp[i][j] = pal1[p]

    const_palette = [5, 6, 8, 4, 7, 1, 6, 3, 2]
    pal2 = {}
    pal_cnt = 0
    for i in range(H - SPLIT, H):
        for j in range(W):
            p = img.getpixel((j, i))
            if i >= GB_Y and i < GB_Y + GB_H and j >= GB_X and j < GB_X + GB_W:
                img_4bpp[i][j] = 0
            else:
                if (p in pal2) == False:
                    pal2[p] = const_palette[pal_cnt]
                    pal_cnt += 1
                img_4bpp[i][j] = pal2[p]

    tile2_offset = 0
    tile_idx = 1
    tiles_k = {"0"*64: 0}
    tiles = b"\x00"*32
    tilemap = []
    for i in range(H // 8):
        if i == (H - SPLIT) // 8:
            tiles_k = {}
        for j in range(W // 8):
            a = ""
            for k in range(8):
                for l in range(8):
                    a += hex(img_4bpp[i*8+k][j*8+l])[2:].rjust(1, "0")

            if (a in tiles_k) == False:
                tiles_k[a] = tile_idx
                tilemap.append(tile_idx)
                tile_idx += 1

                b1 = 0
                b2 = 0
                b3 = 0
                b4 = 0
                tiles1 = b""
                tiles2 = b""
                for m in range(len(a)):
                    color = int(a[m], 16)
                    b1 |= (color & 0b0001) << (7 - (m % 8))
                    b2 |= ((color & 0b0010) >> 1) << (7 - (m % 8))
                    b3 |= ((color & 0b0100) >> 2) << (7 - (m % 8))
                    b4 |= ((color & 0b1000) >> 3) << (7 - (m % 8))
                    if m % 8 == 7:
                        tiles1 += p8(b1) + p8(b2)
                        tiles2 += p8(b3) + p8(b4)
                        b1 = 0
                        b2 = 0
                        b3 = 0
                        b4 = 0
                tiles += tiles1 + tiles2
                if tile_idx == 0x80:
                    tile2_offset = len(tiles)
            else:
                tilemap.append(tiles_k[a])

    tile2_start = (W // 8) * ((H - SPLIT) // 8)
    tilemap_snes = b""
    tidx = 0
    while True:
        if tidx != 0 and tidx % 0x20 == 0: tidx += 0x20
        if tidx >= len(tilemap): break

        indexes = [0, 1, 0x20, 0x21]
        for i in range(len(indexes)):
            tilemap_snes += p8(tilemap[tidx+indexes[i]])
            if tidx+indexes[i] < tile2_start:
                tilemap_snes += p8(0x04)
            else:
                tilemap_snes += p8(0x08)
        tidx += 2

    return tiles, tilemap_snes, tile2_offset

def compress_sgb_border(data, offset):
    result = b""
    result_offset = 0
    temp1 = b""
    temp2 = b""
    prev1 = 0
    prev2 = 0
    for i in range(len(data)):
        if i == offset:
            result_offset = len(result)

        if i % 2 == 0:
            if i % 0x10 == 0: prev1 = 0
            else: prev1 = data[i - 2]
            temp1 += p8(data[i] ^ prev1)
        else:
            if i % 0x10 == 1: prev2 = 0
            else: prev2 = data[i - 2]
            temp2 += p8(data[i] ^ prev2)

        if i % 0x10 == 0x0F:
            result += b"\x00\xFF" + temp1 + b"\xFF" + temp2
            temp1 = b""
            temp2 = b""
    return result, result_offset


JUMP_OP = p8(0xC3)
CALL_OP = p8(0xCD)

TITLE_TILEDATA = 0x3E839
TITLE_TILEMAP = 0x2003C

NEW_FONT_OFFSET = 0x40000
NEW_SGB_BORDER_BANK = 0x12
NEW_SGB_BORDER_ADDR = 0x4000 + 0x1300
NEW_SGB_BORDER_OFFSET = NEW_SGB_BORDER_BANK * 0x4000 + (NEW_SGB_BORDER_ADDR - 0x4000)
NEW_SGB_BORDER_TILEMAP_BANK = 0x12
NEW_SGB_BORDER_TILEMAP_ADDR = 0x4000 + 0x3000
NEW_SGB_BORDER_TILEMAP_OFFSET = NEW_SGB_BORDER_TILEMAP_BANK * 0x4000 + (NEW_SGB_BORDER_TILEMAP_ADDR - 0x4000)

data = open(sys.argv[1], "rb").read()
data = data + b"\x00"*(0x80000-len(data))

title_tiledata, title_tilemap = get_title(Image.open("title_translated.png"))
sgb_tiledata, sgb_tilemap, sgb_tileoffset = get_sgb_border(Image.open("title_translated.png"))

data = patch(data, 0x3CFF, p8(NEW_SGB_BORDER_BANK))
data = patch(data, 0x3D0F, p8(NEW_SGB_BORDER_BANK))
sgb_compressedtile, sgb_compressedtileoffset = compress_sgb_border(sgb_tiledata, sgb_tileoffset)
data = patch(data, NEW_SGB_BORDER_OFFSET, sgb_compressedtile)
data = patch(data, 0x3D02, p16(NEW_SGB_BORDER_ADDR))
data = patch(data, 0x3D12, p16(NEW_SGB_BORDER_ADDR + sgb_compressedtileoffset))

data = patch(data, 0x3D1F, p8(NEW_SGB_BORDER_TILEMAP_BANK))
data = patch(data, 0x3D25, p16(NEW_SGB_BORDER_TILEMAP_ADDR))
data = patch(data, 0x3D3F, p16(NEW_SGB_BORDER_TILEMAP_ADDR + 0xF0))
data = patch(data, NEW_SGB_BORDER_TILEMAP_OFFSET, b"".join([p8(i) for i in range(0xF0)]) + sgb_tilemap)

data = patch(data, TITLE_TILEMAP, title_tilemap)
data = patch(data, TITLE_TILEDATA, title_tiledata)

font = open("galmuri.fnt", "rb").read()
data = patch(data, NEW_FONT_OFFSET, font)

def get_font(char):
    hangul = codecs.open(u"완성형.txt", "r", "UTF-16").read()
    idx = hangul.find(char)
    return font[idx*0x10:idx*0x10+0x10]


PATCH_CODE0 = 0x62
PATCH_CODE1 = 0x3EF0
PATCH_CODE2 = 0x7F50
PATCH_CODE2_OFFSET = 0xBF50
PATCH_CODE3 = 0x7F88
PATCH_CODE3_OFFSET = 0xFF88
PATCH_CODE4 = 0x7EB0
PATCH_CODE4_OFFSET = 0x1BEB0
PATCH_CODE5 = 0x7F50
PATCH_CODE5_OFFSET = 0x1FF50
PATCH_CODE6 = 0x7000
PATCH_CODE6_OFFSET = 0x7F000

patch_code = open("output.obj", "rb").read().split(b"\x88\x88\x88\x88")
patch_code0 = patch_code[0].split(b"\x77\x77\x77\x77")
patch_code1 = patch_code[1].split(b"\x77\x77\x77\x77")
patch_code2 = patch_code[2].split(b"\x77\x77\x77\x77")
patch_code3 = patch_code[3].split(b"\x77\x77\x77\x77")
patch_code4 = patch_code[4].split(b"\x77\x77\x77\x77")
patch_code5 = patch_code[5].split(b"\x77\x77\x77\x77")
patch_code6 = patch_code[6].split(b"\x77\x77\x77\x77")

patch_offsets0 = [0xA55, 0xBB0, 0x72D, 0x941E]
patch_offsets1 = [0x2150, 0x63F, 0x34F, 0x996, 0x2B1C, 0x2B87, 0x19F1, 0x3036, 0xF151, 0x1C79, 0x1C95]
patch_offsets2 = [0xA63C, 0xA648, 0xA61C, 0xA652, 0x923B, 0x9244, 0x92E9, 0x92FD]
patch_offsets3 = [0xCEE1, 0xF475]
patch_offsets4 = [0x1831A, 0x1832A]
patch_offsets5 = [0x1EB1]

print("Code0 end address : " + hex(PATCH_CODE0 + len(b"".join(patch_code0))))
print("Code1 end address : " + hex(PATCH_CODE1 + len(b"".join(patch_code1))))
print("Code2 end address : " + hex(PATCH_CODE2 + len(b"".join(patch_code2))))
print("Code3 end address : " + hex(PATCH_CODE3 + len(b"".join(patch_code3))))
print("Code4 end address : " + hex(PATCH_CODE4 + len(b"".join(patch_code4))))
print("Code5 end address : " + hex(PATCH_CODE5 + len(b"".join(patch_code5))))
print("Code6 end address : " + hex(PATCH_CODE6 + len(b"".join(patch_code6))))
data = patch(data, PATCH_CODE0, b"".join(patch_code0))
data = patch(data, PATCH_CODE1, b"".join(patch_code1))
data = patch(data, PATCH_CODE2_OFFSET, b"".join(patch_code2))
data = patch(data, PATCH_CODE3_OFFSET, b"".join(patch_code3))
data = patch(data, PATCH_CODE4_OFFSET, b"".join(patch_code4))
data = patch(data, PATCH_CODE5_OFFSET, b"".join(patch_code5))
data = patch(data, PATCH_CODE6_OFFSET, b"".join(patch_code6))
patch_code_addr = PATCH_CODE0
for i in range(len(patch_offsets0)):
    op = JUMP_OP
    if patch_offsets0[i] == 0xBB0:  # hack
        op = CALL_OP
        data = patch(data, 0xEE3, op + p16(patch_code_addr))
    data = patch(data, patch_offsets0[i], op + p16(patch_code_addr))
    patch_code_addr += len(patch_code0[i])
patch_code_addr = PATCH_CODE1
data = patch(data, 0x230B, JUMP_OP + p16(patch_code_addr))  # hack
for i in range(len(patch_offsets1)):
    data = patch(data, patch_offsets1[i], JUMP_OP + p16(patch_code_addr))
    patch_code_addr += len(patch_code1[i])
patch_code_addr = PATCH_CODE2
for i in range(len(patch_offsets2)):
    op = JUMP_OP
    if i > 5: op = CALL_OP  # hack
    data = patch(data, patch_offsets2[i], op + p16(patch_code_addr))
    patch_code_addr += len(patch_code2[i])
patch_code_addr = PATCH_CODE3
for i in range(len(patch_offsets3)):
    data = patch(data, patch_offsets3[i], JUMP_OP + p16(patch_code_addr))
    patch_code_addr += len(patch_code3[i])
patch_code_addr = PATCH_CODE4
for i in range(len(patch_offsets4)):
    data = patch(data, patch_offsets4[i], JUMP_OP + p16(patch_code_addr))
    patch_code_addr += len(patch_code4[i])
patch_code_addr = PATCH_CODE5
for i in range(len(patch_offsets5)):
    data = patch(data, patch_offsets5[i], JUMP_OP + p16(patch_code_addr))
    patch_code_addr += len(patch_code5[i])


arr = codecs.open(u"korean.tbl", "rb", "utf8").read().split("\n")
kor_tables = {}
for i in range(len(arr)):
    t = arr[i].split("=")
    kor_tables[t[1]] = t[0]
code_tables = {}
for i in range(len(arr)):
    a = arr[i].split("=")
    code_tables[int(a[0], 16)] = a[1]

def str2code(str):
    global kor_tables

    code = b""
    for i in range(len(str)):
        code += bytes.fromhex(kor_tables[str[i]])
    return code
def code2str(code, length):
    global code_tables

    i = 0
    string = ""
    while True:
        if code[i] >= 0xE0 and code[i] < 0xF0:
            c = code[i] * 0x100 + code[i+1]
            i += 2
        else:
            c = code[i]
            i += 1
        string += code_tables[c]
        if len(string) >= length: break
    return string

data = patch(data, 0x3F869, b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x30\x30\x10\x10\x20\x20")
kor_tables[","] = "34"

EMPTY = b"\x77\x77\x77\x77\x77\x77\x77\x77"

def decompress_text(data, offsets, start):
    window = [0]*0x800
    ptr = 0xCFEE - 0xC800
    idx = 0
    
    text = b""
    fcnt = 0
    flag = 0
    remain = 0
    result = []
    for i in range(len(offsets)-1):
        count = offsets[i+1] - offsets[i]
        if count == 0:
            result.append(EMPTY)
            continue
        remain_count = count

        if remain == 1:
            if len(text) >= count:
                result.append(text[:count])
                if len(text) == count:
                    remain = 0
                text = text[count:]
                continue
            else:
                remain_count -= len(text)
        remain = 0
        while True:
            if fcnt % 8 == 0:
                flag = data[start+idx]
                idx += 1

            if flag & 1 == 1:
                window[ptr % len(window)] = data[start+idx]
                text += data[start+idx].to_bytes(1, byteorder="little")
                idx += 1
                ptr += 1

                remain_count -= 1
            else:
                b = data[start+idx]
                c = data[start+idx+1]
                idx += 2

                length = (c & 0xF) + 3
                off = b + ((c & 0xF0) >> 4) * 0x100
                for j in range(length):
                    if remain == 0 and len(text) >= count:
                        remain = 1
                        result.append(text)
                        text = b""
                    window[ptr % len(window)] = window[off % len(window)]
                    text += window[off % len(window)].to_bytes(1, byteorder="little")
                    remain_count -= 1
                    ptr += 1
                    off += 1

            flag >>= 1
            fcnt += 1
            if remain_count <= 0: break
        if remain == 0:
            result.append(text)
            text = b""
    return result


def create_text_data(translated_text_data):
    TEXT_LOC_TABLE = 0x1C613

    translated_text_data_idx = 0
    translated_text_result_new_banks = []
    translated_text_results = []
    for i in range(0x25):
        temp_result2 = b""
        len_arr = []
        bank = data[TEXT_LOC_TABLE+(i*3)]
        addr = u16(data[TEXT_LOC_TABLE+(i*3)+1:TEXT_LOC_TABLE+(i*3)+3])
        offset = bank * 0x4000 + (addr - 0x4000)

        text_offsets = []
        text_cnt = data[offset] // 2
        for j in range(text_cnt):
            text_offsets.append( u16(data[offset+1+(j*2):offset+1+(j*2)+2]) )

        text_start = offset+1+(text_cnt*2)
        decompressed_text = decompress_text(data, text_offsets, text_start)
        for j in range(len(decompressed_text)):
            temp_result = b""
            if decompressed_text[j] == EMPTY:
                len_arr.append(0)
                continue
            idx = 0
            flag = 0
            is_translated = 0
            is_prev_str_in_line = 0
            while True:
                if idx >= len(decompressed_text[j]): break
                c = decompressed_text[j][idx]
                if c & 0x80 != 0:
                    is_prev_str_in_line = 1
                    length = c & 0xF
                    idx += 1

                    line = translated_text_data[translated_text_data_idx]
                    if code_tables[decompressed_text[j][idx]] == " ":
                        if line != "입니다!": # hack
                            line = " " + line
                    if len(line) == 0: # temporary
                        if is_translated == 1:
                            temp_result = temp_result
                        else:
                            print(i, j, "번역 안됨")
                            temp_result += p8(0x85)
                            temp_result += str2code("번역 안됨")
                    else:
                        is_translated = 1
                        temp_result += p8(len(line) | 0x80)
                        temp_result += str2code(line)
                    idx += length
                elif c == 2 or c == 3 or c == 6 or c == 10 or c == 11 or c == 14 or c == 17 or c == 19 or c == 20 or c == 21:
                    temp_result += p8(c)
                    idx += 1
                elif c == 4 or c == 5 or c == 18 or c == 22:
                    temp_result += p8(c) + p8(decompressed_text[j][idx+1])
                    idx += 2
                elif c == 7 or c == 9 or c == 15:
                    temp_result += p8(c)
                    idx += 1
                    if c == 9 or c == 15:
                        temp_result += p8(decompressed_text[j][idx])
                        idx += 1
                    if is_prev_str_in_line == 1:
                        translated_text_data_idx += 1
                elif c == 16:
                    temp_result += p8(c) + decompressed_text[j][idx+1:idx+3]
                    idx += 3
                elif c == 0:
                    temp_result += p8(c)
                    if flag == 0:
                        translated_text_data_idx += 1
                        is_prev_str_in_line = 0
                    idx += 1
                elif c == 1:
                    temp_result += p8(c)
                    translated_text_data_idx += 1
                    is_prev_str_in_line = 0
                    idx += 1
                elif c == 8:
                    temp_result += p8(c)
                    translated_text_data_idx += 1
                    is_prev_str_in_line = 0
                    idx += 1
                elif c == 12:
                    temp_result += p8(c)
                    translated_text_data_idx += 2
                    is_prev_str_in_line = 0
                    idx += 1
                    flag = 1
                    continue
                elif c == 13:
                    temp_result += p8(c)
                    if len(temp_result) > 0x80:
                        print("ERROR: 대사 size 초과")
                        print(translated_text_data[translated_text_data_idx:translated_text_data_idx+10])
                        sys.exit(0)
                    translated_text_data_idx += 3
                    is_prev_str_in_line = 0
                    idx += 1
                    flag = 1
                    continue
                else:
                    print("ERROR: 알 수 없는 제어코드 " + hex(c))
                    sys.exit(0)
                flag = 0
            len_arr.append(len(temp_result))
            temp_result2 += temp_result
        translated_text_data_idx += 5

        t = 0
        len_table = p8((len(len_arr)+1)*2)
        for j in range(len(len_arr)):
            len_table += p16(t)
            t += len_arr[j]
        len_table += p16(t)

        separator_final = b""
        for j in range(len(temp_result2)):
            if j % 8 == 0:
                separator_final += b"\xFF"
            separator_final += p8(temp_result2[j])

        if (len(b"".join(translated_text_results)) % 0x4000) + len(len_table + separator_final) >= 0x4000:
            translated_text_result_new_banks.append(i)
        translated_text_results.append(len_table + separator_final)

    return translated_text_results, translated_text_result_new_banks


result_text, result_banks = create_text_data(codecs.open(U"translated_text.txt", "rb", "utf8").read().split("\r\n"))

new_text_loc_table1_bank = 0x12
new_text_loc_table1_addr = 0x4000 + 0x3B00
new_text_loc_table1_offset = new_text_loc_table1_bank * 0x4000 + (new_text_loc_table1_addr - 0x4000)
data = patch(data, 0x19EF, p16(new_text_loc_table1_addr))

translated_text_bank = 0x13
translated_text_offset = 0
for i in range(len(result_text)):
    if translated_text_offset + len(result_text[i]) > 0x4000:
        translated_text_bank += 1
        translated_text_offset = 0
    data = patch(data, new_text_loc_table1_offset + (i * 3), p8(translated_text_bank) + p16(0x4000 + translated_text_offset))
    data = patch(data, translated_text_bank * 0x4000 + translated_text_offset, result_text[i])
    translated_text_offset += len(result_text[i])


result_text, result_banks = create_text_data(codecs.open(U"translated_text2.txt", "rb", "utf8").read().split("\r\n"))

new_text_loc_table2_bank = 0x12
new_text_loc_table2_addr = 0x4000 + 0x3B00 + 0x80
new_text_loc_table2_offset = new_text_loc_table2_bank * 0x4000 + (new_text_loc_table2_addr - 0x4000)

translated_text_bank = 0x19
translated_text_offset = 0
for i in range(len(result_text)):
    if translated_text_offset + len(result_text[i]) > 0x4000:
        translated_text_bank += 1
        translated_text_offset = 0
    data = patch(data, new_text_loc_table2_offset + (i * 3), p8(translated_text_bank) + p16(0x4000 + translated_text_offset))
    data = patch(data, translated_text_bank * 0x4000 + translated_text_offset, result_text[i])
    translated_text_offset += len(result_text[i])


newbank_text_start_addr = 0xF000
newbank_text_start_offset = 0x7C000


ending_text = ["CONGRATULATIONS!", "클리어 타임", " 패스워드", " 탐정랭크 "]
ending_text_code = b""
ending_text_table_offset = 0x1839C
for i in range(4):
    data = patch(data, ending_text_table_offset + (i * 5), p16(newbank_text_start_addr + len(ending_text_code)) + p8(len(ending_text[i])))
    ending_text_code += p8(len(ending_text[i]) | 0x80)
    ending_text_code += str2code(ending_text[i])
    ending_text_code += b"\x00"
data = patch(data, newbank_text_start_offset, ending_text_code)
newbank_text_start_addr += len(ending_text_code)
newbank_text_start_offset += len(ending_text_code)

ending_text = [
["랭크 D 어린이   탐정단", "랭크 C 유명한", "랭크 B골롬보반장", "랭크 A  명탐정 코난", "랭크 S 셜록 홈즈   "],
["랭크 D 소년   탐정단 ", "랭크 C 코고로", "랭크 B메구레경부 ", "랭크 A  명탐정 코난", "랭크 S 셜록 홈즈   "]
]
ending_text_code = b""
ending_text_table_offset = 0x183DA
ending_text_start_addr = 0x7ED0
ending_text_start_offset = 0x1BED0
for i in range(5*2):
    if i < 5: text = ending_text[0][i]
    else: text = ending_text[1][i-5]
    data = patch(data, ending_text_table_offset + (i * 2), p16(ending_text_start_addr + len(ending_text_code)) + p8(len(text)))
    ending_text_code += p8(len(text) | 0x80)
    ending_text_code += str2code(text)
    ending_text_code += b"\x00"
data = patch(data, ending_text_start_offset, ending_text_code)


ending_tilemap_addrs = 0x1C251
ending_tilemap_index_table = u16(data[ending_tilemap_addrs:ending_tilemap_addrs+2])
ending_tilemap_index_table_bank = data[ending_tilemap_addrs+2]
ending_tilemap_data_table = u16(data[ending_tilemap_addrs+3:ending_tilemap_addrs+5])
ending_tilemap_data_table_bank = data[ending_tilemap_addrs+5]

ending_tilemap_index_offset = ending_tilemap_index_table_bank * 0x4000 + (ending_tilemap_index_table - 0x4000)
ending_tilemap_data_offset = ending_tilemap_data_table_bank * 0x4000 + (ending_tilemap_data_table - 0x4000)

ending_tilemap_index = data[ending_tilemap_index_offset:ending_tilemap_index_offset+0x5A]
ending_tilemap_data = data[ending_tilemap_data_offset:ending_tilemap_data_offset+0xC0]

ending_tile = [ [0]*20 for _ in range(18) ]
outidx = 0
for i in range(len(ending_tilemap_index)):
    idx = (ending_tilemap_index[i] * 4)
    tile = ending_tilemap_data[idx:idx+4]
    ending_tile[outidx//20][outidx%20] = tile[0]
    ending_tile[outidx//20][outidx%20+1] = tile[1]
    ending_tile[outidx//20+1][outidx%20] = tile[2]
    ending_tile[outidx//20+1][outidx%20+1] = tile[3]
    outidx += 2
    if outidx % 20 == 0: outidx += 20

for i in range(3):
    ending_tile[9+i][7] = ending_tile[9+i][6]
    ending_tile[9+i][8] = ending_tile[5+i][8]
    ending_tile[9+i][8] = ending_tile[5+i][8]
    ending_tile[13+i][8] = ending_tile[5+i][8]
    ending_tile[13+i][9] = ending_tile[5+i][9]

new_ending_tilemap = {}
new_ending_tilemap_data = b""
new_ending_tilemap_index = b""
cnt = 0
for i in range(0, 18, 2):
    for j in range(0, 20, 2):
        tm = p8(ending_tile[i][j]) + p8(ending_tile[i][j+1]) + p8(ending_tile[i+1][j]) + p8(ending_tile[i+1][j+1])
        if (tm in new_ending_tilemap) == False:
            new_ending_tilemap_data += tm
            new_ending_tilemap[tm] = cnt
            cnt += 1
        new_ending_tilemap_index += p8(new_ending_tilemap[tm])
data = patch(data, ending_tilemap_index_offset, new_ending_tilemap_index)
data = patch(data, ending_tilemap_data_offset, new_ending_tilemap_data)


menu_text = [" 게임시작", " 패스워드", "  설정 ", " 메시지 표시속도", "빠르게", "보통", "느리게", "패스워드를 입력해주세요", "OK", "나가기"]
menu_text_data = b""
for i in range(len(menu_text)):
    data = patch(data, 0xF694 + (i * 5), p16(newbank_text_start_addr + len(menu_text_data)) + p8(len(menu_text[i])))
    menu_text_data += p8(len(menu_text[i]) | 0x80)
    menu_text_data += str2code(menu_text[i])
    menu_text_data += b"\x00"
data = patch(data, newbank_text_start_offset, menu_text_data)
newbank_text_start_addr += len(menu_text_data)
newbank_text_start_offset += len(menu_text_data)


menu_tile = 0x2EC70
menu_bg_tile = data[0x2EC60:0x2EC70]
menu_new_tiles = [
b"\x1F\x1F\x76\x21\x63\x40\x43\xC0\x43\x40\xC3\x40\xC3\x40\xC3\x80",
b"\x00\x01\xFE\xE1\xDE\x39\xF7\x0F\xF9\x00\xF4\x00\xE8\x00\xD0\x00",
b"\x00\x01\x7E\x01\x7E\x01\x00\xFF\xFF\xFF\x00\x00\x00\x00\x00\x00",
b"\x00\x01\x7E\x01\x7E\x01\x00\xFF\xFF\xFF\x00\x00\x00\x00\x00\x00",
b"\x00\x01\x7E\x01\x7E\x01\x00\xFF\x81\x91\xF7\x71\x7F\x0D\x5F\x03",
b"\x3F\x3F\x63\x40\xC1\x80\x81\x80\x83\x00\x07\x00\x07\x00\x0F\x00",
b"\x00\x01\xFE\x81\xFE\x41\xA0\x7F\xE0\x30\xE7\x30\xA7\x70\xC0\x7F",
b"\x00\x01\x7E\x01\x7E\x01\x01\xFF\x01\x11\xE7\x12\xE7\x12\x04\xFF",
b"\x83\x80\x83\x80\x87\x80\x87\x00\x0F\x00\x1F\x00\xFD\x7E\x8B\xFF",
b"\xE8\x00\xD0\x00\xE4\x00\xD0\x00\xE8\x00\xF4\x00\xF0\x00\xDA\xE0",
b"\xAF\x01\x1F\x01\x2F\x01\x5F\x01\x2F\x01\x1F\x01\xAF\x01\x1F\x01",
b"\x0F\x00\x0F\x00\x0F\x00\x0E\x01\x07\x01\x07\x01\x03\x01\xFF\x7D",
b"\x40\xC1\xFE\x81\xFE\x81\x80\xFF\x00\x10\xE7\x10\xE7\x10\x00\xFF",
b"\x05\x05\x7E\x07\x7E\x07\x06\xFF\x02\x13\xE7\x11\xE7\x10\x00\xFF",
b"\x3D\xCB\x73\x91\xFB\x39\xB7\x0D\x8E\x06\x8F\x06\xFF\xFC\x00\xFF",
b"\x34\x38\x7F\x0E\x7F\x01\x00\xFF\x00\x10\xE7\x10\xE7\x10\x00\xFF",
b"\x00\x00\x00\x00\xFF\xFF\x00\xFF\x00\x10\xE7\x10\xE7\x10\x00\xFF",
b"\x2F\x01\x5F\x01\xFF\x01\xEF\xF0\x1B\x1C\xE6\x17\xE7\x11\x00\xFF",
b"\xAF\xF3\x77\xA1\x73\xA1\xF3\xA1\xF6\x62\xFF\x0C\xF7\xF0\x00\xFF",
b"\x00\x01\x7E\x01\x7E\x01\x00\xFF\xFF\xFF\x00\x00\x00\x00\x00\x00"]

for i in range(4):
    data = patch(data, menu_tile+(i*0x10), menu_bg_tile)
for i in range(len(menu_new_tiles)):
    data = patch(data, menu_tile+((i+4)*0x10), menu_new_tiles[i])


menu_tilemap_addrs = 0x1C1E1
menu_tilemap_index_table = u16(data[menu_tilemap_addrs:menu_tilemap_addrs+2])
menu_tilemap_index_table_bank = data[menu_tilemap_addrs+2]
menu_tilemap_data_table = u16(data[menu_tilemap_addrs+3:menu_tilemap_addrs+5])
menu_tilemap_data_table_bank = data[menu_tilemap_addrs+5]

menu_tilemap_index_offset = menu_tilemap_index_table_bank * 0x4000 + (menu_tilemap_index_table - 0x4000)
menu_tilemap_data_offset = menu_tilemap_data_table_bank * 0x4000 + (menu_tilemap_data_table - 0x4000)

menu_tilemap_index = data[menu_tilemap_index_offset:menu_tilemap_index_offset+0x60]
menu_tilemap_data = data[menu_tilemap_data_offset:menu_tilemap_data_offset+0x80]

index_idx = [26, 27, 28, 36, 37, 46, 47, 48, 56, 57, 66, 67, 68, 76, 77]
index_val = [0x18, 0x19, 0x01, 0x1A, 0x1B]
for i in range(len(index_idx)):
    menu_tilemap_index = patch(menu_tilemap_index, index_idx[i], p8(index_val[i % len(index_val)]))
menu_tilemap_data = patch(menu_tilemap_data, 0x18*4, b"\x18\x19\x00\x1F")
menu_tilemap_data = patch(menu_tilemap_data, 0x19*4, b"\x1A\x1B\x20\x21")
menu_tilemap_data = patch(menu_tilemap_data, 0x1A*4, b"\x25\x26\x10\x13")
menu_tilemap_data = patch(menu_tilemap_data, 0x1B*4, b"\x27\x10\x10\x10")

new_menu_tilemap_data_bank = 0x12
new_menu_tilemap_data_addr = 0x4000 + 0x3800
new_menu_tilemap_data_offset = new_menu_tilemap_data_bank * 0x4000 + (new_menu_tilemap_data_addr - 0x4000)

data = patch(data, menu_tilemap_index_offset, menu_tilemap_index)
data = patch(data, menu_tilemap_addrs+3, p16(new_menu_tilemap_data_addr) + p8(new_menu_tilemap_data_bank))
data = patch(data, new_menu_tilemap_data_offset, menu_tilemap_data)


data = patch(data, 0x2EE20, data[0x2EE20:0x2EE20+8] + b"\x00"*8)
data = patch(data, 0x2EE30, data[0x2EE30:0x2EE30+8] + b"\x00"*8)
data = patch(data, 0x3F5E9, data[0x3F5E9:0x3F5E9+8] + b"\x00"*8)
data = patch(data, 0x3F5F9, data[0x3F5F9:0x3F5F9+8] + b"\x00"*8)
data = patch(data, 0x2CF20, data[0x2CF20:0x2CF20+8] + b"\x00"*8)
data = patch(data, 0x2CF30, data[0x2CF30:0x2CF30+8] + b"\x00"*8)
data = patch(data, 0x3F5D9, b"\x00"*0x10)

image1 = [
b"\x00\x01\x7E\x01\x7E\x01\x00\xFF\xFF\x00\x80\x00\x80\x00\x80\x00",
b"\x00\x01\x7E\x01\x7E\x01\x00\xFF\xFF\x00\x00\x00\x72\x72\xFA\xFA",
b"\x00\x01\x7E\x01\x7E\x01\x00\xFF\xFF\x00\x00\x00\x08\x08\x08\x08",
b"\x00\x01\x7E\x01\x7E\x01\x00\xFF\xFF\x00\x01\x00\x01\x00\x01\x00",
b"\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\xFF\x00",
b"\x32\x32\xCA\xCA\x02\x02\xFA\xFA\x22\x22\x22\x22\x00\x00\xFF\x00",
b"\x14\x14\x22\x22\x41\x41\x08\x08\x08\x08\x7F\x7F\x00\x00\xFF\x00",
b"\x01\x00\x01\x00\x01\x00\x01\x00\x01\x00\x01\x00\x01\x00\xFF\x00"]
data = patch(data, 0x34210, b"".join(image1))

image2 = [
b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00",
b"\x38\x38\xFE\xFE\x28\x28\x10\x10\xFF\xFF\x0E\x0E\x70\x70\x7E\x7E",
b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"]
data = patch(data, 0x32F50, b"".join(image2))

image3 = [
b"\x00\x00\x00\x00\x00\x00\x00\x00\x01\x01\x00\x00\x00\x00\x00\x00",
b"\x00\x00\x00\x00\x00\x00\x64\x64\xFC\xFC\x94\x94\x94\x94\x64\x64",
b"\x00\x00\x00\x00\x00\x00\xF2\xF2\x13\x13\xF2\xF2\x82\x82\xFA\xFA",
b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00",
b"\x00\x00\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xFF\xFF",
b"\x44\x44\xFC\xFC\x04\x04\x00\x00\x00\x00\x00\x00\x00\x00\xFF\xFF",
b"\x3C\x3C\x42\x42\x3C\x3C\x00\x00\x00\x00\x00\x00\x00\x00\xFF\xFF",
b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xFF\xFF"]
data = patch(data, 0x33130, b"".join(image3))

image4 = [
b"\x89\x89\x89\x89\x8F\x8F\x89\x89\x89\x89\x8F\x8F\x80\x80\x80\x80",
b"\x21\x21\x21\x21\x21\x21\x21\x21\x21\x21\x21\x21\x21\x21\x21\x21",
b"\x8F\x8F\x89\x89\x8F\x8F\x80\x80\x87\x87\x80\x80\x87\x87\x87\x87",
b"\x21\x21\x21\x21\x21\x21\x01\x01\xE1\xE1\xE1\xE1\x01\x01\xE1\xE1",
b"\x80\x80\x87\x87\x87\x87\x87\x87\x80\x80\x8F\x8F\x83\x83\x84\x84",
b"\x01\x01\xE1\xE1\xC1\xC1\xE1\xE1\x81\x81\xF1\xF1\xC1\xC1\x21\x21",
b"\x83\x83\x87\x87\x80\x80\x87\x87\x84\x84\x87\x87\x80\x80\x8F\x8F",
b"\xC1\xC1\xE1\xE1\x21\x21\xE1\xE1\x01\x01\xE1\xE1\x81\x81\xF1\xF1"]
data = patch(data, 0x331F0, b"".join(image4))

image5 = [
b"\x06\x06\x0F\x0F\x02\x02\x05\x05\x08\x08\x03\x03\x04\x04\x03\x03",
b"\x27\x27\x20\x20\x30\x30\x21\x21\x81\x81\xC1\xC1\x2F\x2F\xC0\xC0",
b"\xE0\xE0\x20\x20\x20\x20\x20\x20\x20\x20\x00\x00\xF0\xF0\x00\x00"]
data = patch(data, 0x33270, b"".join(image5))

image6_1 = [
b"\x80\x80\x9F\xBF\xA0\xA0\x9C\xBC\x84\xBC\x88\xB8\x93\xB3\xA4\xA7",
b"\x00\x00\xEC\xFF\x12\x13\xF2\xF3\x91\xF1\x53\x73\x33\x33\x93\x93",
b"\x00\x00\x38\xFF\x5D\xC7\xFF\x93\x6F\x39\xEF\x39\xEF\x39\xEF\x39",
b"\x00\x00\xCF\xFF\x70\x30\xEF\x3F\xE1\x3F\xEF\x3F\xF0\x30\xF3\x13",
b"\x00\x00\xCC\xFF\x32\x33\x32\x33\x32\x33\x32\x33\x32\x33\xD1\xF1",
b"\x00\x00\x1F\xFF\x2F\xE0\x1F\xFF\x00\xFF\x1F\xFF\x2F\xE0\x1F\xFF",
b"\x00\x00\xF3\xFF\xFD\x0C\xFB\xCF\x78\xCF\xFB\xCF\xFD\x0C\xFF\xCC",
b"\x00\x00\xED\xFF\xF6\x12\xFF\x92\xFF\x92\xFF\x92\xFF\x12\xFF\xE2",
b"\x00\x00\x8E\xFF\xD7\x71\xFF\x64\xDB\x4E\xFB\x4E\xFF\x64\xDF\x71",
b"\x00\x00\x31\xFF\x5A\xCE\xF9\xCF\xF8\x4F\xF8\x4F\xF8\xCF\x78\xCF",
b"\x00\x00\xF6\xFF\xFB\x09\xFF\xC9\x7F\xC9\x7F\xC9\x7F\xC1\x7F\xC9",
b"\x00\x00\xC7\xFF\x6B\x38\xFF\x32\xED\x27\xFD\x27\xFF\x32\xEF\x38",
b"\x01\x01\x19\xFD\xAD\xE5\xFD\x65\xFD\x25\xFD\x25\xFD\x65\xBD\xE5"]
image6_2 = [
b"\x9C\xBF\x93\xB3\x90\xB0\x93\xB3\x90\xB0\x8F\xBF\x80\x80\x7F\x7F",
b"\x6D\xFF\xF3\xF3\x02\x03\xF2\xF3\x02\x03\xFC\xFF\x00\x00\xFF\xFF",
b"\xEF\x39\xEF\x39\xFF\x93\x7D\xC7\x39\xFF\x00\xFF\x00\x00\xFF\xFF",
b"\xF2\x33\xF2\x33\xF3\x33\xF0\x30\xEF\x3F\xC0\xFF\x00\x00\xFF\xFF",
b"\x12\xF3\x12\xF3\xF2\xF3\x12\x13\xF2\xF3\x0C\xFF\x00\x00\xFF\xFF",
b"\x00\xFF\x00\xFF\x3F\xFF\x5F\xC0\x3F\xFF\x00\xFF\x00\x00\xFF\xFF",
b"\x7F\xCC\xF7\x9C\xFF\xFC\xFF\x04\xFB\xFF\x00\xFF\x00\x00\xFF\xFF",
b"\x9F\xF2\x9F\xF2\xFF\xF2\xFF\x12\xFF\xF2\x0D\xFF\x00\x00\xFF\xFF",
b"\xDE\x7F\xEC\x67\xFC\x67\xFF\x67\xFF\x60\x9F\xFF\x00\x00\xFF\xFF",
b"\x78\xCF\x78\xCF\x31\xFF\xF3\xFE\xF9\x0F\xF0\xFF\x00\x00\xFF\xFF",
b"\xBF\x99\xFF\x99\xEF\x39\xCF\x79\x8F\xF9\x06\xFF\x00\x00\xFF\xFF",
b"\xEF\x3F\xF7\x30\xFF\x33\xFF\x33\xFF\x30\xCF\xFF\x00\x00\xFF\xFF",
b"\xF9\xFD\xFD\x05\xFD\xE5\xFD\xE5\xFD\x05\xF9\xFD\x01\x01\xFE\xFE"]
data = patch(data, 0x2D010, b"".join(image6_1))
data = patch(data, 0x2D150, b"".join(image6_2))

image7 = [
b"\x07\x07\x04\x07\x04\x06\x05\x04\x02\x03\x01\x01\x00\x00\x00\x00",
b"\xE0\xE0\x60\x20\xA0\x60\x20\xE0\x40\xC0\x80\x80\x00\x00\x00\x00",
b"\xE8\x9E\xB8\x9C\xB8\x98\xB8\x98\xB8\x98\xB8\x98\xB8\x98\xE9\x98",
b"\x03\x00\x07\x00\x0E\x01\x1C\x03\x38\x07\x71\x0E\xFF\x3F\xC0\x40",
b"\x88\x77\x10\xEF\x20\xDF\x40\xBF\x80\x7F\x00\xFF\xCF\xFF\x30\x30",
b"\x00\xFF\x00\xFF\x00\xFF\x00\xFF\x00\xFF\x00\xFF\xE0\xFF\x10\x1F",
b"\x01\xF0\x03\xE0\x06\xC1\x0C\x83\x18\x07\x30\x0F\x60\x1F\xC0\x07",
b"\x9D\x73\x17\xF3\x17\xF3\x17\xF3\x17\xF3\x17\xF3\x17\xF3\x1D\xF3",
b"\xEB\x98\xBF\x98\xBE\x99\xBC\x9B\xB8\x9F\xB9\x9E\xBA\x9D\xEC\x9B",
b"\xDF\x5F\x44\xC4\x4A\xCA\x51\xD1\xC8\x48\x28\xE8\x2F\xEF\x20\xE0",
b"\xA6\xA6\x89\x89\xC9\xC9\x89\x89\xA9\xA9\x26\x26\xB0\xB0\x2F\x3F",
b"\x50\x5F\xD0\xDF\x50\x5F\xD0\xDF\x50\x5F\x50\x5E\x50\x5C\x10\x18",
b"\x10\x10\x7D\x7D\x39\x39\x6D\x6D\x39\x39\x11\x11\x7D\x7D\x00\x00",
b"\x1D\x73\x17\x73\x17\x73\x37\x53\x77\x13\x57\x33\x17\x73\x1D\x73",
b"\xE8\x9F\xB8\x9F\xBF\x9F\xBE\x9F\xBF\x80\x9E\xBF\xFF\xFF\x00\x00",
b"\x1F\xFF\x00\xFF\xFF\xFF\x81\x00\xFF\x00\x7E\xFF\xFF\xFF\x00\x00",
b"\xC0\xFF\x00\xFF\xFF\xFF\x81\x00\xFF\x00\x7E\xFF\xFF\xFF\x00\x00",
b"\xE1\xF0\x03\xE0\xFF\xFF\x81\x00\xFF\x00\x7E\xFF\xFF\xFF\x00\x00"]
data = patch(data, 0x2D2E0, b"".join(image7))


menu_speed_tilemap_addrs = 0x1C269
menu_speed_tilemap_index_table = u16(data[menu_speed_tilemap_addrs:menu_speed_tilemap_addrs+2])
menu_speed_tilemap_index_table_bank = data[menu_speed_tilemap_addrs+2]
menu_speed_tilemap_data_table = u16(data[menu_speed_tilemap_addrs+3:menu_speed_tilemap_addrs+5])
menu_speed_tilemap_data_table_bank = data[menu_speed_tilemap_addrs+5]

menu_speed_tilemap_index_offset = menu_speed_tilemap_index_table_bank * 0x4000 + (menu_speed_tilemap_index_table - 0x4000)
menu_speed_tilemap_data_offset = menu_speed_tilemap_data_table_bank * 0x4000 + (menu_speed_tilemap_data_table - 0x4000)

menu_speed_tilemap_index = data[menu_speed_tilemap_index_offset:menu_speed_tilemap_index_offset+0x60]
menu_speed_tilemap_data = data[menu_speed_tilemap_data_offset:menu_speed_tilemap_data_offset+0x100]

new_menu_tilemap_index = patch(menu_speed_tilemap_index, 10*7, b"\x05"*(10*2))

menu_speed_tile = [ [0]*20 for _ in range(18) ]
for i in range(9):
    for j in range(10):
        idx = new_menu_tilemap_index[i*10+j]
        tmd = menu_speed_tilemap_data[idx*4:idx*4+4]
        menu_speed_tile[i*2][j*2] = tmd[0]
        menu_speed_tile[i*2][j*2+1] = tmd[1]
        menu_speed_tile[i*2+1][j*2] = tmd[2]
        menu_speed_tile[i*2+1][j*2+1] = tmd[3]
for i in range(12):
    menu_speed_tile[17-i] = menu_speed_tile[16-i]
new_menu_tilemap_data = b""
for i in range(9):
    for j in range(10):
        new_menu_tilemap_data += p8(menu_speed_tile[i*2][j*2])
        new_menu_tilemap_data += p8(menu_speed_tile[i*2][j*2+1])
        new_menu_tilemap_data += p8(menu_speed_tile[i*2+1][j*2])
        new_menu_tilemap_data += p8(menu_speed_tile[i*2+1][j*2+1])

new_menu_tilemap_index = b"".join([ p8(i) for i in range(9*10) ])

NEW_MENU_TILEMAP_INDEX_BANK = 0x12
NEW_MENU_TILEMAP_INDEX_ADDR = 0x4000 + 0x3880
NEW_MENU_TILEMAP_INDEX_OFFSET = NEW_MENU_TILEMAP_INDEX_BANK * 0x4000 + (NEW_MENU_TILEMAP_INDEX_ADDR - 0x4000)

NEW_MENU_TILEMAP_DATA_BANK = 0x12
NEW_MENU_TILEMAP_DATA_ADDR = 0x4000 + 0x3900
NEW_MENU_TILEMAP_DATA_OFFSET = NEW_MENU_TILEMAP_DATA_BANK * 0x4000 + (NEW_MENU_TILEMAP_DATA_ADDR - 0x4000)

data = patch(data, 0x1C2F0, b"\x01" + p16(NEW_MENU_TILEMAP_INDEX_ADDR) + p8(NEW_MENU_TILEMAP_INDEX_BANK) + p16(NEW_MENU_TILEMAP_DATA_ADDR) + p8(NEW_MENU_TILEMAP_DATA_BANK) + b"\x01")
data = patch(data, NEW_MENU_TILEMAP_INDEX_OFFSET, new_menu_tilemap_index)
data = patch(data, NEW_MENU_TILEMAP_DATA_OFFSET, new_menu_tilemap_data)

menu_text = [" 번역 종류 선택", "더빙판", "자막판"]
menu_text_data = b""
for i in range(len(menu_text)):
    pos = data[0xF6A3 + (i * 5) + 3:0xF6A3 + (i * 5) + 5]
    if i > 0: pos = p16(u16(pos) + 0x20)
    data = patch(data, 0xF6C6 + (i * 5), p16(newbank_text_start_addr + len(menu_text_data)) + p8(len(menu_text[i])) + pos)
    menu_text_data += p8(0x80 + len(menu_text[i]))
    menu_text_data += str2code(menu_text[i])
    menu_text_data += b"\x00"
data = patch(data, newbank_text_start_offset, menu_text_data)
newbank_text_start_addr += len(menu_text_data)
newbank_text_start_offset += len(menu_text_data)

makers_tiles = [
b"\x00"*16,
b"\x00\x01\x7E\x01\x7E\x01\x00\xFF\x00\x10\xE7\x10\xE7\x10\x00\xFF",
b"\x00\x00\x18\x18\x18\x18\x00\x00\x00\x00\x18\x18\x18\x18\x00\x00",
b"\x3C\x3C\x66\x66\x70\x70\x3C\x3C\x0E\x0E\x66\x66\x3C\x3C\x00\x00",
b"\x00\x00\x3C\x3C\x66\x66\x66\x66\x7E\x7E\x60\x60\x3E\x3E\x00\x00",
b"\x66\x66\x66\x66\x66\x66\x7E\x7E\x66\x66\x66\x66\x66\x66\x00\x00",
b"\x00\x00\x00\x00\x63\x63\x6B\x6B\x6B\x6B\x7F\x7F\x36\x36\x00\x00",
b"\x00\x00\x00\x00\x1E\x1E\x36\x36\x36\x36\x36\x36\x1F\x1F\x00\x00"]
makers_arr = ["그래픽:피씨   ", "번역 :가각   ", "패치 :SeHwa"]
makers = makers_arr[0].ljust(32, "?") + makers_arr[1].ljust(32, "?") + makers_arr[2]
makers_uniq = list(set(makers))
makers_tables = {}
for i in range(len(makers_uniq)):
    if makers_uniq[i] == " ":
        tile = makers_tiles[0]
    elif makers_uniq[i] == "?":
        tile = makers_tiles[1]
    elif makers_uniq[i] == ":":
        tile = makers_tiles[2]
    elif makers_uniq[i] == "S":
        tile = makers_tiles[3]
    elif makers_uniq[i] == "e":
        tile = makers_tiles[4]
    elif makers_uniq[i] == "H":
        tile = makers_tiles[5]
    elif makers_uniq[i] == "w":
        tile = makers_tiles[6]
    elif makers_uniq[i] == "a":
        tile = makers_tiles[7]
    else:
        idx = ub16(str2code(makers_uniq[i])) - 0xE000
        tile = font[idx*0x10:idx*0x10+0x10]
    data = patch(data, 0x3F879 + (i * 0x10), tile)
    makers_tables[makers_uniq[i]] = 0x35 + i
makers_code = b"".join(map(lambda x: p8(makers_tables[x]), makers))
makers_code = p8(0x80 + len(makers_code)) + makers_code + b"\x00"
data = patch(data, 0xF6C6 + (3 * 5), p16(newbank_text_start_addr) + p8(len(makers)) + p16(0x99E0))
data = patch(data, newbank_text_start_offset, makers_code)
newbank_text_start_addr += len(makers_code)
newbank_text_start_offset += len(makers_code)


enter_menu_text1 = "지도        범인추리"
enter_menu_text2 = "인물소개      생각하기"
enter_menu_text_code1 = p8(0x80 + len(enter_menu_text1)) + str2code(enter_menu_text1) + b"\x01" + p8(0x80 + len(enter_menu_text2[:4])) + str2code(enter_menu_text2[:4]) + b"\x00"
enter_menu_text_code2 = p8(0x80 + len(enter_menu_text1)) + str2code(enter_menu_text1) + b"\x01" + p8(0x80 + len(enter_menu_text2)) + str2code(enter_menu_text2) + b"\x00"
data = patch(data, 0xC7EF, p16(newbank_text_start_addr))
data = patch(data, newbank_text_start_offset, enter_menu_text_code1)
newbank_text_start_addr += len(enter_menu_text_code1)
newbank_text_start_offset += len(enter_menu_text_code1)

data = patch(data, 0xC7F8, p16(newbank_text_start_addr))
data = patch(data, newbank_text_start_offset, enter_menu_text_code2)
newbank_text_start_addr += len(enter_menu_text_code2)
newbank_text_start_offset += len(enter_menu_text_code2)

enter_menu2_text = "범인추리"
enter_menu2_text_code = p8(0x80 + len(enter_menu2_text)) + str2code(enter_menu2_text) + b"\x00"
data = patch(data, 0xCF34, p8(p16(newbank_text_start_addr)[0]))
data = patch(data, 0xCF37, p8(p16(newbank_text_start_addr)[1]))
data = patch(data, 0xCF57, p8(0x4))
data = patch(data, 0xCF5A, p8(0x2E))
data = patch(data, newbank_text_start_offset, enter_menu2_text_code)
newbank_text_start_addr += len(enter_menu2_text_code)
newbank_text_start_offset += len(enter_menu2_text_code)

enter_menu3_text = "인물소개"
enter_menu3_text_code = p8(0x80 + len(enter_menu3_text)) + str2code(enter_menu3_text) + b"\x00"
data = patch(data, 0xFDB1, p8(p16(newbank_text_start_addr)[0]))
data = patch(data, 0xFDB4, p8(p16(newbank_text_start_addr)[1]))
data = patch(data, 0xFDD4, p8(0x4))
data = patch(data, 0xFDD7, p8(0x2E))
data = patch(data, newbank_text_start_offset, enter_menu3_text_code)
newbank_text_start_addr += len(enter_menu3_text_code)
newbank_text_start_offset += len(enter_menu3_text_code)

enter_menu4_text = "생각하기"
enter_menu4_text_code = p8(0x80 + len(enter_menu4_text)) + str2code(enter_menu4_text) + b"\x00"
data = patch(data, 0xD512, p8(p16(newbank_text_start_addr)[0]))
data = patch(data, 0xD515, p8(p16(newbank_text_start_addr)[1]))
data = patch(data, newbank_text_start_offset, enter_menu4_text_code)
newbank_text_start_addr += len(enter_menu4_text_code)
newbank_text_start_offset += len(enter_menu4_text_code)

names1 = [
["전명호다! ", "오너다!  ", "연진우다! ", "연미리다! ", "한원기다! ", "진보희다! ", "구강재다! ", "백연수다! "], ["타무라다! ", "오너다!  ", "마코토다! ", "미도리다! ", "오오쿠보다!", "타에코다! ", "호리구치다!", "미즈호다! "]
]
name_code = b""
name_offset = 0xD252
for i in range(8*2):
    if i < 8: name = names1[0][i]
    else: name = names1[1][i-8]
    data = patch(data, name_offset + (i * 2), p16(newbank_text_start_addr + len(name_code)))
    name_code += p8(0x80 + len(name)) + str2code(name) + b"\x00"
data = patch(data, newbank_text_start_offset, name_code)
newbank_text_start_addr += len(name_code)
newbank_text_start_offset += len(name_code)

names2 = [
["전명호 씨", "오너", "연진우 씨", "연미리 씨", "한원기 씨", "진보희 씨", "구강재 씨", "백연수 씨"],
["타무라 씨", "오너", "마코토 씨", "미도리 씨", "오오쿠보 씨", "타에코 씨", "호리구치 씨", "미즈호 씨"]
]
name2_offset = 0x1C68B
for i in range(8*2):
    if i < 8: name = names2[0][i]
    else: name = names2[1][i-8]
    data = patch(data, name2_offset + (i * 3), p16(newbank_text_start_addr - 0xB000) + p8(0x1F))
    code = p8(0x80 + len(name)) + str2code(name)
    data = patch(data, newbank_text_start_offset, code)
    newbank_text_start_addr += len(code)
    newbank_text_start_offset += len(code)

strings = [
["호러 하우스", "제트 코스터", "거대 미로", "거대 미로", "      ?", "스토리       미니게임", "OK     취소", "잡아라 크레인 게임", "체감 스케이트 보드", "따라따라 귀신", "밀어라 벽퍼즐", "남도일 리프팅", "취소"],
["호러 하우스", "제트 코스터", "거대 미로", "거대 미로", "      ?", "스토리       미니게임", "OK     취소", "잡아라 크레인 게임", "체감 스케이트 보드", "따라따라 귀신", "밀어라 벽퍼즐", "신이치 리프팅", "취소"]
]
strings_offset = 0xF70F
for i in range(13*2):
    if i < 13: string = strings[0][i]
    else: string = strings[1][i-13]
    data = patch(data, strings_offset + (i * 2), p16(newbank_text_start_addr))
    code = p8(0x80 + len(string)) + str2code(string) + b"\x00"
    data = patch(data, newbank_text_start_offset, code)
    newbank_text_start_addr += len(code)
    newbank_text_start_offset += len(code)


new_passwd_tilemap = [
(0xD0C8, b"\x80\x81\x82\x83"),
(0xD126, b"\x93\x94\x94\x94\x94\x94\x94\x95"),
(0xD146, b"\x96"),
(0xD14D, b"\x97"),
(0xD166, b"\x98\x99\x99\x99\x99\x99\x99\x9a"),
(0xD1A7, b"\x84\x85\x86\x87\x88\x89"),
(0xD1C6, b"\x8A\x8B\x8C\x8D\x8E\x8F\x90\x91"),
(0xD206, b"\x92\x9B"),
(0xD20B, b"\x9C\x9D\x9E")]
passwd_tilemap_offset = 0x1819E
for i in range(len(new_passwd_tilemap)):
    pos = new_passwd_tilemap[i][0]
    tm = new_passwd_tilemap[i][1]
    data = patch(data, passwd_tilemap_offset, p16(pos) + p8(len(tm)) + tm)
    passwd_tilemap_offset += 3 + len(tm)
data = patch(data, passwd_tilemap_offset, b"\xFF")

passwd_tile_chrs = "패스워드"
passwd_tiles = b""
for i in range(len(passwd_tile_chrs)):
    c = str2code(passwd_tile_chrs[i])
    hangul_idx = c[0]*0x100 + c[1] - 0xE000
    fontdata = font[hangul_idx*0x10:hangul_idx*0x10+0x10]
    for j in range(len(fontdata)):
        passwd_tiles += p8(fontdata[j] ^ 0xFF)

passwd_tile_chrs = "미니게임을"
for i in range(len(passwd_tile_chrs)):
    c = str2code(passwd_tile_chrs[i])
    hangul_idx = c[0]*0x100 + c[1] - 0xE000
    fontdata = font[hangul_idx*0x10:hangul_idx*0x10+0x10]
    
    prev_fontdata = b"\x00"*0x10
    if i != 0:
        c = str2code(passwd_tile_chrs[i-1])
        hangul_idx = c[0]*0x100 + c[1] - 0xE000
        prev_fontdata = font[hangul_idx*0x10:hangul_idx*0x10+0x10]

    for j in range(len(fontdata)):
        new_font = (fontdata[j] ^ 0xFF) >> 4
        new_font |= ((prev_fontdata[j] ^ 0xFF) & 0xF) << 4
        passwd_tiles += p8(new_font)

c = str2code(passwd_tile_chrs[len(passwd_tile_chrs)-1])
hangul_idx = c[0]*0x100 + c[1] - 0xE000
prev_fontdata = font[hangul_idx*0x10:hangul_idx*0x10+0x10]
for i in range(len(prev_fontdata)):
    passwd_tiles += p8((((prev_fontdata[i] ^ 0xFF) & 0xF) << 4) | 0xF)


passwd_tile_chrs = "하시겠습니까?"
for i in range(len(passwd_tile_chrs)):
    if passwd_tile_chrs[i] == "?":
        tempdata = data[0x2F3C0:0x2F3C0+0x10]
        fontdata = b""
        for j in range(len(tempdata)):
            fontdata += p8(tempdata[j] ^ 0xFF)
    else:
        c = str2code(passwd_tile_chrs[i])
        hangul_idx = c[0]*0x100 + c[1] - 0xE000
        fontdata = font[hangul_idx*0x10:hangul_idx*0x10+0x10]
    
    prev_fontdata = b"\x00"*0x10
    if i != 0:
        c = str2code(passwd_tile_chrs[i-1])
        hangul_idx = c[0]*0x100 + c[1] - 0xE000
        prev_fontdata = font[hangul_idx*0x10:hangul_idx*0x10+0x10]

    for j in range(len(fontdata)):
        new_font = (fontdata[j] ^ 0xFF) >> 4
        new_font |= ((prev_fontdata[j] ^ 0xFF) & 0xF) << 4
        passwd_tiles += p8(new_font)

tempdata = data[0x2F3C0:0x2F3C0+0x10]
prev_fontdata = b""
for i in range(len(tempdata)):
    prev_fontdata += p8(tempdata[i] ^ 0xFF)
for i in range(len(prev_fontdata)):
    passwd_tiles += p8((((prev_fontdata[i] ^ 0xFF) & 0xF) << 4) | 0xF)

passwd_tiles += data[0x2F420:0x2F4B0]

passwd_tile_chrs = "예아니오"
for i in range(len(passwd_tile_chrs)):
    c = str2code(passwd_tile_chrs[i])
    hangul_idx = c[0]*0x100 + c[1] - 0xE000
    fontdata = font[hangul_idx*0x10:hangul_idx*0x10+0x10]
    for j in range(len(fontdata)):
        passwd_tiles += p8(fontdata[j] ^ 0xFF)

bank = 0x12
addr = 0x4000 + 0x3C00
data = patch(data, 0x1C0D8, p8(0x1F) + p8(bank) + p16(addr))
data = patch(data, bank * 0x4000 + (addr - 0x4000), passwd_tiles)

data = patch(data, 0xD2E7, b"\x05")

stage_chrs_img = Image.open("image6.bmp")
stage_chrs_pal = dict(zip(sorted(set(stage_chrs_img.getdata())), [0b11, 0b01, 0b00]))
stage_tiledata = b""
for i in range(18):
    pos = [(i * 16 + i, 0),
     (i * 16 + i + 8, 0),
     (i * 16 + i, 8),
     (i * 16 + i + 8, 8)]
    for j in range(len(pos)):
        sx = pos[j][0]
        sy = pos[j][1]
        tile_low = [ stage_chrs_pal[stage_chrs_img.getpixel( (sx + (n % 8), sy + (n // 8)) )] & 0b01 for n in range(64) ]
        tile_high = [ (stage_chrs_pal[stage_chrs_img.getpixel( (sx + (n % 8), sy + (n // 8)) )] & 0b10) >> 1 for n in range(64) ]
        low = [ sum([tile_low[x1*8+x2] << (7-x2) for x2 in range(8)]) for x1 in range(8) ]
        high = [ sum([tile_high[x1*8+x2] << (7-x2) for x2 in range(8)]) for x1 in range(8) ]
        stage_tiledata += b"".join(reduce(lambda a, b: a+[p8(b[0])]+[p8(b[1])], list(zip(low, high)), []))

stage_start_image_tile_offset = 0x1C097
new_stage_start_image_tile_bank = 0x1F
new_stage_start_image_tile_addr = 0x4000 + 0x3200
data = patch(data, stage_start_image_tile_offset, p8(new_stage_start_image_tile_bank))
data = patch(data, stage_start_image_tile_offset+1, p16(new_stage_start_image_tile_addr))

data = patch(data, new_stage_start_image_tile_bank * 0x4000 + (new_stage_start_image_tile_addr - 0x4000), stage_tiledata)

stage_start_image_tilemap_data_offset = 0x1D66A
data = patch(data, stage_start_image_tilemap_data_offset, b"".join([p8(0x80+i) if i < 0x48 else p8(0x01) for 
i in range(0x50)]))

stage_start_image_tilemap_info_table_offset = 0x1C53F
for i in range(4):
    start_tilemap_offset = stage_start_image_tilemap_data_offset + (i*4)
    info_offset = stage_start_image_tilemap_info_table_offset+(i*7)
    data = patch(data, info_offset+5, p16(start_tilemap_offset - 0x1C000 + 0x4000))
stage_start_image_tilemap_info_table_offset = 0x1C55B
for i in range(8):
    pos = [0x9925, 0x9927, 0x9929, 0x992b, 0x992d, 0x99a5, 0x99a5, 0x99a5]
    start_tilemap_offset = stage_start_image_tilemap_data_offset + (4*4) + (i*4)
    if pos[i] == 0x99a5: start_tilemap_offset = stage_start_image_tilemap_data_offset + (18*4)
    info_offset = stage_start_image_tilemap_info_table_offset+(i*7)
    data = patch(data, info_offset+3, p16(pos[i]))
    data = patch(data, info_offset+5, p16(start_tilemap_offset - 0x1C000 + 0x4000))
    if i == 0: data = patch(data, info_offset+2, b"\x02") # hack
stage_start_image_tilemap_info_table_offset = 0x1C4F9
for i in range(6):
    pos = [0x9925, 0x9927, 0x9929, 0x992b, 0x992d, 0x99a5]
    start_tilemap_offset = stage_start_image_tilemap_data_offset + (9*4) + (i*4)
    if pos[i] == 0x99a5: start_tilemap_offset = stage_start_image_tilemap_data_offset + (18*4)
    info_offset = stage_start_image_tilemap_info_table_offset+(i*7)
    data = patch(data, info_offset+3, p16(pos[i]))
    data = patch(data, info_offset+5, p16(start_tilemap_offset - 0x1C000 + 0x4000))
stage_start_image_tilemap_info_table_offset = 0x1C523
for i in range(4):
    start_tilemap_offset = stage_start_image_tilemap_data_offset + (14*4) + (i*4)
    info_offset = stage_start_image_tilemap_info_table_offset+(i*7)
    data = patch(data, info_offset+5, p16(start_tilemap_offset - 0x1C000 + 0x4000))


data = patch(data, 0x29C20, data[0x29C2E:0x29C30] + data[0x29C20:0x29C20+0x0E])
data = patch(data, 0x29C30, data[0x29C3E:0x29C40] + data[0x29C30:0x29C30+0x0E])
data = patch(data, 0x29C40, data[0x29C4E:0x29C50] + data[0x29C40:0x29C40+0x0E])
data = patch(data, 0x29C50, b"\x04\x0A" + data[0x29C50:0x29C50+0x0E])
data = patch(data, 0x29C60, b"\x00\x40" + data[0x29C60:0x29C60+0x0E])
data = patch(data, 0x29C70, b"\x20\x50" + data[0x29C70:0x29C70+0x0E])
data = patch(data, 0x29C90, data[0x29C9E:0x29CA0] + data[0x29C90:0x29C90+0x0E])

data = patch(data, 0x29C80, b"\x00\x00\x00\xFF\xFF\x00\x00\xFF\x00\x00\x00\x00\x00\x00\x00\x00")

orig_quiz_tilemap_data_addr_table_offset = 0x1C368
orig_quiz_tilemap_data_addr_table = data[orig_quiz_tilemap_data_addr_table_offset:orig_quiz_tilemap_data_addr_table_offset+8]
data = patch(data, 0x1FF60, orig_quiz_tilemap_data_addr_table)
data = patch(data, 0x1FF68, orig_quiz_tilemap_data_addr_table)
orig_quiz_tilemap_index_addr_table_offset = 0x1C47D
orig_quiz_tilemap_index_addr_table = data[orig_quiz_tilemap_index_addr_table_offset:orig_quiz_tilemap_index_addr_table_offset+0x10]
data = patch(data, 0x1FF70, orig_quiz_tilemap_index_addr_table)
data = patch(data, 0x1FF80, orig_quiz_tilemap_index_addr_table)
orig_quiz_tiledata_info_table_offset = 0x1C17A
orig_quiz_tiledata_info_table = data[orig_quiz_tiledata_info_table_offset:orig_quiz_tiledata_info_table_offset+0x6]
data = patch(data, 0x1FF90, orig_quiz_tiledata_info_table)
data = patch(data, 0x1FF98, orig_quiz_tiledata_info_table)

quiz_tilemap_data_table_addrs = 0x1C36D
quiz_tilemap_data_table = u16(data[quiz_tilemap_data_table_addrs:quiz_tilemap_data_table_addrs+2])
quiz_tilemap_data_table_bank = data[quiz_tilemap_data_table_addrs+2]
quiz_tilemap_index_table_addrs = 0x1C47D
quiz_tilemap_index_table = u16(data[quiz_tilemap_index_table_addrs:quiz_tilemap_index_table_addrs+2])
quiz_tilemap_index_table_bank = data[quiz_tilemap_index_table_addrs+2]

quiz_tilemap_index_offset = quiz_tilemap_index_table_bank * 0x4000 + (quiz_tilemap_index_table - 0x4000)
quiz_tilemap_data_offset = quiz_tilemap_data_table_bank * 0x4000 + (quiz_tilemap_data_table - 0x4000)
quiz_tilemap_index = data[quiz_tilemap_index_offset:quiz_tilemap_index_offset+0x90*2]
quiz_tilemap_data = data[quiz_tilemap_data_offset:quiz_tilemap_data_offset+0x100]

quiz_tile = [ [0]*32 for _ in range(36) ]
outidx = 0
for i in range(0x90*2):
    idx = (quiz_tilemap_index[i] * 4)
    tile = quiz_tilemap_data[idx:idx+4]
    tile = b"".join(map(lambda x: p8(x+0x20) if x >= 0x21 and x <= 0x28 else p8(x), tile))
    tile = b"".join(map(lambda x: p8(0x18) if x == 0x1D else p8(x), tile))
    quiz_tile[outidx//32][outidx%32] = tile[0]
    quiz_tile[outidx//32][outidx%32+1] = tile[1]
    quiz_tile[outidx//32+1][outidx%32] = tile[2]
    quiz_tile[outidx//32+1][outidx%32+1] = tile[3]
    outidx += 2
    if outidx % 32 == 0: outidx += 32

for i in range(9):
    quiz_tile[6][1+(i*2)] = 0x1d
for i in range(5):
    quiz_tile[6][22+(i*2)] = 0x1d
for i in range(4):
    quiz_tile[24][(i*2)] = 0x1d


quiz_tiledata_info = 0x1C17A
quiz_tiledata_cnt = data[quiz_tiledata_info]
quiz_tiledata_bank = data[quiz_tiledata_info+1]
quiz_tiledata_addr = u16(data[quiz_tiledata_info+2:quiz_tiledata_info+4])
quiz_tiledata_offset = quiz_tiledata_bank * 0x4000 + (quiz_tiledata_addr - 0x4000)

def create_quiz_tile(quiz_tile, quiz_text):
    new_quiz_tiledata = data[quiz_tiledata_offset:quiz_tiledata_offset+(quiz_tiledata_cnt*0x10)]
    quiz_text_uniq = "".join(list(dict.fromkeys("".join(quiz_text))))
    for i in range(len(quiz_text_uniq)):
        new_quiz_tiledata = patch(new_quiz_tiledata, (0x11+i)*0x10, get_font(quiz_text_uniq[i]))

    new_quiz_tiledata = patch(new_quiz_tiledata, (0x11+len(quiz_text_uniq))*0x10, b"\x0C\x0C\x1C\x1C\x1C\x1C\x18\x18\x10\x10\x00\x00\x30\x30\x00\x00")

    quiz_tile_chr_pos = [
    [(3,3),(5,3),(7,3),(9,3),(11,3),(13,3),(15,3),(17,3)],
    [(3,5),(5,5),(7,5),(9,5),(11,5),(13,5),(15,5),(17,5)],
    [(24,3),(26,3),(28,3),(30,3),(0,21),(2,21),(4,21),(6,21)],
    [(24,5),(26,5),(28,5),(30,5),(0,23),(2,23),(4,23),(6,23)]]

    for i in range(len(quiz_text)):
        length = len(quiz_text[i])
        for j in range(length):
            tile_num = 0x21 + quiz_text_uniq.find(quiz_text[i][j])
            x, y = quiz_tile_chr_pos[i][j]
            quiz_tile[y][x] = tile_num

        if i % 2 == 0:
            for j in range(length, 7):
                x, y = quiz_tile_chr_pos[i][j]
                quiz_tile[y][x] = 0
        else:
            x, y = quiz_tile_chr_pos[i][length]
            quiz_tile[y][x] = 0x21 + len(quiz_text_uniq)
            for j in range(length+1, 8):
                x, y = quiz_tile_chr_pos[i][j]
                quiz_tile[y][x] = 0

    new_quiz_tilemap = {}
    new_quiz_tilemap_data = b""
    new_quiz_tilemap_index1 = b""
    cnt = 0
    for i in range(0, 18, 2):
        for j in range(0, 32, 2):
            tm = p8(quiz_tile[i][j]) + p8(quiz_tile[i][j+1]) + p8(quiz_tile[i+1][j]) + p8(quiz_tile[i+1][j+1])
            if (tm in new_quiz_tilemap) == False:
                new_quiz_tilemap_data += tm
                new_quiz_tilemap[tm] = cnt
                cnt += 1
            new_quiz_tilemap_index1 += p8(new_quiz_tilemap[tm])

    new_quiz_tilemap_index2 = b""
    for i in range(18, 36, 2):
        for j in range(0, 32, 2):
            tm = p8(quiz_tile[i][j]) + p8(quiz_tile[i][j+1]) + p8(quiz_tile[i+1][j]) + p8(quiz_tile[i+1][j+1])
            if (tm in new_quiz_tilemap) == False:
                new_quiz_tilemap_data += tm
                new_quiz_tilemap[tm] = cnt
                cnt += 1
            new_quiz_tilemap_index2 += p8(new_quiz_tilemap[tm])
    
    return new_quiz_tiledata, new_quiz_tilemap_data, new_quiz_tilemap_index1+new_quiz_tilemap_index2

def create_quiz_data(quiz_numbers, quiz_text):
    quiz_text_uniq = "".join(list(dict.fromkeys("".join(quiz_text))))    
    quiz_answer_xy = b""
    quiz_answer_code = b""
    current_page = 1
    bang_xy = [0x21+len(quiz_text[1]), 0x21+len(quiz_text[3])]
    quiz_numbers_strip = "".join(quiz_numbers).replace(" ", "")
    for i in range(0, len(quiz_numbers_strip), 2):
        xy = int(quiz_numbers_strip[i] + quiz_numbers_strip[i+1], 16)
        if xy == bang_xy[current_page]:
            current_page ^= 1
        else:
            x = int(quiz_numbers_strip[i+1])-1
            y = int(quiz_numbers_strip[i])-1
            if x >= len(quiz_text[current_page*2 + y]):
                quiz_answer_code += p8(0)
            else:
                char = quiz_text[current_page*2 + y][x]
                quiz_answer_code += p8(quiz_text_uniq.find(char) + 1)
        quiz_answer_xy += p8(current_page * 0x80 + xy - 0x11)

    quiz_text_code = b""
    for i in range(len(quiz_text)):
        length = len(quiz_text[i])
        for j in range(length):
            quiz_text_code += p8(quiz_text_uniq.find(quiz_text[i][j]) + 1)
        if i % 2 == 0: quiz_text_code += b"\x00"*(7-length) + b"\xFF"
        else: quiz_text_code += b"\xFE" + b"\x00"*(7-length)

    hangul_len = len(font) // 0x10
    quiz_text_hangul_code_table = pb16(0xE000 + hangul_len + 1)  # hack
    for i in range(len(quiz_text_uniq)):
        quiz_text_hangul_code_table += str2code(quiz_text_uniq[i])

    return quiz_text_code, quiz_answer_xy, quiz_answer_code, quiz_text_hangul_code_table

quiz1_text = ["평범한", "유원지는가라", "인기많은", "놀이기구한가득"]
quiz1_num = ["2812 2711 1428 15", "27 2528 2227 12  "]
new_quiz_tiledata, new_quiz_tilemap_data, new_quiz_tilemap_index = create_quiz_tile(quiz_tile, quiz1_text)
quiz_text_code, quiz_answer_xy, quiz_answer_code, quiz_text_hangul_code_table = create_quiz_data(quiz1_num, quiz1_text)

new_quiz_tiledata1_bank = 0x1F
new_quiz_tiledata1_addr = 0x4000 + 0x1000
data = patch(data, new_quiz_tiledata1_bank * 0x4000 + (new_quiz_tiledata1_addr - 0x4000), new_quiz_tiledata)
new_quiz_tilemap_data1_bank = 0x1F
new_quiz_tilemap_data1_addr = 0x4000 + 0x1600
data = patch(data, new_quiz_tilemap_data1_bank * 0x4000 + (new_quiz_tilemap_data1_addr - 0x4000), new_quiz_tilemap_data)
new_quiz_tilemap_index1_bank = 0x1F
new_quiz_tilemap_index1_addr = 0x4000 + 0x1800
data = patch(data, new_quiz_tilemap_index1_bank * 0x4000 + (new_quiz_tilemap_index1_addr - 0x4000), new_quiz_tilemap_index)

newbank_quiz_text_start_offset = 0x7CE00
data = patch(data, newbank_quiz_text_start_offset, quiz_text_code)
data = patch(data, newbank_quiz_text_start_offset+0x20, quiz_answer_xy)
data = patch(data, newbank_quiz_text_start_offset+0x2E, quiz_answer_code)

new_quiz_text_hangul_code_table_bank = 0x1F
new_quiz_text_hangul_code_table_addr = 0x4000 + 0xF00
data = patch(data, new_quiz_text_hangul_code_table_bank * 0x4000 + (new_quiz_text_hangul_code_table_addr - 0x4000), quiz_text_hangul_code_table)

data = patch(data, 0xBFFB, p8(len(quiz_answer_xy)))
data = patch(data, 0xBFFD, p8(len(quiz_answer_code)))


quiz2_text = ["인기오락실에다", "쿠폰적립도", "오팔같은비범한", "보물도한가득"]
quiz2_num = ["1627 1126 1427 13", "26 1127 2126 21  "]
new_quiz_tiledata, new_quiz_tilemap_data, new_quiz_tilemap_index = create_quiz_tile(quiz_tile, quiz2_text)
quiz_text_code, quiz_answer_xy, quiz_answer_code, quiz_text_hangul_code_table = create_quiz_data(quiz2_num, quiz2_text)

new_quiz_tiledata2_bank = 0x1F
new_quiz_tiledata2_addr = 0x4000 + 0x1300
data = patch(data, new_quiz_tiledata2_bank * 0x4000 + (new_quiz_tiledata2_addr - 0x4000), new_quiz_tiledata)
new_quiz_tilemap_data2_bank = 0x1F
new_quiz_tilemap_data2_addr = 0x4000 + 0x1700
data = patch(data, new_quiz_tilemap_data2_bank * 0x4000 + (new_quiz_tilemap_data2_addr - 0x4000), new_quiz_tilemap_data)
new_quiz_tilemap_index2_bank = 0x1F
new_quiz_tilemap_index2_addr = 0x4000 + 0x1920
data = patch(data, new_quiz_tilemap_index2_bank * 0x4000 + (new_quiz_tilemap_index2_addr - 0x4000), new_quiz_tilemap_index)

newbank_quiz_text_start_offset = 0x7CE00
data = patch(data, newbank_quiz_text_start_offset+0x40, quiz_text_code)
data = patch(data, newbank_quiz_text_start_offset+0x60, quiz_answer_xy)
data = patch(data, newbank_quiz_text_start_offset+0x6E, quiz_answer_code)

new_quiz_text_hangul_code_table_bank = 0x1F
new_quiz_text_hangul_code_table_addr = 0x4000 + 0xF40
data = patch(data, new_quiz_text_hangul_code_table_bank * 0x4000 + (new_quiz_text_hangul_code_table_addr - 0x4000), quiz_text_hangul_code_table)

data = patch(data, 0xBFFC, p8(len(quiz_answer_xy)))
data = patch(data, 0xBFFE, p8(len(quiz_answer_code)))


data = patch(data, 0x1FF60+5, p16(new_quiz_tilemap_data1_addr) + p8(new_quiz_tilemap_data1_bank))
data = patch(data, 0x1FF68+5, p16(new_quiz_tilemap_data2_addr) + p8(new_quiz_tilemap_data2_bank))
data = patch(data, 0x1FF70, p16(new_quiz_tilemap_index1_addr) + p8(new_quiz_tilemap_index1_bank) + p16(new_quiz_tilemap_index1_addr+0x90) + p8(new_quiz_tilemap_index1_bank))
data = patch(data, 0x1FF80, p16(new_quiz_tilemap_index2_addr) + p8(new_quiz_tilemap_index2_bank) + p16(new_quiz_tilemap_index2_addr+0x90) + p8(new_quiz_tilemap_index2_bank))
data = patch(data, 0x1FF90+1, p8(new_quiz_tiledata1_bank) + p16(new_quiz_tiledata1_addr))
data = patch(data, 0x1FF98+1, p8(new_quiz_tiledata2_bank) + p16(new_quiz_tiledata2_addr))

quiz_numbers_bytes = b"".join(map(lambda x: p8(int(x)) if x != " " else p8(0), "".join(quiz1_num)))
data = patch(data, 0x9275, quiz_numbers_bytes)
quiz_numbers_bytes = b"".join(map(lambda x: p8(int(x)) if x != " " else p8(0), "".join(quiz2_num)))
data = patch(data, 0x948E, quiz_numbers_bytes)

data = patch(data, 0x93EF, p16(0xC500))
data = patch(data, 0x93F4, p16(0xC510))
data = patch(data, 0x92E7, p16(0xC520))
data = patch(data, 0x92FB, p16(0xC52E))
data = patch(data, 0x9411, p8(0xD))
data = patch(data, 0x9469, p8(0xD))

menu_think_tilemap_addrs = 0x1C231
menu_think_tilemap_index_table = u16(data[menu_think_tilemap_addrs:menu_think_tilemap_addrs+2])
menu_think_tilemap_index_table_bank = data[menu_think_tilemap_addrs+2]
menu_think_tilemap_data_table = u16(data[menu_think_tilemap_addrs+3:menu_think_tilemap_addrs+5])
menu_think_tilemap_data_table_bank = data[menu_think_tilemap_addrs+5]

menu_think_tilemap_index_offset = menu_think_tilemap_index_table_bank * 0x4000 + (menu_think_tilemap_index_table - 0x4000)
menu_think_tilemap_data_offset = menu_think_tilemap_data_table_bank * 0x4000 + (menu_think_tilemap_data_table - 0x4000)

menu_think_tilemap_index = data[menu_think_tilemap_index_offset:menu_think_tilemap_index_offset+0x3C]
menu_think_tilemap_data = data[menu_think_tilemap_data_offset:menu_think_tilemap_data_offset+0x40]

menu_think_tile = [ [0]*20 for _ in range(12) ]
outidx = 0
for i in range(len(menu_think_tilemap_index)):
    idx = (menu_think_tilemap_index[i] * 4)
    tile = menu_think_tilemap_data[idx:idx+4]
    menu_think_tile[outidx//20][outidx%20] = tile[0]
    menu_think_tile[outidx//20][outidx%20+1] = tile[1]
    menu_think_tile[outidx//20+1][outidx%20] = tile[2]
    menu_think_tile[outidx//20+1][outidx%20+1] = tile[3]
    outidx += 2
    if outidx % 20 == 0: outidx += 20

for i in range(3):
    menu_think_tile[i][12] = menu_think_tile[i][13]
for i in range(3):
    menu_think_tile[i][13] = menu_think_tile[i][14]

new_menu_think_tilemap = {}
new_menu_think_tilemap_data = b""
new_menu_think_tilemap_index = b""
cnt = 0
for i in range(0, 12, 2):
    for j in range(0, 20, 2):
        tm = p8(menu_think_tile[i][j]) + p8(menu_think_tile[i][j+1]) + p8(menu_think_tile[i+1][j]) + p8(menu_think_tile[i+1][j+1])
        if (tm in new_menu_think_tilemap) == False:
            new_menu_think_tilemap_data += tm
            new_menu_think_tilemap[tm] = cnt
            cnt += 1
        new_menu_think_tilemap_index += p8(new_menu_think_tilemap[tm])

data = patch(data, menu_think_tilemap_index_offset, new_menu_think_tilemap_index)
data = patch(data, menu_think_tilemap_data_offset, new_menu_think_tilemap_data)


menu_suspect_tilemap_addrs = 0x1C229
menu_suspect_tilemap_index_table = u16(data[menu_suspect_tilemap_addrs:menu_suspect_tilemap_addrs+2])
menu_suspect_tilemap_index_table_bank = data[menu_suspect_tilemap_addrs+2]
menu_suspect_tilemap_data_table = u16(data[menu_suspect_tilemap_addrs+3:menu_suspect_tilemap_addrs+5])
menu_suspect_tilemap_data_table_bank = data[menu_suspect_tilemap_addrs+5]

menu_suspect_tilemap_index_offset = menu_suspect_tilemap_index_table_bank * 0x4000 + (menu_suspect_tilemap_index_table - 0x4000)
menu_suspect_tilemap_data_offset = menu_suspect_tilemap_data_table_bank * 0x4000 + (menu_suspect_tilemap_data_table - 0x4000)

menu_suspect_tilemap_index = data[menu_suspect_tilemap_index_offset:menu_suspect_tilemap_index_offset+0x3C]
menu_suspect_tilemap_data = data[menu_suspect_tilemap_data_offset:menu_suspect_tilemap_data_offset+0x7C]

menu_suspect_tile = [ [0]*20 for _ in range(12) ]
outidx = 0
for i in range(len(menu_suspect_tilemap_index)):
    idx = (menu_suspect_tilemap_index[i] * 4)
    tile = menu_suspect_tilemap_data[idx:idx+4]
    menu_suspect_tile[outidx//20][outidx%20] = tile[0]
    menu_suspect_tile[outidx//20][outidx%20+1] = tile[1]
    menu_suspect_tile[outidx//20+1][outidx%20] = tile[2]
    menu_suspect_tile[outidx//20+1][outidx%20+1] = tile[3]
    outidx += 2
    if outidx % 20 == 0: outidx += 20

for i in range(3):
    menu_suspect_tile[i][12] = menu_suspect_tile[i][11]
for i in range(3):
    menu_suspect_tile[i][11] = menu_suspect_tile[i][10]

new_menu_suspect_tilemap = {}
new_menu_suspect_tilemap_data = b""
new_menu_suspect_tilemap_index = b""
cnt = 0
for i in range(0, 12, 2):
    for j in range(0, 20, 2):
        tm = p8(menu_suspect_tile[i][j]) + p8(menu_suspect_tile[i][j+1]) + p8(menu_suspect_tile[i+1][j]) + p8(menu_suspect_tile[i+1][j+1])
        if (tm in new_menu_suspect_tilemap) == False:
            new_menu_suspect_tilemap_data += tm
            new_menu_suspect_tilemap[tm] = cnt
            cnt += 1
        new_menu_suspect_tilemap_index += p8(new_menu_suspect_tilemap[tm])

data = patch(data, menu_suspect_tilemap_index_offset, new_menu_suspect_tilemap_index)
data = patch(data, menu_suspect_tilemap_data_offset, new_menu_suspect_tilemap_data)

data = patch(data, 0x148, b"\x04")
data = patch(data, 0x14D, p8(gb_checksum1(data)))
data = patch(data, 0x14E, pb16(gb_checksum2(data)))

open("output.gb", "wb").write(data)