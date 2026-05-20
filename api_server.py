"""
# WebAPI文档

` python api_v2.py -a 127.0.0.1 -p 9880 -c GPT_SoVITS/configs/tts_infer.yaml `

## 执行参数:
    `-a` - `绑定地址, 默认"0.0.0.0"`
    `-p` - `绑定端口, 默认9880`
    `-c` - `TTS配置文件路径, 默认"GPT_SoVITS/configs/tts_infer.yaml"`

## 调用:

### 推理

endpoint: `/tts`
GET:
```
http://127.0.0.1:9880/tts?text=先帝创业未半而中道崩殂，今天下三分，益州疲弊，此诚危急存亡之秋也。&text_lang=zh&ref_audio_path=archive_jingyuan_1.wav&prompt_lang=zh&prompt_text=我是「罗浮」云骑将军景元。不必拘谨，「将军」只是一时的身份，你称呼我景元便可&text_split_method=cut5&batch_size=1&media_type=wav&streaming_mode=true
```

**注意：`text_lang` 参数支持智能语言识别，当不提供此参数时，系统将自动检测文本语言并进行智能处理。**
```
http://127.0.0.1:9880/tts?text=Hello, 你好こんにちは&ref_audio_path=archive_jingyuan_1.wav&prompt_lang=zh&prompt_text=我是「罗浮」云骑将军景元&text_split_method=cut5&batch_size=1&media_type=wav&streaming_mode=true
```

POST:
```json
{
    "text": "",                   # str.(required) text to be synthesized
    "text_lang: "",               # str.(required) language of the text to be synthesized
    "ref_audio_path": "",         # str.(required) reference audio path
    "aux_ref_audio_paths": [],    # list.(optional) auxiliary reference audio paths for multi-speaker tone fusion
    "prompt_text": "",            # str.(optional) prompt text for the reference audio
    "prompt_lang": "",            # str.(required) language of the prompt text for the reference audio
    "top_k": 15,                  # int. top k sampling
    "top_p": 1,                   # float. top p sampling
    "temperature": 1,             # float. temperature for sampling
    "text_split_method": "cut5",  # str. text split method, see text_segmentation_method.py for details.
    "batch_size": 1,              # int. batch size for inference
    "batch_threshold": 0.75,      # float. threshold for batch splitting.
    "split_bucket": True,         # bool. whether to split the batch into multiple buckets.
    "speed_factor":1.0,           # float. control the speed of the synthesized audio.
    "fragment_interval":0.3,      # float. to control the interval of the audio fragment.
    "seed": -1,                   # int. random seed for reproducibility.
    "parallel_infer": True,       # bool. whether to use parallel inference.
    "repetition_penalty": 1.35,   # float. repetition penalty for T2S model.
    "sample_steps": 32,           # int. number of sampling steps for VITS model V3.
    "super_sampling": False,      # bool. whether to use super-sampling for audio when using VITS model V3.
    "streaming_mode": False,      # bool or int. return audio chunk by chunk. The available options are: 0,1,2,3 or True/False (0/False: Disabled | 1/True: Best Quality, Slowest response speed (old version streaming_mode) | 2: Medium Quality, Slow response speed | 3: Lower Quality, Faster response speed )
    "overlap_length": 2,          # int. overlap length of semantic tokens for streaming mode.
    "min_chunk_length": 16,       # int. The minimum chunk length of semantic tokens for streaming mode. (affects audio chunk size)
}
```

RESP:
成功: 直接返回 wav 音频流， http code 200
失败: 返回包含错误信息的 json, http code 400

### 命令控制

endpoint: `/control`

command:
"restart": 重新运行
"exit": 结束运行

GET:
```
http://127.0.0.1:9880/control?command=restart
```
POST:
```json
{
    "command": "restart"
}
```

RESP: 无


### 切换GPT模型

endpoint: `/set_gpt_weights`

GET:
```
http://127.0.0.1:9880/set_gpt_weights?weights_path=GPT_SoVITS/pretrained_models/s1bert25hz-2kh-longer-epoch=68e-step=50232.ckpt
```
RESP:
成功: 返回"success", http code 200
失败: 返回包含错误信息的 json, http code 400


### 切换Sovits模型

endpoint: `/set_sovits_weights`

GET:
```
http://127.0.0.1:9880/set_sovits_weights?weights_path=GPT_SoVITS/pretrained_models/s2G488k.pth
```

RESP:
成功: 返回"success", http code 200
失败: 返回包含错误信息的 json, http code 400

"""

import os
import sys
import traceback
import re
import time
from typing import Union
from collections import defaultdict
from datetime import datetime, timedelta
import yaml
import uuid

now_dir = os.getcwd()
sys.path.append(now_dir)
sys.path.append("%s/GPT_SoVITS" % (now_dir))

import argparse
import signal
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse, JSONResponse
import uvicorn
from io import BytesIO
from tools.i18n.i18n import I18nAuto
from GPT_SoVITS.TTS_infer_pack.TTS import TTS, TTS_Config
from GPT_SoVITS.TTS_infer_pack.text_segmentation_method import get_method_names as get_cut_method_names
from pydantic import BaseModel
from pathlib import Path
from glob import glob
from random import choice
from re import split

# 导入统计和安全模块
from api_stats import get_stats_manager, register_stats_routes

# 导入 api_v2 的核心功能
import api_v2

# print(sys.path)
i18n = I18nAuto()
cut_method_names = get_cut_method_names()

LANG_MAPPING = {
    "zh": "中文",
    "en": "英语",
    "ja": "日语",
    "yue": "粤语",
    "ko": "韩语"
}

LANG_MAPPING_REVERSE = {v: k for k, v in LANG_MAPPING.items()}

VERSION_PRIORITY = ["v2ProPlus", "v2Pro", "v4", "v3", "v2"]

#===============自动获取参考音频和文本的函数================

def get_tag_text(file_name):
    """根据参考音频文件名分离情感名称和参考文本"""
    tag = split("【|】", file_name)[1]
    text = split("【|】", file_name)[2]
    return tag, text

def get_ref_audio(model_name: str, lang: str, emotion: str, version: str = "v4") -> tuple[str, str]:
    """获取指定情感的完整参考音频文件名和对应的prompt_text"""
    emo = ""
    emo_text = ""
    
    actual_lang = LANG_MAPPING.get(lang, lang)
    
    version_paths = [f"models/{version}"] + [f"models/{v}" for v in VERSION_PRIORITY if v != version]
    
    for version_path in version_paths:
        if Path(f"{version_path}/{model_name}").exists():
            # 先尝试原始语言代码
            audios = glob(f"{version_path}/{model_name}/reference_audios/{lang}/emotions/*.wav")
            if not audios:
                # 如果没找到，尝试映射后的语言目录名
                audios = glob(f"{version_path}/{model_name}/reference_audios/{actual_lang}/emotions/*.wav")
            
            for audio in audios:
                audio_name = str(Path(audio).name).replace(".wav", "")
                if f"【{emotion}】" in audio_name:
                    emo, emo_text = get_tag_text(audio_name)
                    return emo, emo_text
    return emo, emo_text

def random_ref_audio(model_name: str, lang: str, version: str = "v4"):
    """随机选择参考音频"""
    version_paths = [f"models/{version}"] + [f"models/{v}" for v in VERSION_PRIORITY if v != version]
    
    for version_path in version_paths:
        if Path(f"{version_path}/{model_name}").exists():
            if Path(f"{version_path}/{model_name}/reference_audios/{lang}/randoms").exists():
                audios = glob(f"{version_path}/{model_name}/reference_audios/{lang}/randoms/*.wav")
                if audios:
                    audio = choice(audios)
                    lab_content = Path(audio).name.replace(".wav", "")
                    return audio, lab_content
    
    return "", ""

def auto_get_ref_audio_and_prompt_text(model_name: str = "", prompt_lang: str = "", emotion: str = "默认", version: str = "v4"):
    """自动获取参考音频路径和prompt_text"""
    if model_name == "" or prompt_lang == "":
        return "", ""
    
    actual_lang = LANG_MAPPING.get(prompt_lang, prompt_lang)
    
    if emotion == "随机":
        ref_audio, lab_content = random_ref_audio(model_name, actual_lang, version)
        prompt_text = lab_content
    else:
        emo, prompt_text = get_ref_audio(model_name, prompt_lang, emotion, version)
        if emo != "":
            version_paths = [f"models/{version}"] + [f"models/{v}" for v in VERSION_PRIORITY if v != version]
            ref_audio = ""
            for version_path in version_paths:
                if Path(f"{version_path}/{model_name}").exists():
                    # 使用映射后的语言目录名
                    potential_path = f"{version_path}/{model_name}/reference_audios/{actual_lang}/emotions/【{emo}】{prompt_text}.wav"
                    if Path(potential_path).exists():
                        ref_audio = potential_path
                        if should_log('api_details'):
                            print(f"📁 找到参考音频 - 路径: {ref_audio}")
                        break
        else:
            ref_audio = ""
            prompt_text = ""
    
    return ref_audio, prompt_text

