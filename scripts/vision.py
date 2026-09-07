# -*- coding: utf-8 -*-
"""多模态饮食图片识别模块：通过 openai Python 库调用视觉模型
(async) QwenVL / GLM-4V / GPT-4o 等，从图片中识别饮食描述，
产出可供 calc.parse_meal 解析的结构化描述串。

- 依赖第三方库 openai（`pip install openai`）。
- API Key 来源优先级：显式参数 > settings.json 的 vision 段 > 环境变量。
- 支持多服务商切换，当前激活的服务商通过 `vision config` 配置。
"""
import base64
import json
import mimetypes
import os
import sys

from openai import OpenAI

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS_PATH = os.path.join(SKILL_DIR, "data", "settings.json")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# 支持的服务商（均为 OpenAI 兼容接口，可直接套用 openai 库）
PROVIDERS = {
    "qwen": {
        "name": "QwenVL(通义千问)",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-vl-max",
        "env_key": "DASHSCOPE_API_KEY",
    },
    "glm": {
        "name": "GLM-4V(智谱)",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "default_model": "glm-4v",
        "env_key": "ZHIPUAI_API_KEY",
    },
    "openai": {
        "name": "GPT-4o(OpenAI)",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o",
        "env_key": "OPENAI_API_KEY",
    },
}

IMAGE_PROMPT = (
    "你是一个饮食营养记录助手，请根据图片中的食物，输出一份可被程序解析的饮食记录描述。\n"
    "必须遵守：\n"
    "1. 只输出食物描述本身，不要任何解释、评论、序号或多余文字。\n"
    "2. 每种食物用「数量+单位+食物名」格式，例如：1碗米饭、150克鸡胸肉(煎)。\n"
    "3. 多种食物用中文逗号「，」分隔。\n"
    "4. 烹饪方式（煎/炸/炒/烤/蒸/煮/红烧/清炒等）写在食物名后的括号里。\n"
    "5. 使用常见单位：克/碗/个/杯/份/两；估算份量要合理，宁可少估也不要夸大。\n"
    "6. 若实在无法识别任何食物，只输出四个字：无法识别。\n"
)


def load_vision_config():
    """读取 vision 配置；settings.json 不存在或损坏时返回 {}。"""
    if os.path.exists(SETTINGS_PATH):
        try:
            data = json.load(open(SETTINGS_PATH, encoding="utf-8"))
            return data.get("vision", {})
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_vision_config(provider, api_key, model=None):
    """保存当前激活的视觉服务商配置到 settings.json，保留其余字段。"""
    data = {}
    if os.path.exists(SETTINGS_PATH):
        try:
            data = json.load(open(SETTINGS_PATH, encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
    cfg = {"provider": provider, "api_key": api_key}
    if model:
        cfg["model"] = model
    data["vision"] = cfg
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return cfg


def resolve_credentials(provider, api_key_override=None, model_override=None):
    """解析 provider 的 API Key 与模型名。优先级：显式参数 > settings.json > 环境变量。"""
    info = PROVIDERS[provider]
    cfg = load_vision_config()
    key = api_key_override or cfg.get("api_key") or os.environ.get(info["env_key"])
    if not key:
        raise ValueError(
            f"未配置 {info['name']} 的 API Key：请执行 "
            f"`diet vision config {provider} <api_key>`，或设置环境变量 {info['env_key']}"
        )
    model = model_override or cfg.get("model") or info["default_model"]
    return key, model


def encode_image(image_path):
    """读取图片并编码为 base64 data URL（适合 OpenAI 兼容接口）。"""
    try:
        with open(image_path, "rb") as f:
            raw = f.read()
    except OSError as exc:
        raise ValueError(f"无法读取图片: {image_path} ({exc})")
    mime = mimetypes.guess_type(image_path)[0] or "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(raw).decode("ascii")


def build_messages(image_path, prompt=IMAGE_PROMPT):
    """构造多模态对话消息，供 openai 库调用，也用于 --dry-run 预览。"""
    data_url = encode_image(image_path)
    return [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        }
    ]


def chat(client, messages, model, timeout=60):
    """通过 openai 库调用视觉模型，返回回复文本。"""
    from openai import APIError, APIConnectionError

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=300,
            temperature=0.2,
            timeout=timeout,
        )
    except APIConnectionError as exc:
        raise RuntimeError(f"网络请求失败: {exc}") from exc
    except APIError as exc:
        raise RuntimeError(f"模型接口返回错误: {exc}") from exc

    choices = resp.choices or []
    if not choices:
        raise RuntimeError("模型未返回有效结果")
    content = choices[0].message.content or ""
    if isinstance(content, list):  # 某些模型返回分段 content 数组
        content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
    return str(content).strip()


def analyze_image(image_path, provider=None, model=None, timeout=60):
    """识别图片中的食物，返回描述串。无配置或无图片均抛 ValueError。"""
    provider = provider or load_vision_config().get("provider")
    if not provider:
        raise ValueError("未配置视觉服务商，请先执行 `diet vision config <provider> <api_key>`")
    if provider not in PROVIDERS:
        raise ValueError(f"未知服务商 {provider}，可选: {', '.join(PROVIDERS)}")

    api_key, resolved_model = resolve_credentials(provider, model_override=model)
    client = OpenAI(
        base_url=PROVIDERS[provider]["base_url"],
        api_key=api_key,
        timeout=timeout,
    )
    messages = build_messages(image_path)
    content = chat(client, messages, resolved_model, timeout)

    if content.strip().rstrip("。").replace(" ", "") == "无法识别":
        raise ValueError("模型未能识别出图片中的食物，请换一张更清晰的照片或改用文字描述")

    return content