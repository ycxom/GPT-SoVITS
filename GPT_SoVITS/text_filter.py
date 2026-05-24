"""
文本屏蔽词过滤器

用于在 TTS 推理前拦截与屏蔽词完全匹配的文本请求。
匹配不区分大小写，且会去除首尾空白。
"""

BLOCKED_KEYWORDS = [
    "未适配或纯音乐",
]

# 纯音乐/无歌词相关的扩展屏蔽词
BLOCKED_KEYWORDS_EXTRA = [
]


def filter_text(text: str) -> tuple[bool, str]:
    """
    检查文本是否与屏蔽词完全匹配。

    Args:
        text: 待检查的文本

    Returns:
        (is_blocked, matched_keyword) 元组
        - is_blocked: True 表示文本被屏蔽
        - matched_keyword: 命中的屏蔽词（用于日志/提示）
    """
    if not text or not text.strip():
        return False, ""

    text_stripped = text.strip().lower()

    for keyword in BLOCKED_KEYWORDS:
        if text_stripped == keyword.lower():
            return True, keyword

    for keyword in BLOCKED_KEYWORDS_EXTRA:
        if text_stripped == keyword.lower():
            return True, keyword

    return False, ""


def is_text_blocked(text: str) -> bool:
    """
    快速检查文本是否被屏蔽。
    """
    blocked, _ = filter_text(text)
    return blocked