def extract_language_from_model_name(model_name: str) -> str:
    """从模型名称中提取语言信息"""
    if not model_name:
        return ""
    
    # 匹配模型名称中的语言信息
    # 格式：xxx-语言-xxx、xxx-语言、xxx_zh、xxx_zh_test 等
    patterns = [
        r'-(中文|日语|英语|韩语|粤语)-',
        r'-(zh|ja|en|ko|yue)-',
        r'_([a-zA-Z]{2,3})(_|$)',  # 匹配 _ZH、_zh、_EN、_en 等后缀或后跟其他内容
        r'([a-zA-Z]{2,3})_',       # 匹配 各种语言代码后跟下划线的情况
    ]
    
    for pattern in patterns:
        match = re.search(pattern, model_name)
        if match:
            extracted = match.group(1) if len(match.groups()) >= 1 else match.group(0)
            if extracted in ["zh", "ja", "en", "ko", "yue", "ZH", "JA", "EN", "KO", "YUE"]:
                return extracted.lower()
            return LANG_MAPPING_REVERSE.get(extracted, extracted.lower())
    
    return ""


def safe_header_value(value: str) -> str:
    """
    将字符串转换为HTTP头安全的ASCII值
    移除或替换非ASCII字符
    """
    if not value:
        return ""
    
    # 尝试编码为ASCII，忽略无法编码的字符
    try:
        return value.encode('ascii', 'ignore').decode('ascii')
    except Exception:
        # 如果还是失败，使用更保守的方法
        safe_chars = []
        for char in value:
            if ord(char) < 128 and char.isprintable():
                safe_chars.append(char)
            else:
                safe_chars.append('_')  # 替换为下划线
        return ''.join(safe_chars)


def detect_text_language(text: str) -> str:
    """基于字符占比检测文本语言"""
    if not text:
        return ""
    
    # 移除空格和标点符号，只统计有效字符
    effective_text = re.sub(r'[\s\.,;:!?。，；：！？…\-\(\)（）\[\]【】""''`~@#$%^&*+=<>/\\|_]', '', text)
    total_chars = len(effective_text)
    
    if total_chars == 0:
        return ""
    
    # 统计不同语言字符的数量
    chinese_count = len(re.findall(r'[\u4e00-\u9fff]', effective_text))
    japanese_hiragana_count = len(re.findall(r'[\u3040-\u309f]', effective_text))  # 平假名
    japanese_katakana_count = len(re.findall(r'[\u30a0-\u30ff]', effective_text))  # 片假名
    korean_count = len(re.findall(r'[\uac00-\ud7af]', effective_text))
    english_count = len(re.findall(r'[a-zA-Z]', effective_text))
    
    # 日语特征：平假名或片假名
    japanese_kana_count = japanese_hiragana_count + japanese_katakana_count
    
    # 计算各语言字符占比
    chinese_ratio = chinese_count / total_chars
    japanese_ratio = japanese_kana_count / total_chars
    korean_ratio = korean_count / total_chars
    english_ratio = english_count / total_chars
    
    # 语言判断阈值
    DOMINANT_THRESHOLD = 0.3  # 主导语言阈值（30%以上）
    MINOR_THRESHOLD = 0.1     # 次要语言阈值（10%以上）
    
    # 构建语言占比字典
    language_ratios = {
        'zh': chinese_ratio,
        'ja': japanese_ratio,
        'ko': korean_ratio,
        'en': english_ratio
    }
    
    # 找出占比最高的语言
    max_lang = max(language_ratios, key=language_ratios.get)
    max_ratio = language_ratios[max_lang]
    
    # 调试信息（可选）
    if should_log('api_details'):
        ratios_str = ", ".join([f"{lang}: {ratio:.1%}" for lang, ratio in language_ratios.items() if ratio > 0])
        print(f"🔍 语言占比分析 - 文本: '{text[:20]}{'...' if len(text) > 20 else ''}' ({total_chars}字符), 占比: {ratios_str}")
        
        # 显示检测规则应用情况
        if japanese_ratio >= MINOR_THRESHOLD:
            print(f"📋 应用规则1: 日语假名占比 {japanese_ratio:.1%} >= {MINOR_THRESHOLD:.1%}，判断为日语")
        elif chinese_ratio >= MINOR_THRESHOLD and japanese_ratio == 0:
            print(f"📋 应用规则2: 中文占比 {chinese_ratio:.1%} >= {MINOR_THRESHOLD:.1%} 且无日语假名，判断为中文")
        elif korean_ratio >= MINOR_THRESHOLD:
            print(f"📋 应用规则3: 韩语占比 {korean_ratio:.1%} >= {MINOR_THRESHOLD:.1%}，判断为韩语")
        elif english_ratio >= DOMINANT_THRESHOLD:
            print(f"📋 应用规则4: 英语占比 {english_ratio:.1%} >= {DOMINANT_THRESHOLD:.1%}，判断为英语")
        elif max_ratio >= DOMINANT_THRESHOLD:
            print(f"📋 应用规则5: 最高占比语言 {max_lang} ({max_ratio:.1%}) >= {DOMINANT_THRESHOLD:.1%}")
        elif (chinese_ratio + japanese_ratio) >= DOMINANT_THRESHOLD and japanese_ratio == 0:
            print(f"📋 应用规则6: 中日文总占比 {(chinese_ratio + japanese_ratio):.1%} >= {DOMINANT_THRESHOLD:.1%} 且无假名，判断为中文")
        elif max_ratio > 0:
            print(f"📋 应用规则7: 使用最高占比语言 {max_lang} ({max_ratio:.1%})")
        else:
            print(f"📋 无法确定语言: 所有语言占比都为0")
    
    # 特殊规则优先判断
    
    # 1. 如果有日语假名且占比超过阈值，优先判断为日语
    if japanese_ratio >= MINOR_THRESHOLD:
        return 'ja'
    
    # 2. 如果有中文字符但没有日语假名，且中文占比足够，判断为中文
    if chinese_ratio >= MINOR_THRESHOLD and japanese_ratio == 0:
        return 'zh'
    
    # 3. 如果韩语字符占比超过阈值，判断为韩语
    if korean_ratio >= MINOR_THRESHOLD:
        return 'ko'
    
    # 4. 如果英语字符占比超过主导阈值，判断为英语
    if english_ratio >= DOMINANT_THRESHOLD:
        return 'en'
    
    # 5. 如果最高占比语言超过主导阈值，使用该语言
    if max_ratio >= DOMINANT_THRESHOLD:
        return max_lang
    
    # 6. 混合语言情况：如果中文+日语占比很高，但没有假名，判断为中文
    if (chinese_ratio + japanese_ratio) >= DOMINANT_THRESHOLD and japanese_ratio == 0:
        return 'zh'
    
    # 7. 如果所有语言占比都很低，返回占比最高的（如果有的话）
    if max_ratio > 0:
        return max_lang
    
    return ""


def validate_language_match(text: str, model_name: str) -> tuple[bool, str]:
    """
    验证文本语言与模型语言是否匹配
    
    Returns:
        (is_valid, warning_message)
    """
    if not model_name or not text:
        return True, ""
    
    model_lang = extract_language_from_model_name(model_name)
    if not model_lang:
        return True, ""  # 无法确定模型语言，跳过验证
    
    text_lang = detect_text_language(text)
    if not text_lang:
        return True, ""  # 无法确定文本语言，跳过验证
    
    # 语言匹配检查
    if model_lang != text_lang:
        warning = f"⚠️ 语言不匹配警告: 文本语言({text_lang}) 与模型语言({model_lang}) 不一致，可能影响合成质量"
        return False, warning
    
    return True, ""

