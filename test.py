import zlib
def file_crc32(path):
    try:
        bufsize = 65536
        crc = 0
        with open(path, 'rb') as f:
            while True:
                data = f.read(bufsize)
                if not data:
                    break
                crc = zlib.crc32(data, crc)
        return crc & 0xFFFFFFFF
    except Exception:
        return None
    
if __name__ == "__main__":
    files=[
        "IMG_0048.JPG",
        "IMG_0048_2.JPG",
    ]

    for file in files:
        # 将file转换为hex格式的txt文件，每8个字节一行
        with open(file, 'rb') as f:
            data = f.read()
        hex_file = file + ".hex.txt"
        with open(hex_file, 'w') as hf:
            for i in range(0, len(data), 8):
                line = data[i:i+8]
                hf.write(' '.join(f"{b:02x}" for b in line) + '\n')
        

    for file in files:
        crc = file_crc32(file)
        if crc is not None:
            print(f"CRC32 of {file}: {hex(crc)}")
        else:
            print(f"Failed to calculate CRC32 for {file}")