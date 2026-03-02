"""
签名验证器
"""
import hmac
import hashlib
import base64


class SignatureVerifier:
    """签名验证器"""

    def __init__(self, app_secret: str):
        self.app_secret = base64.b64decode(app_secret)

    def verify(
        self,
        timestamp: str,
        nonce: str,
        body: bytes,
        signature: str
    ) -> bool:
        """
        验证飞书请求签名

        Args:
            timestamp: 请求时间戳
            nonce: 随机数
            body: 请求体
            signature: 签名值

        Returns:
            是否验证通过
        """
        if not all([timestamp, nonce, body, signature]):
            return False

        # 构建签名字符串
        sign_str = f"{timestamp}\n{nonce}\n{body.decode('utf-8')}"

        # 计算签名
        sign_bytes = hmac.new(
            self.app_secret,
            sign_str.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        expected_signature = base64.b64encode(sign_bytes).decode()

        # 恒时比较（防止时序攻击）
        return hmac.compare_digest(signature, expected_signature)