def get_available_model_versions(model_name: str) -> list:
    """获取指定模型名称的所有可用版本"""
    available_versions = []
    
    for version in VERSION_PRIORITY:
        model_path = Path(f"models/{version}/{model_name}")
        if model_path.exists() and model_path.is_dir():
            # 检查是否有实际的模型文件（不只是.keep文件）
            files = list(model_path.rglob("*"))
            non_keep_files = [f for f in files if f.name != ".keep"]
            if non_keep_files:
                available_versions.append(version)
    
    return available_versions


def auto_select_best_version(model_name: str, preferred_version: str = "v4") -> str:
    """自动选择最佳的模型版本"""
    available_versions = get_available_model_versions(model_name)
    
    if not available_versions:
        if should_log('api_details'):
            print(f"⚠️ 模型 '{model_name}' 在任何版本中都不存在")
        return preferred_version  # 返回默认版本
    
    # 如果首选版本可用，使用首选版本
    if preferred_version in available_versions:
        if should_log('api_details'):
            print(f"✅ 使用首选版本 - 模型: {model_name}, 版本: {preferred_version}")
        return preferred_version
    
    # 否则使用最高优先级的可用版本
    best_version = available_versions[0]  # available_versions已按优先级排序
    if should_log('api_details'):
        print(f"🔄 版本自动选择 - 模型: {model_name}, 首选: {preferred_version} -> 实际: {best_version}")
    
    return best_version


def auto_get_all_parameters(model_name: str = "", emotion: str = "默认", version: str = "v4"):
    """自动获取所有缺失的参数：prompt_lang, ref_audio_path, prompt_text"""
    if model_name == "":
        return "", "", ""
    
    # 自动选择最佳版本
    best_version = auto_select_best_version(model_name, version)
    
    # 首先尝试从模型名称自动获取语言
    auto_prompt_lang = extract_language_from_model_name(model_name)
    
    if not auto_prompt_lang:
        version_paths = [f"models/{best_version}"] + [f"models/{v}" for v in VERSION_PRIORITY if v != best_version]
        for version_path in version_paths:
            model_path = Path(f"{version_path}/{model_name}")
            if model_path.exists():
                ref_audios_path = model_path / "reference_audios"
                if ref_audios_path.exists():
                    # 获取第一个可用的语言目录
                    lang_dirs = [d for d in ref_audios_path.iterdir() if d.is_dir()]
                    if lang_dirs:
                        first_lang_dir = lang_dirs[0].name
                        auto_prompt_lang = LANG_MAPPING_REVERSE.get(first_lang_dir, "zh")
                        break
    
    # 如果还是没找到语言，使用默认语言
    if not auto_prompt_lang:
        auto_prompt_lang = "zh"
    
    # 使用获取到的语言和最佳版本自动获取参考音频和文本
    ref_audio, prompt_text = auto_get_ref_audio_and_prompt_text(model_name, auto_prompt_lang, emotion, best_version)
    
    return auto_prompt_lang, ref_audio, prompt_text
#===============API配置管理和认证功能================

# 全局配置变量
API_CONFIG = {}
USAGE_STATS = defaultdict(list)
RATE_LIMIT = defaultdict(list)
PROCESSING_REQUESTS = {}  # 正在处理的请求（用于去重）

IP_REQUEST_LOG = defaultdict(list)
IP_TOKEN_LOG = defaultdict(list)
IP_BAN_LIST = {}

IP_DEFAULT_LIMITS = {
    "single_max_chars": 100,
    "minute_max_chars": 5000,
    "minute_max_requests": 80,
    "five_minute_max_requests": 400,
    "ban_duration": 300,
}

def get_ip_rate_limit_config(api_key: str = "") -> dict:
    key_info = API_CONFIG.get("api_keys", {}).get(api_key, {})
    mode = key_info.get("ip_rate_limit_mode", "global")

    if mode == "none":
        return None

    if mode == "custom":
        custom = key_info.get("ip_rate_limit", {})
        return {
            "single_max_chars": custom.get("single_max_chars", IP_DEFAULT_LIMITS["single_max_chars"]),
            "minute_max_chars": custom.get("minute_max_chars", IP_DEFAULT_LIMITS["minute_max_chars"]),
            "minute_max_requests": custom.get("minute_max_requests", IP_DEFAULT_LIMITS["minute_max_requests"]),
            "five_minute_max_requests": custom.get("five_minute_max_requests", IP_DEFAULT_LIMITS["five_minute_max_requests"]),
            "ban_duration": custom.get("ban_duration", IP_DEFAULT_LIMITS["ban_duration"]),
        }

    global_cfg = API_CONFIG.get("security", {}).get("ip_rate_limit", {})
    return {
        "single_max_chars": global_cfg.get("single_max_chars", IP_DEFAULT_LIMITS["single_max_chars"]),
        "minute_max_chars": global_cfg.get("minute_max_chars", IP_DEFAULT_LIMITS["minute_max_chars"]),
        "minute_max_requests": global_cfg.get("minute_max_requests", IP_DEFAULT_LIMITS["minute_max_requests"]),
        "five_minute_max_requests": global_cfg.get("five_minute_max_requests", IP_DEFAULT_LIMITS["five_minute_max_requests"]),
        "ban_duration": global_cfg.get("ban_duration", IP_DEFAULT_LIMITS["ban_duration"]),
    }

def is_ip_rate_limit_enabled() -> bool:
    return API_CONFIG.get("security", {}).get("ip_rate_limit", {}).get("enabled", True)

def count_cjk_chars(text: str) -> int:
    if not text:
        return 0
    cjk_pattern = re.compile(
        r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff'
        r'\u3000-\u303f\uff00-\uffef'
        r'\u2e80-\u2eff\u31c0-\u31ef\u3200-\u32ff'
        r'\u3300-\u33bf\ufe30-\ufe4f\uf900-\ufaff'
        r'\u2f800-\u2fa1f]'
    )
    return len(cjk_pattern.findall(text))

def check_ip_rate_limit(client_ip: str, text: str, limits: dict = None) -> tuple:

    if not is_ip_rate_limit_enabled():
        return True, ""

    if limits is None:
        limits = get_ip_rate_limit_config("")

    if limits is None:
        return True, ""

    single_max_chars = limits.get("single_max_chars", 100)
    minute_max_chars = limits.get("minute_max_chars", 5000)
    minute_max_requests = limits.get("minute_max_requests", 80)
    five_minute_max_requests = limits.get("five_minute_max_requests", 400)
    ban_duration = limits.get("ban_duration", 300)

    now = time.time()

    if client_ip in IP_BAN_LIST:
        ban_until = IP_BAN_LIST[client_ip]
        if now < ban_until:
            remaining = int(ban_until - now)
            return False, f"IP banned, remaining {remaining}s"
        del IP_BAN_LIST[client_ip]

    cjk_count = count_cjk_chars(text)

    if cjk_count > single_max_chars:
        IP_BAN_LIST[client_ip] = now + ban_duration
        print(f"\U0001f6ab IP封禁(单次超限) - IP: {client_ip}, 字符数: {cjk_count}, 阈值: {single_max_chars}")
        return False, f"Single request exceeds {single_max_chars} chars"

    IP_REQUEST_LOG[client_ip].append(now)
    IP_TOKEN_LOG[client_ip].append((now, cjk_count))

    cutoff_1m = now - 60
    cutoff_5m = now - 300

    IP_REQUEST_LOG[client_ip] = [
        t for t in IP_REQUEST_LOG[client_ip] if t > cutoff_5m
    ]
    IP_TOKEN_LOG[client_ip] = [
        (t, c) for t, c in IP_TOKEN_LOG[client_ip] if t > max(cutoff_1m, cutoff_5m)
    ]

    requests_1m = sum(1 for t in IP_REQUEST_LOG[client_ip] if t > cutoff_1m)
    requests_5m = len(IP_REQUEST_LOG[client_ip])
    tokens_1m = sum(c for t, c in IP_TOKEN_LOG[client_ip] if t > cutoff_1m)

    if requests_1m > minute_max_requests:
        IP_BAN_LIST[client_ip] = now + ban_duration
        print(f"\U0001f6ab IP封禁(1分钟请求超限) - IP: {client_ip}, 请求数: {requests_1m}, 阈值: {minute_max_requests}")
        return False, f"Too many requests per minute"

    if requests_5m > five_minute_max_requests:
        IP_BAN_LIST[client_ip] = now + ban_duration
        print(f"\U0001f6ab IP封禁(5分钟请求超限) - IP: {client_ip}, 请求数: {requests_5m}, 阈值: {five_minute_max_requests}")
        return False, f"Too many requests per 5 minutes"

    if tokens_1m > minute_max_chars:
        IP_BAN_LIST[client_ip] = now + ban_duration
        print(f"\U0001f6ab IP封禁(每分钟token超限) - IP: {client_ip}, token数: {tokens_1m}, 阈值: {minute_max_chars}")
        return False, f"Too many tokens per minute"

    return True, ""

