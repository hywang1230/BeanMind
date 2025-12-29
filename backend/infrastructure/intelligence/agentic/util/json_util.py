import json


def parse_json_from_markdown(text: str) -> dict:
    f"""
    解析文本为 json 格式，去除markdown格式

    Args:
        text: 文本

    Returns:
        dict: json 格式，如果解析失败则返回空字典
    """
    # 去除 markdown 代码块标记
    text = text.strip()
    if text.startswith("```"):
        # 移除开头的 ```json 或 ```
        lines = text.split('\n')
        if lines[0].startswith("```"):
            lines = lines[1:]
        # 移除结尾的 ```
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = '\n'.join(lines)
    
    # 找到第一个 { 和最后一个 }
    first_brace = text.find('{')
    last_brace = text.rfind('}')
    
    if first_brace != -1 and last_brace != -1 and first_brace < last_brace:
        text = text[first_brace:last_brace + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}