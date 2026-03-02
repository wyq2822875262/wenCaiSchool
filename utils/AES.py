import json, base64
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

# 密钥
key = b"5165325946459632"
# 偏移量
iv = b"8655624543959233"


def aes_encrypt(plaintext):
    """
    对输入的文本进行加密
    :param plaintext: string/int/float - 输入的数据，支持字符串、数字等类型
    :return: string(base64)
    """
    # 将输入转换为字符串
    plaintext_str = str(plaintext)

    cipher = AES.new(key, AES.MODE_CBC, iv)
    padded_plaintext = pad(plaintext_str.encode(), AES.block_size)
    ciphertext = cipher.encrypt(padded_plaintext)
    return base64.b64encode(ciphertext).decode()


# 解密
def aes_decrypt(ciphertext):
    """
    对密文进行解密
    :param ciphertext: string(base64)
    :return: dict 或 string
    """
    # 解密
    cipher = AES.new(key, AES.MODE_CBC, iv)
    padded_plaintext = cipher.decrypt(base64.b64decode(ciphertext))
    plaintext = unpad(padded_plaintext, AES.block_size).decode()

    # 尝试解析为 JSON
    try:
        # 将单引号替换为双引号（兼容不规范 JSON）
        normalized_text = plaintext.replace("'", '"')
        return json.loads(normalized_text)
    except json.JSONDecodeError:
        # 如果不是 JSON 格式，直接返回字符串
        return plaintext

if __name__ == '__main__':
    data = aes_decrypt("hOzniORz0aV2/qDzSKeobPT7hQGoIr/luy+lJaHEPHA=")
    print(data)