def check_ip_ban(client_ip: str) -> bool:
    if client_ip in IP_BAN_LIST:
        if time.time() < IP_BAN_LIST[client_ip]:
            return True
        del IP_BAN_LIST[client_ip]
    return False

def load_api_config():
    """加载API配置文件"""
    global API_CONFIG
    try:
        with open('api_config.yaml', 'r', encoding='utf-8') as f:
            API_CONFIG = yaml.safe_load(f)
        print("✅ API配置加载成功")
        return True
    except FileNotFoundError:
        print("⚠️ 未找到api_config.yaml文件，使用默认配置")
        API_CONFIG = {
            'api_keys': {},
            'default_models': {
                'fallback_model': '蔚蓝档案-中文-心奈',
                'language_defaults': {
                    'zh': '蔚蓝档案-中文-心奈',
                    'ja': '蔚蓝档案-日语-伊吹',
                    'en': '蔚蓝档案-英语-test',
                    'ko': '蔚蓝档案-韩语-test',
                    'yue': '蔚蓝档案-粤语-test'
                }
            },
            'permissions': {
                'require_api_key': True,
                'allow_no_model_name': True,
                'strict_model_access': False
            },
            'statistics': {
                'enable_stats': True,
                'storage_type': 'memory'
            },
            'security': {
                'rate_limit_per_minute': 60,
                'log_requests': True,
                'blocked_models': [],
                'ip_rate_limit': {
                    'enabled': True,
                    'single_max_chars': 100,
                    'minute_max_chars': 5000,
                    'minute_max_requests': 80,
                    'five_minute_max_requests': 400,
                    'ban_duration': 300
                }
            },
            'logging': {
                'enable_logging': True,
                'log_level': 'info',
                'log_url_requests': True,
                'log_tts_synthesis': True,
                'log_api_details': True,
                'log_request_status': True
            }
        }
        return False
    except Exception as e:
        print(f"❌ 加载API配置失败: {e}")
        return False

def authenticate_api_key(api_key: str) -> dict:
    """API Key认证"""
    # 如果配置要求API密钥认证
    if API_CONFIG.get('permissions', {}).get('require_api_key', False):
        # 检查是否提供了API密钥
        if not api_key or api_key.strip() == "":
            return {'valid': False, 'error': 'API key is required'}
        
        # 检查API密钥配置是否存在
        if not API_CONFIG.get('api_keys', {}):
            return {'valid': False, 'error': 'API key authentication is required but no keys are configured'}
        
        # 验证提供的API密钥
        key_info = API_CONFIG['api_keys'].get(api_key)
        if not key_info:
            return {'valid': False, 'error': 'Invalid API key'}
        
        if not key_info.get('enabled', True):
            return {'valid': False, 'error': 'API key is disabled'}
        
        return {
            'valid': True,
            'key': api_key,
            'models': key_info.get('models', ['*']),
            'daily_limit': key_info.get('daily_limit', 100)
        }
    else:
        # 如果不要求API密钥认证，返回默认的有效状态
        if not API_CONFIG.get('api_keys', {}):
            return {'valid': True, 'key': 'default', 'models': ['*'], 'daily_limit': 1000}
        
        # 如果有API密钥配置但用户没提供，返回无效状态
        if not api_key or api_key.strip() == "":
            return {'valid': True, 'key': 'anonymous', 'models': ['*'], 'daily_limit': 1000}
        
        # 验证提供的API密钥
        key_info = API_CONFIG['api_keys'].get(api_key)
        if not key_info:
            return {'valid': False, 'error': 'Invalid API key'}
        
        if not key_info.get('enabled', True):
            return {'valid': False, 'error': 'API key is disabled'}
        
        return {
            'valid': True,
            'key': api_key,
            'models': key_info.get('models', ['*']),
            'daily_limit': key_info.get('daily_limit', 100)
        }

def check_model_access(user_models: list, requested_model: str) -> bool:
    """检查用户是否有权限访问指定模型"""
    if '*' in user_models:
        return True
    
    # 检查是否在禁止列表中
    if requested_model in API_CONFIG.get('security', {}).get('blocked_models', []):
        return False
    
    return requested_model in user_models

def check_rate_limit(api_key: str) -> bool:
    """检查请求频率限制"""
    if not API_CONFIG.get('security', {}).get('rate_limit_per_minute'):
        return True
    
    now = datetime.now()
    minute_ago = now - timedelta(minutes=1)
    
    # 清理过期的记录
    RATE_LIMIT[api_key] = [
        timestamp for timestamp in RATE_LIMIT[api_key] 
        if timestamp > minute_ago
    ]
    
    # 检查是否超过限制
    limit = API_CONFIG['security']['rate_limit_per_minute']
    if len(RATE_LIMIT[api_key]) >= limit:
        return False
    
    # 记录本次请求
    RATE_LIMIT[api_key].append(now)
    return True

def update_usage_stats(api_key: str, model_name: str, success: bool = True):
    """更新使用统计"""
    if not API_CONFIG.get('statistics', {}).get('enable_stats', True):
        return
    
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    USAGE_STATS[api_key].append({
        'timestamp': now,
        'model': model_name,
        'success': success
    })

def get_default_model(text_lang: str = "") -> str:
    """获取默认模型"""
    # 按语言获取默认模型
    if text_lang and text_lang in API_CONFIG.get('default_models', {}).get('language_defaults', {}):
        return API_CONFIG['default_models']['language_defaults'][text_lang]
    
    # 返回全局默认模型
    return API_CONFIG.get('default_models', {}).get('fallback_model', '蔚蓝档案-中文-心奈')

def should_log(log_type: str) -> bool:
    """检查是否应该打印指定类型的日志"""
    logging_config = API_CONFIG.get('logging', {})
    
    # 如果日志功能被禁用，不打印任何日志
    if not logging_config.get('enable_logging', True):
        return False
    
    # 根据日志类型检查配置
    if log_type == 'url_requests':
        return logging_config.get('log_url_requests', True)
    elif log_type == 'tts_synthesis':
        return logging_config.get('log_tts_synthesis', True)
    elif log_type == 'api_details':
        return logging_config.get('log_api_details', True)
    elif log_type == 'request_status':
        return logging_config.get('log_request_status', True)
    
    # 默认打印
    return True

def get_model_for_user(api_key: str, text_lang: str, model_name: str = "", text: str = "") -> tuple[str, dict, str]:
    """
    为用户获取合适的模型，返回(最终模型名, 重定向信息, 检测到的语言)
    
    Args:
        api_key: 用户API密钥
        text_lang: 文本语言（可能是"auto"）
        model_name: 指定的模型名（可能为空）
        text: 要合成的文本（用于自动语言检测）
    
    Returns:
        tuple: (final_model_name, redirect_info, detected_lang)
            - final_model_name: 最终使用的模型名
            - redirect_info: 重定向信息字典，包含是否被重定向和原因
            - detected_lang: 检测到的语言（如果进行了自动检测）
    """
    redirect_info = {
        "redirected": False,
        "original_model": model_name,
        "final_model": "",
        "reason": ""
    }
    
    detected_lang = text_lang  # 默认使用原始语言
    
    # 如果 text_lang 是 "auto"，先检测文本语言
    if text_lang == "auto" and text:
        if should_log('api_details'):
            print(f"🔍 启动自动语言检测 - 文本: '{text[:30]}{'...' if len(text) > 30 else ''}'")
        
        detected_lang = detect_text_language(text)
        if detected_lang:
            text_lang = detected_lang
            if should_log('api_details'):
                print(f"✅ 自动语言检测完成 - 检测结果: {detected_lang}")
        else:
            if should_log('api_details'):
                print(f"⚠️ 自动语言检测失败 - 无法确定语言，使用默认语言: zh")
            text_lang = "zh"  # 默认使用中文
            detected_lang = "zh"
    
    # 如果没有指定模型，使用默认模型
    if not model_name:
        final_model = get_default_model(text_lang)
        redirect_info["final_model"] = final_model
        if should_log('api_details'):
            print(f"📋 使用默认模型 - 语言: {text_lang}, 模型: {final_model}")
        return final_model, redirect_info, detected_lang
    
    # 检查用户权限
    if API_CONFIG.get('permissions', {}).get('strict_model_access', False):
        key_info = authenticate_api_key(api_key)
        if key_info['valid'] and not check_model_access(key_info['models'], model_name):
            final_model = get_default_model(text_lang)
            redirect_info.update({
                "redirected": True,
                "final_model": final_model,
                "reason": f"模型 '{model_name}' 不在用户 {api_key[:8]}... 的授权列表中，已重定向到默认模型 '{final_model}'"
            })
            
            # 记录重定向日志
            if API_CONFIG.get('security', {}).get('log_requests', True) and should_log('api_details'):
                print(f"⚠️ 模型重定向 - Key: {api_key[:8]}..., 请求模型: {model_name}, 重定向到: {final_model}")
            
            return final_model, redirect_info, detected_lang
    
    # 用户有权限访问指定模型
    redirect_info["final_model"] = model_name
    return model_name, redirect_info, detected_lang

parser = argparse.ArgumentParser(description="GPT-SoVITS api")
parser.add_argument("-c", "--tts_config", type=str, default="GPT_SoVITS/configs/tts_infer.yaml", help="tts_infer路径")
parser.add_argument("-a", "--bind_addr", type=str, default="0.0.0.0", help="default: 0.0.0.0")
parser.add_argument("-p", "--port", type=int, default="9880", help="default: 9880")
args = parser.parse_args()
config_path = args.tts_config
# device = args.device
port = args.port
host = args.bind_addr
argv = sys.argv

if config_path in [None, ""]:
    config_path = "GPT-SoVITS/configs/tts_infer.yaml"

# 加载API配置文件
load_api_config()

# 导入 api_v2 模块（这会初始化 TTS）
print("=" * 80)
print("🚀 正在启动 GPT-SoVITS API Server")
print("=" * 80)
print(f"📁 配置文件: {config_path}")
print(f"🌐 绑定地址: {host}:{port}")
print(f"📊 统计功能: {'启用' if API_CONFIG.get('statistics', {}).get('enable_stats', True) else '禁用'}")
print(f"🔐 认证功能: {'启用' if API_CONFIG.get('permissions', {}).get('require_api_key', False) else '禁用'}")
print("=" * 80)
print()

# 记录服务启动事件
try:
    from api_stats import get_stats_manager
    stats_manager_init = get_stats_manager()
    stats_manager_init.log_system_event(
        event_type="server_start",
        event_name="API服务启动",
        details=f"配置文件: {config_path}, 端口: {port}",
        status="success"
    )
except Exception as e:
    print(f"⚠️ 无法记录启动事件: {e}")

# 使用 api_v2 的 TTS 配置和 Pipeline，避免重复初始化
print("📦 复用 api_v2 的 TTS 实例...")
tts_config = api_v2.tts_config
tts_pipeline = api_v2.tts_pipeline
print("✅ TTS 实例加载完成")
print()

try:
    stats_manager_init.log_system_event(
        event_type="model_load",
        event_name="TTS配置加载",
        details=f"版本: {tts_config.version}",
        status="success"
    )
except Exception:
    pass

APP = FastAPI()

# 安全中间件：检测和阻止恶意请求
@APP.middleware("http")
async def security_middleware(request: Request, call_next):
    """安全中间件：检测恶意请求并记录"""
    stats_manager = get_stats_manager()
    client_ip = get_real_ip(request)
    path = request.url.path

    if check_ip_ban(client_ip):
        return JSONResponse(
            status_code=429,
            content={"message": "IP is banned due to rate limit violation"}
        )

    # 获取白名单配置
    whitelist_paths = API_CONFIG.get('security_features', {}).get('whitelist_paths', [
        '/tts', '/stats', '/security', '/control', 
        '/set_gpt_weights', '/set_sovits_weights', '/set_refer_audio'
    ])
    
    # 白名单检查：跳过核心API路径的安全检测
    for whitelist_path in whitelist_paths:
        if path.startswith(whitelist_path):
            # 仍然检查IP黑名单
            if stats_manager.is_ip_blacklisted(client_ip):
                print(f"🚫 IP黑名单拦截 - IP: {client_ip}, 路径: {path}")
                return JSONResponse(
                    status_code=403,
                    content={"message": "Hacker", "error": "Access denied"}
                )
            # 跳过恶意检测，直接处理请求
            response = await call_next(request)
            return response
    
    # 检查IP是否在黑名单中
    if stats_manager.is_ip_blacklisted(client_ip):
        return JSONResponse(
            status_code=403,
            content={"message": "Hacker", "error": "Access denied"}
        )
    
    # 获取请求信息
    query_string = request.url.query or ""
    method = request.method
    user_agent = request.headers.get("user-agent", "unknown")
    full_url = str(request.url)
    
    # 尝试读取请求体（仅用于检测，不影响后续处理）
    request_body = ""
    try:
        if method in ["POST", "PUT", "PATCH"]:
            body = await request.body()
            request_body = body.decode('utf-8', errors='ignore')[:500]  # 限制长度
    except Exception:
        pass
    
    # 检测恶意请求（使用security_manager中的方法）
    from api_stats.security_manager import get_security_manager
    security_manager = get_security_manager()
    is_malicious, threat_type, threat_details = security_manager.detect_malicious_request(
        path, query_string, request_body
    )
    
    if is_malicious:
        # 记录恶意请求
        stats_manager.log_malicious_request(
            client_ip=client_ip,
            method=method,
            path=path,
            query_string=query_string,
            user_agent=user_agent,
            threat_type=threat_type,
            threat_details=threat_details,
            full_url=full_url,
            request_body=request_body
        )
        
        # 打印警告日志
        print(f"🚨 恶意请求已阻止 - IP: {client_ip}, 威胁类型: {threat_type}, 路径: {path}, 详情: {threat_details}")
        
        # 返回Hacker响应
        return JSONResponse(
            status_code=403,
            content={"message": "Hacker", "error": "Malicious request detected"}
        )
    
    # 继续处理正常请求
    response = await call_next(request)
    return response

# 注册统计WebUI路由（包含安全日志）
register_stats_routes(APP)


class TTS_Request(BaseModel):
    text: str = None
    text_lang: str = None  # 不提供默认值，在处理时自动设置为 "auto"
    ref_audio_path: str = None
    aux_ref_audio_paths: list = None
    prompt_lang: str = None
    prompt_text: str = ""
    top_k: int = 15
    top_p: float = 1
    temperature: float = 1
    text_split_method: str = "cut5"
    batch_size: int = 1
    batch_threshold: float = 0.75
    split_bucket: bool = True
    speed_factor: float = 1.0
    fragment_interval: float = 0.3
    seed: int = -1
    media_type: str = "wav"
    streaming_mode: Union[bool, int] = False  # 支持 0/1/2/3 或 True/False
    parallel_infer: bool = True
    repetition_penalty: float = 1.35
    sample_steps: int = 32
    super_sampling: bool = False
    overlap_length: int = 2  # 流式模式下语义token的重叠长度
    min_chunk_length: int = 16  # 流式模式下语义token的最小块长度
    # 自动获取相关字段
    model_name: str = ""
    emotion: str = "默认"
    version: str = "v4"
    # 企业级功能字段
    api_key: str = ""


# 音频处理函数使用 api_v2 模块的实现


def get_real_ip(request: Request) -> str:
    """获取真实IP地址"""
    if "x-forwarded-for" in request.headers:
        # 当有多级代理时，x-forwarded-for 的值是 "client, proxy1, proxy2"，取第一个
        return request.headers["x-forwarded-for"].split(",")[0].strip()
    if "x-real-ip" in request.headers:
        return request.headers["x-real-ip"]
    return request.client.host


def extract_prompt_text_from_filename(ref_audio_path: str) -> str:
    """从参考音频文件名中提取prompt_text，文件名格式： 【情感】文本.wav"""
    try:
        file_name = Path(ref_audio_path).stem  # 获取不含扩展名的文件名
        # 使用正则表达式提取【】中的内容
        if "【" in file_name and "】" in file_name:
            # 查找最后一个】之后的内容作为prompt_text
            last_bracket = file_name.rfind("】")
            if last_bracket != -1 and last_bracket < len(file_name) - 1:
                prompt_text = file_name[last_bracket + 1:]
                return prompt_text
        return ""
    except Exception:
        return ""

# 参数验证函数 - 扩展版（支持企业级功能）
def check_params_extended(req: dict):
    """
    扩展的参数验证，支持 api_server 的企业级功能
    在调用 api_v2.check_params 前进行预处理
    """
    text: str = req.get("text", "")
    text_lang: str = req.get("text_lang", "")
    ref_audio_path: str = req.get("ref_audio_path", "")
    model_name: str = req.get("model_name", "")
    prompt_lang: str = req.get("prompt_lang", "")

    if text in [None, ""]:
        return JSONResponse(status_code=400, content={"message": "text is required"})
    
    # 如果没有提供 text_lang，自动使用智能语言识别模式
    if text_lang in [None, ""]:
        text_lang = "auto"
        req["text_lang"] = "auto"
    
    # 验证 text_lang（"auto" 是特殊值，无需验证）
    if text_lang.lower() != "auto" and text_lang.lower() not in tts_config.languages:
        return JSONResponse(
            status_code=400,
            content={"message": f"text_lang: {text_lang} is not supported in version {tts_config.version}. Use 'auto' for automatic detection or one of: {', '.join(tts_config.languages)}"},
        )
    
    # 如果提供了 model_name，允许在没有 ref_audio_path 的情况下继续
    if ref_audio_path in [None, ""] and model_name == "":
        return JSONResponse(status_code=400, content={"message": "Either ref_audio_path or model_name is required"})
    
    # prompt_lang 验证 - 修复 NoneType 错误
    if model_name != "" and prompt_lang == "":
        pass  # 会在后续自动获取
    elif ref_audio_path not in [None, ""] and prompt_lang == "":
        pass  # 可以从文件名提取
    elif prompt_lang and prompt_lang != "" and prompt_lang.lower() not in tts_config.languages:
        return JSONResponse(
            status_code=400,
            content={"message": f"prompt_lang: {prompt_lang} is not supported in version {tts_config.version}"},
        )
    elif model_name == "" and ref_audio_path in [None, ""] and prompt_lang == "":
        return JSONResponse(status_code=400, content={"message": "prompt_lang is required when neither ref_audio_path nor model_name is provided"})
    
    return None


async def tts_handle(req: dict):
    """
    Text to speech handler with enterprise features.

    Args:
        req (dict):
            {
                "text": "",                   # str.(required) text to be synthesized
                "text_lang: "",               # str.(required) language of the text to be synthesized
                "ref_audio_path": "",         # str.(optional) reference audio path
                "aux_ref_audio_paths": [],    # list.(optional) auxiliary reference audio paths for multi-speaker synthesis
                "prompt_text": "",            # str.(optional) prompt text for the reference audio (auto extracted from ref_audio_path filename)
                "prompt_lang": "",            # str.(required) language of the prompt text for the reference audio
                "top_k": 15,                  # int. top k sampling
                "top_p": 1,                   # float. top p sampling
                "temperature": 1,             # float. temperature for sampling
                "text_split_method": "cut5",  # str. text split method, see text_segmentation_method.py for details.
                "batch_size": 1,              # int. batch size for inference
                "batch_threshold": 0.75,      # float. threshold for batch splitting.
                "split_bucket: True,          # bool. whether to split the batch into multiple buckets.
                "speed_factor":1.0,           # float. control the speed of the synthesized audio.
                "fragment_interval":0.3,      # float. to control the interval of the audio fragment.
                "seed": -1,                   # int. random seed for reproducibility.
                "media_type": "wav",          # str. media type of the output audio, support "wav", "raw", "ogg", "aac".
                "streaming_mode": False,      # bool. whether to return a streaming response.
                "parallel_infer": True,       # bool.(optional) whether to use parallel inference.
                "repetition_penalty": 1.35    # float.(optional) repetition penalty for T2S model.
                "sample_steps": 32,           # int. number of sampling steps for VITS model V3.
                "super_sampling": False,       # bool. whether to use super-sampling for audio when using VITS model V3.
                "model_name": "",             # str.(optional) model name for auto getting ref_audio and prompt_text
                "emotion": "默认",             # str.(optional) emotion for auto getting
                "version": "v4",              # str.(optional) model version
                "api_key": "",                # str.(optional) API Key for authentication
            }
    returns:
        StreamingResponse: audio stream response.
    """
    
    # 记录开始时间用于统计
    start_time = time.time()
    stats_manager = get_stats_manager()
    
    # 调试日志
    request_id = req.get("request_id", "unknown")
    if should_log('request_status'):
        print(f"🔶 tts_handle 函数被调用 - ID: {request_id[:8] if len(request_id) > 8 else request_id}..., Text: {req.get('text', '')[:30]}...")
    
    # 检查是否正在处理相同的请求（防止浏览器重复提交）
    if request_id in PROCESSING_REQUESTS:
        wait_time = time.time() - PROCESSING_REQUESTS[request_id]
        if should_log('request_status'):
            print(f"⚠️ 检测到重复请求 - ID: {request_id[:8]}..., 已等待 {wait_time:.1f}秒")
        return JSONResponse(
            status_code=409,
            content={
                "message": "Request is already being processed",
                "request_id": request_id,
                "wait_time": f"{wait_time:.1f}s",
                "tip": "请等待当前请求完成，不要重复提交"
            }
        )
    
    # 标记请求正在处理
    PROCESSING_REQUESTS[request_id] = time.time()

    client_ip = req.get("client_ip", "unknown")

    is_banned = check_ip_ban(client_ip)
    if is_banned:
        return JSONResponse(
            status_code=429,
            content={"message": "IP is banned due to rate limit violation"}
        )

    api_key_early = req.get("api_key", "")
    ip_limits = get_ip_rate_limit_config(api_key_early)

    allowed, limit_reason = check_ip_rate_limit(client_ip, req.get("text", ""), ip_limits)
    if not allowed:
        return JSONResponse(
            status_code=429,
            content={"message": limit_reason}
        )

    # ========== 企业级功能集成 ==========
    
    # 1. API Key认证
    api_key = req.get("api_key", "")
    user_info = authenticate_api_key(api_key)
    
    if not user_info['valid']:
        error_message = user_info.get('error', 'Authentication failed')
        text = req.get("text", "")
        text_preview = text[:100] if len(text) > 100 else text
        text_full = text
        
        # 记录失败的认证尝试
        stats_manager.record_request(
            api_key=api_key or "anonymous",
            model_name=req.get("model_name", ""),
            text_length=len(text),
            processing_time=time.time() - start_time,
            success=False,
            error_message=error_message,
            client_ip=req.get("client_ip", "unknown"),
            text_lang=req.get("text_lang", ""),
            media_type=req.get("media_type", "wav"),
            text_preview=text_preview,
            text_full=text_full,
            ref_audio_path=req.get("ref_audio_path", ""),
            prompt_text=req.get("prompt_text", "")
        )
        return JSONResponse(status_code=401, content={"message": error_message})
    
    # 2. 速率限制检查
    if not check_rate_limit(user_info['key']):
        text = req.get("text", "")
        text_preview = text[:100] if len(text) > 100 else text
        text_full = text
        
        # 记录被限流的请求
        stats_manager.record_request(
            api_key=user_info['key'],
            model_name=req.get("model_name", ""),
            text_length=len(text),
            processing_time=time.time() - start_time,
            success=False,
            error_message="Rate limit exceeded",
            client_ip=req.get("client_ip", "unknown"),
            text_lang=req.get("text_lang", ""),
            media_type=req.get("media_type", "wav"),
            text_preview=text_preview,
            text_full=text_full,
            ref_audio_path=req.get("ref_audio_path", ""),
            prompt_text=req.get("prompt_text", "")
        )
        return JSONResponse(status_code=429, content={"message": "Rate limit exceeded"})
    

    # 3. 模型权限检查和获取
    model_name = req.get("model_name", "")
    text_lang = req.get("text_lang", "")
    original_text_lang = text_lang  # 保存用户原始传入的语言参数
    text = req.get("text", "")

    # 获取用户可访问的模型
    final_model_name, redirect_info, detected_lang = get_model_for_user(user_info['key'], text_lang, model_name, text)
    
    # 如果语言检测发生了变化，更新请求中的 text_lang
    if detected_lang != req.get("text_lang", ""):
        req["text_lang"] = detected_lang
        text_lang = detected_lang
        if should_log('api_details'):
            print(f"📝 更新请求语言 - 原始: {req.get('text_lang', '')}, 检测后: {detected_lang}")
    
    # 4. 验证文本语言与模型语言是否匹配，并自动修正（仅在 auto 模式下生效）
    if original_text_lang in ("auto", ""):
        is_match, warning_msg = validate_language_match(text, final_model_name)
        if not is_match:
            if should_log('api_details'):
                print(warning_msg)

            # 检测文本语言并尝试重定向到合适的模型
            detected_lang = detect_text_language(text)
            if detected_lang and detected_lang != text_lang:
                # 更新 text_lang 为检测到的语言
                text_lang = detected_lang
                req["text_lang"] = detected_lang

                # 尝试获取该语言的默认模型
                suggested_model = get_default_model(detected_lang)

                # 检查用户是否有权限访问建议的模型
                if check_model_access(user_info.get('models', ['*']), suggested_model):
                    if should_log('api_details'):
                        print(f"🔄 自动语言修正 - 检测到文本语言: {detected_lang}, 重定向模型: {final_model_name} -> {suggested_model}")

                    final_model_name = suggested_model
                    req["model_name"] = suggested_model

                    # 更新重定向信息
                    redirect_info.update({
                        "redirected": True,
                        "original_model": model_name,
                        "final_model": suggested_model,
                        "reason": f"检测到文本语言({detected_lang})与原模型语言不匹配，已自动重定向到合适的{detected_lang}模型"
                    })
                else:
                    if should_log('api_details'):
                        print(f"⚠️ 无法自动修正 - 用户无权限访问建议的{detected_lang}模型: {suggested_model}")
            else:
                if should_log('api_details'):
                    print("⚠️ 无法自动修正语言不匹配 - 继续使用原模型，可能影响合成质量")
    
    # 如果模型发生了变更，记录到req中
    if final_model_name != model_name:
        req["model_name"] = final_model_name
        model_name = final_model_name
    
    # ========== 自动获取参数 ==========
    
    emotion = req.get("emotion", "默认")
    version = req.get("version", "v4")
    ref_audio_path = req.get("ref_audio_path", "")
    prompt_lang = req.get("prompt_lang", "")
    media_type = req.get("media_type", "wav")
    streaming_mode = req.get("streaming_mode", False)
    return_fragment = req.get("return_fragment", False)
    fixed_length_chunk = False
    
    # 处理 streaming_mode 的多种模式 (0/1/2/3 或 True/False)
    if streaming_mode == 0 or streaming_mode is False:
        streaming_mode = False
        return_fragment = False
        fixed_length_chunk = False
    elif streaming_mode == 1 or streaming_mode is True:
        streaming_mode = False
        return_fragment = True
        fixed_length_chunk = False
    elif streaming_mode == 2:
        streaming_mode = True
        return_fragment = False
        fixed_length_chunk = False
    elif streaming_mode == 3:
        streaming_mode = True
        return_fragment = False
        fixed_length_chunk = True
    
    req["streaming_mode"] = streaming_mode
    req["return_fragment"] = return_fragment
    req["fixed_length_chunk"] = fixed_length_chunk

    # 如果没有提供 ref_audio_path，尝试完全自动获取所有参数
    if ref_audio_path in [None, ""] and model_name != "":
        auto_prompt_lang, auto_ref_audio, auto_prompt_text = auto_get_all_parameters(model_name, emotion, version)
        if auto_ref_audio != "":
            ref_audio_path = auto_ref_audio
            prompt_lang = auto_prompt_lang
            req["ref_audio_path"] = ref_audio_path
            req["prompt_lang"] = prompt_lang
            req["prompt_text"] = auto_prompt_text

    # 如果只提供了 ref_audio_path，自动从文件名提取 prompt_text
    elif ref_audio_path not in [None, ""]:
        extracted_prompt_text = extract_prompt_text_from_filename(ref_audio_path)
        if extracted_prompt_text != "":
            req["prompt_text"] = extracted_prompt_text
    
    # 使用扩展的参数验证
    check_res = check_params_extended(req)
    if check_res is not None:
        text = req.get("text", "")
        text_preview = text[:100] if len(text) > 100 else text
        text_full = text
        
        # 记录参数验证失败
        stats_manager.record_request(
            api_key=user_info['key'],
            model_name=model_name,
            text_length=len(text),
            processing_time=time.time() - start_time,
            success=False,
            error_message="Parameter validation failed",
            client_ip=req.get("client_ip", "unknown"),
            text_lang=req.get("text_lang", ""),
            media_type=media_type,
            text_preview=text_preview,
            text_full=text_full,
            ref_audio_path=req.get("ref_audio_path", ""),
            prompt_text=req.get("prompt_text", "")
        )
        
        # 如果是重定向情况且参数验证失败，仍然需要添加重定向头信息
        if redirect_info["redirected"]:
            # 获取原始响应的内容和状态码
            status_code = check_res.status_code
            response_body = check_res.body.decode('utf-8') if isinstance(check_res.body, bytes) else str(check_res.body)
            
            # 创建带有重定向头的新Response对象（使用ASCII安全编码）
            headers = {
                "X-Model-Redirected": "true",
                "X-Original-Model": "unauthorized_model",
                "X-Final-Model": safe_header_value(redirect_info["final_model"]),
                "X-Redirect-Reason": "model_not_authorized"
            }
            
            return Response(
                content=response_body,
                status_code=status_code,
                headers=headers,
                media_type="application/json"
            )
        
        return check_res

    # 更新 streaming_mode 状态用于后续判断
    streaming_mode = streaming_mode or return_fragment

    try:
        # 4. 记录请求日志
        if API_CONFIG.get('security', {}).get('log_requests', True) and should_log('api_details'):
            client_ip = req.get("client_ip", "unknown")
            print(f"📊 API调用 - IP: {client_ip}, Key: {user_info['key'][:8]}..., Model: {model_name}, Text: {req.get('text', '')[:20]}...")
        
        # 5. 执行TTS推理 - 调用 api_v2 的核心处理逻辑
        tts_start_time = time.time()
        if should_log('tts_synthesis'):
            print(f"🎤 开始TTS合成 - Model: {model_name}, Text长度: {len(req.get('text', ''))}字符")
        
        # 调用 api_v2.tts_handle 进行实际的 TTS 处理
        response = await api_v2.tts_handle(req)

        # 检查 api_v2 是否返回了错误（静默捕获的异常）
        if isinstance(response, JSONResponse) and response.status_code >= 400:
            import json
            body = json.loads(response.body.decode())
            print(f"❌ TTS合成失败 - {body}")
            print(f"❌ 请求文本: {req.get('text', '')[:100]}")
            print(f"❌ 语言: {req.get('text_lang', '')}, 切分方法: {req.get('text_split_method', '')}")
        
        # 添加企业级功能的响应头
        if redirect_info["redirected"]:
            # 为响应添加重定向信息头（使用ASCII安全的编码）
            if isinstance(response, StreamingResponse):
                response.headers["X-Model-Redirected"] = "true"
                response.headers["X-Original-Model"] = safe_header_value(redirect_info["original_model"])
                response.headers["X-Final-Model"] = safe_header_value(redirect_info["final_model"])
                response.headers["X-Redirect-Reason"] = "language_mismatch_auto_corrected"
            elif isinstance(response, Response):
                response.headers["X-Model-Redirected"] = "true"
                response.headers["X-Original-Model"] = safe_header_value(redirect_info["original_model"])
                response.headers["X-Final-Model"] = safe_header_value(redirect_info["final_model"])
                response.headers["X-Redirect-Reason"] = "language_mismatch_auto_corrected"
        
        # 6. 记录成功的请求统计（在完成所有处理后记录）
        tts_time = time.time() - tts_start_time
        total_time = time.time() - start_time
        text = req.get("text", "")
        text_preview = text[:100] if len(text) > 100 else text
        text_full = text
        
        stats_manager.record_request(
            api_key=user_info['key'],
            model_name=model_name,
            text_length=len(text),
            processing_time=total_time,
            success=True,
            error_message=None,
            client_ip=req.get("client_ip", "unknown"),
            text_lang=req.get("text_lang", ""),
            media_type=media_type,
            text_preview=text_preview,
            text_full=text_full,
            tts_time=tts_time,
            ref_audio_path=req.get("ref_audio_path", ""),
            prompt_text=req.get("prompt_text", "")
        )
        
        if should_log('tts_synthesis'):
            print(f"⏱️  处理时间 - 总计: {total_time:.2f}秒, TTS合成: {tts_time:.2f}秒")
        
        # 清理处理标记
        if request_id in PROCESSING_REQUESTS:
            del PROCESSING_REQUESTS[request_id]
            if should_log('request_status'):
                print(f"✅ 请求处理完成 - ID: {request_id[:8]}...")
        
        return response
        
    except Exception as e:
        # 8. 记录失败的请求统计
        processing_time = time.time() - start_time
        text = req.get("text", "")
        text_preview = text[:100] if len(text) > 100 else text
        text_full = text  # 保存完整文本
        
        stats_manager.record_request(
            api_key=user_info['key'],
            model_name=model_name,
            text_length=len(text),
            processing_time=processing_time,
            success=False,
            error_message=str(e),
            client_ip=req.get("client_ip", "unknown"),
            text_lang=req.get("text_lang", ""),
            media_type=media_type,
            text_preview=text_preview,
            text_full=text_full,
            ref_audio_path=req.get("ref_audio_path", ""),
            prompt_text=req.get("prompt_text", "")
        )
        
        # 清理处理标记
        if request_id in PROCESSING_REQUESTS:
            del PROCESSING_REQUESTS[request_id]
        
        # 如果是重定向情况，在异常响应中也添加重定向头信息
        if redirect_info["redirected"]:
            headers = {
                "X-Model-Redirected": "true",
                "X-Original-Model": "unauthorized_model",
                "X-Final-Model": safe_header_value(redirect_info["final_model"]),
                "X-Redirect-Reason": "model_not_authorized"
            }
            return JSONResponse(
                status_code=400,
                content={"message": "tts failed", "Exception": str(e)},
                headers=headers
            )
        
        return JSONResponse(status_code=400, content={"message": "tts failed", "Exception": str(e)})


@APP.get("/health")
async def health_check():
    return JSONResponse(status_code=200, content={"status": "ok"})


@APP.get("/control")
async def control(command: str = None):
    """代理到 api_v2.control"""
    return await api_v2.control(command)


@APP.get("/tts")
async def tts_get_endpoint(
    request: Request,
    text: str = None,
    text_lang: str = None,
    ref_audio_path: str = None,
    aux_ref_audio_paths: list = None,
    prompt_lang: str = None,
    prompt_text: str = "",
    top_k: int = 15,
    top_p: float = 1,
    temperature: float = 1,
    text_split_method: str = "cut0",
    batch_size: int = 1,
    batch_threshold: float = 0.75,
    split_bucket: bool = True,
    speed_factor: float = 1.0,
    fragment_interval: float = 0.3,
    seed: int = -1,
    media_type: str = "wav",
    streaming_mode: Union[bool, int] = False,
    parallel_infer: bool = True,
    repetition_penalty: float = 1.35,
    sample_steps: int = 32,
    super_sampling: bool = False,
    overlap_length: int = 2,
    min_chunk_length: int = 16,
    # 自动获取相关参数
    model_name: str = "",
    emotion: str = "默认",
    version: str = "v4",
    # 企业级功能参数
    api_key: str = "",
):
    # 如果 text_lang 为空，自动设置为智能语言识别模式
    if not text_lang:
        text_lang = "auto"
    
    client_ip = get_real_ip(request)
    
    # 生成请求ID（浏览器可以通过 X-Request-ID 头传递，否则自动生成）
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    
    if should_log('url_requests'):
        print(f"🔵 GET /tts 端点被调用 - ID: {request_id[:8]}..., IP: {client_ip}, Text: {text[:30] if text else 'None'}...")
    
    req = {
        "request_id": request_id,
        "client_ip": client_ip,
        "text": text,
        "text_lang": text_lang.lower(),
        "ref_audio_path": ref_audio_path,
        "aux_ref_audio_paths": aux_ref_audio_paths,
        "prompt_text": prompt_text,
        "prompt_lang": prompt_lang.lower() if prompt_lang else "",
        "top_k": top_k,
        "top_p": top_p,
        "temperature": temperature,
        "text_split_method": text_split_method,
        "batch_size": int(batch_size),
        "batch_threshold": float(batch_threshold),
        "speed_factor": float(speed_factor),
        "split_bucket": split_bucket,
        "fragment_interval": fragment_interval,
        "seed": seed,
        "media_type": media_type,
        "streaming_mode": streaming_mode,
        "parallel_infer": parallel_infer,
        "repetition_penalty": float(repetition_penalty),
        "sample_steps": int(sample_steps),
        "super_sampling": super_sampling,
        "overlap_length": int(overlap_length),
        "min_chunk_length": int(min_chunk_length),
        # 自动获取相关参数
        "model_name": model_name,
        "emotion": emotion,
        "version": version,
        # 企业级功能参数
        "api_key": api_key,
    }
    return await tts_handle(req)


@APP.post("/tts")
async def tts_post_endpoint(body: TTS_Request, request: Request):
    req = body.dict()
    client_ip = get_real_ip(request)
    req["client_ip"] = client_ip
    
    # 生成请求ID
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    req["request_id"] = request_id
    
    if should_log('url_requests'):
        print(f"🟢 POST /tts 端点被调用 - ID: {request_id[:8]}..., IP: {client_ip}, Text: {req.get('text', '')[:30]}...")
    
    # 如果 text_lang 为空，自动设置为智能语言识别模式
    if not req.get("text_lang"):
        req["text_lang"] = "auto"
    
    return await tts_handle(req)


# 以下端点直接代理到 api_v2 的实现，并添加统计功能

@APP.get("/set_refer_audio")
async def set_refer_audio(refer_audio_path: str = None):
    """代理到 api_v2.set_refer_aduio"""
    return await api_v2.set_refer_aduio(refer_audio_path)


@APP.get("/set_gpt_weights")
async def set_gpt_weights(weights_path: str = None):
    """代理到 api_v2.set_gpt_weights 并添加统计"""
    load_start = time.time()
    result = await api_v2.set_gpt_weights(weights_path)
    
    # 记录模型切换事件
    try:
        stats_manager = get_stats_manager()
        if result.status_code == 200:
            stats_manager.log_system_event(
                event_type="model_switch",
                event_name="GPT模型切换",
                details=f"模型路径: {weights_path}",
                status="success",
                duration=time.time() - load_start
            )
        else:
            stats_manager.log_system_event(
                event_type="model_switch",
                event_name="GPT模型切换失败",
                details=f"模型路径: {weights_path}",
                status="failed",
                duration=time.time() - load_start
            )
    except Exception:
        pass
    
    return result


@APP.get("/set_sovits_weights")
async def set_sovits_weights(weights_path: str = None):
    """代理到 api_v2.set_sovits_weights 并添加统计"""
    load_start = time.time()
    result = await api_v2.set_sovits_weights(weights_path)
    
    try:
        stats_manager = get_stats_manager()
        if result.status_code == 200:
            stats_manager.log_system_event(
                event_type="model_switch",
                event_name="SoVITS模型切换",
                details=f"模型路径: {weights_path}",
                status="success",
                duration=time.time() - load_start
            )
        else:
            stats_manager.log_system_event(
                event_type="model_switch",
                event_name="SoVITS模型切换失败",
                details=f"模型路径: {weights_path}",
                status="failed",
                duration=time.time() - load_start
            )
    except Exception:
        pass
    
    return result


if __name__ == "__main__":
    try:
        if host == "None":  # 在调用时使用 -a None 参数，可以让api监听双栈
            host = None
        
        # 根据配置决定uvicorn的日志级别
        logging_config = API_CONFIG.get('logging', {})
        if not logging_config.get('log_url_requests', True):
            # 如果关闭URL请求日志，设置uvicorn为warning级别（不显示访问日志）
            log_level = "warning"
        else:
            log_level = "info"
        
        print("=" * 80)
        print("✅ API Server 启动成功！")
        print("=" * 80)
        print(f"📍 访问地址: http://{host if host else '0.0.0.0'}:{port}")
        print(f"📊 统计面板: http://{host if host else '0.0.0.0'}:{port}/stats")
        print(f"🔒 安全日志: http://{host if host else '0.0.0.0'}:{port}/security")
        print(f"📖 API文档: http://{host if host else '0.0.0.0'}:{port}/docs")
        print("=" * 80)
        print()
        
        uvicorn.run(
            app=APP, 
            host=host, 
            port=port, 
            workers=1, 
            proxy_headers=True, 
            forwarded_allow_ips='*',
            log_level=log_level,
            access_log=logging_config.get('log_url_requests', True)
        )
    except Exception:
        traceback.print_exc()
        os.kill(os.getpid(), signal.SIGTERM)
        exit(0)
