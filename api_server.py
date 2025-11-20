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
    "top_k": 5,                   # int. top k sampling
    "top_p": 1,                   # float. top p sampling
    "temperature": 1,             # float. temperature for sampling
    "text_split_method": "cut0",  # str. text split method, see text_segmentation_method.py for details.
    "batch_size": 1,              # int. batch size for inference
    "batch_threshold": 0.75,      # float. threshold for batch splitting.
    "split_bucket": True,         # bool. whether to split the batch into multiple buckets.
    "speed_factor":1.0,           # float. control the speed of the synthesized audio.
    "streaming_mode": False,      # bool. whether to return a streaming response.
    "seed": -1,                   # int. random seed for reproducibility.
    "parallel_infer": True,       # bool. whether to use parallel inference.
    "repetition_penalty": 1.35,   # float. repetition penalty for T2S model.
    "sample_steps": 32,           # int. number of sampling steps for VITS model V3.
    "super_sampling": False       # bool. whether to use super-sampling for audio when using VITS model V3.
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
from typing import Generator
from collections import defaultdict
from datetime import datetime, timedelta
import yaml
import uuid

now_dir = os.getcwd()
sys.path.append(now_dir)
sys.path.append("%s/GPT_SoVITS" % (now_dir))

import argparse
import subprocess
import wave
import signal
import numpy as np
import soundfile as sf
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

# 导入统计模块
from api_stats import get_stats_manager, register_stats_routes

# print(sys.path)
i18n = I18nAuto()
cut_method_names = get_cut_method_names()

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
    
    # 语言代码映射：API语言代码 -> 目录名
    lang_mapping = {
        "zh": "中文",
        "en": "英语",
        "ja": "日语",
        "yue": "粤语",
        "ko": "韩语"
    }
    
    # 获取实际的语言目录名
    actual_lang = lang_mapping.get(lang, lang)
    
    # 支持多个版本的查找
    version_paths = [f"models/{version}", "models/v4", "models/v3", "models/v2"]
    
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
    # 支持多个版本的查找
    version_paths = [f"models/{version}", "models/v4", "models/v3", "models/v2"]
    
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
    
    # 语言代码映射：API语言代码 -> 目录名
    lang_mapping = {
        "zh": "中文",
        "en": "英语",
        "ja": "日语",
        "yue": "粤语",
        "ko": "韩语"
    }
    
    # 获取实际的语言目录名
    actual_lang = lang_mapping.get(prompt_lang, prompt_lang)
    
    if emotion == "随机":
        ref_audio, lab_content = random_ref_audio(model_name, actual_lang, version)
        prompt_text = lab_content
    else:
        emo, prompt_text = get_ref_audio(model_name, prompt_lang, emotion, version)
        if emo != "":
            # 支持多个版本的查找
            version_paths = [f"models/{version}", "models/v4", "models/v3", "models/v2"]
            ref_audio = ""
            for version_path in version_paths:
                if Path(f"{version_path}/{model_name}").exists():
                    # 使用映射后的语言目录名
                    potential_path = f"{version_path}/{model_name}/reference_audios/{actual_lang}/emotions/【{emo}】{prompt_text}.wav"
                    if Path(potential_path).exists():
                        ref_audio = potential_path
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
            # 如果是语言全称，返回对应的代码
            language_map = {
                "中文": "zh",
                "日语": "ja",
                "英语": "en",
                "韩语": "ko",
                "粤语": "yue"
            }
            # 如果匹配到的是下划线开头的语言代码，直接返回
            if extracted in ["zh", "ja", "en", "ko", "yue", "ZH", "JA", "EN", "KO", "YUE"]:
                return extracted.lower()
            return language_map.get(extracted, extracted.lower())
    
    return ""

def auto_get_all_parameters(model_name: str = "", emotion: str = "默认", version: str = "v4"):
    """自动获取所有缺失的参数：prompt_lang, ref_audio_path, prompt_text"""
    if model_name == "":
        return "", "", ""
    
    # 首先尝试从模型名称自动获取语言
    auto_prompt_lang = extract_language_from_model_name(model_name)
    
    if not auto_prompt_lang:
        # 如果从模型名称提取失败，尝试查找第一个可用的语言
        version_paths = [f"models/{version}", "models/v4", "models/v3", "models/v2"]
        for version_path in version_paths:
            model_path = Path(f"{version_path}/{model_name}")
            if model_path.exists():
                ref_audios_path = model_path / "reference_audios"
                if ref_audios_path.exists():
                    # 获取第一个可用的语言目录
                    lang_dirs = [d for d in ref_audios_path.iterdir() if d.is_dir()]
                    if lang_dirs:
                        first_lang_dir = lang_dirs[0].name
                        # 将目录名映射回语言代码
                        dir_to_lang_mapping = {
                            "中文": "zh",
                            "英语": "en", 
                            "日语": "ja",
                            "粤语": "yue",
                            "韩语": "ko"
                        }
                        auto_prompt_lang = dir_to_lang_mapping.get(first_lang_dir, "zh")
                        break
    
    # 如果还是没找到语言，使用默认语言
    if not auto_prompt_lang:
        auto_prompt_lang = "zh"
    
    # 使用获取到的语言自动获取参考音频和文本
    ref_audio, prompt_text = auto_get_ref_audio_and_prompt_text(model_name, auto_prompt_lang, emotion, version)
    
    return auto_prompt_lang, ref_audio, prompt_text
#===============API配置管理和认证功能================

# 全局配置变量
API_CONFIG = {}
USAGE_STATS = defaultdict(list)
RATE_LIMIT = defaultdict(list)
PROCESSING_REQUESTS = {}  # 正在处理的请求（用于去重）

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
                'blocked_models': []
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

def get_model_for_user(api_key: str, text_lang: str, model_name: str = "") -> tuple[str, dict]:
    """
    为用户获取合适的模型，返回(最终模型名, 重定向信息)
    
    Returns:
        tuple: (final_model_name, redirect_info)
            - final_model_name: 最终使用的模型名
            - redirect_info: 重定向信息字典，包含是否被重定向和原因
    """
    redirect_info = {
        "redirected": False,
        "original_model": model_name,
        "final_model": "",
        "reason": ""
    }
    
    # 如果没有指定模型，使用默认模型
    if not model_name:
        final_model = get_default_model(text_lang)
        redirect_info["final_model"] = final_model
        return final_model, redirect_info
    
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
            if API_CONFIG.get('security', {}).get('log_requests', True):
                print(f"⚠️ 模型重定向 - Key: {api_key[:8]}..., 请求模型: {model_name}, 重定向到: {final_model}")
            
            return final_model, redirect_info
    
    # 用户有权限访问指定模型
    redirect_info["final_model"] = model_name
    return model_name, redirect_info

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

# 记录TTS配置加载
import time as time_module
load_start = time_module.time()
tts_config = TTS_Config(config_path)
print(tts_config)

try:
    stats_manager_init.log_system_event(
        event_type="model_load",
        event_name="TTS配置加载",
        details=f"版本: {tts_config.version}",
        status="success",
        duration=time_module.time() - load_start
    )
except:
    pass

# 记录TTS Pipeline初始化
pipeline_start = time_module.time()
tts_pipeline = TTS(tts_config)

try:
    stats_manager_init.log_system_event(
        event_type="model_load",
        event_name="TTS Pipeline初始化",
        details="GPT-SoVITS模型加载完成",
        status="success",
        duration=time_module.time() - pipeline_start
    )
except:
    pass

APP = FastAPI()

# 注册统计WebUI路由
register_stats_routes(APP)


class TTS_Request(BaseModel):
    text: str = None
    text_lang: str = None  # 不提供默认值，在处理时自动设置为 "auto"
    ref_audio_path: str = None
    aux_ref_audio_paths: list = None
    prompt_lang: str = None
    prompt_text: str = ""
    top_k: int = 5
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
    streaming_mode: bool = False
    parallel_infer: bool = True
    repetition_penalty: float = 1.35
    sample_steps: int = 32
    super_sampling: bool = False
    # 自动获取相关字段
    model_name: str = ""
    emotion: str = "默认"
    version: str = "v4"
    # 企业级功能字段
    api_key: str = ""


### modify from https://github.com/RVC-Boss/GPT-SoVITS/pull/894/files
def pack_ogg(io_buffer: BytesIO, data: np.ndarray, rate: int):
    with sf.SoundFile(io_buffer, mode="w", samplerate=rate, channels=1, format="ogg") as audio_file:
        audio_file.write(data)
    return io_buffer


def pack_raw(io_buffer: BytesIO, data: np.ndarray, rate: int):
    io_buffer.write(data.tobytes())
    return io_buffer


def pack_wav(io_buffer: BytesIO, data: np.ndarray, rate: int):
    io_buffer = BytesIO()
    sf.write(io_buffer, data, rate, format="wav")
    return io_buffer


def pack_aac(io_buffer: BytesIO, data: np.ndarray, rate: int):
    process = subprocess.Popen(
        [
            "ffmpeg",
            "-f",
            "s16le",  # 输入16位有符号小端整数PCM
            "-ar",
            str(rate),  # 设置采样率
            "-ac",
            "1",  # 单声道
            "-i",
            "pipe:0",  # 从管道读取输入
            "-c:a",
            "aac",  # 音频编码器为AAC
            "-b:a",
            "192k",  # 比特率
            "-vn",  # 不包含视频
            "-f",
            "adts",  # 输出AAC数据流格式
            "pipe:1",  # 将输出写入管道
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    out, _ = process.communicate(input=data.tobytes())
    io_buffer.write(out)
    return io_buffer


def pack_audio(io_buffer: BytesIO, data: np.ndarray, rate: int, media_type: str):
    if media_type == "ogg":
        io_buffer = pack_ogg(io_buffer, data, rate)
    elif media_type == "aac":
        io_buffer = pack_aac(io_buffer, data, rate)
    elif media_type == "wav":
        io_buffer = pack_wav(io_buffer, data, rate)
    else:
        io_buffer = pack_raw(io_buffer, data, rate)
    io_buffer.seek(0)
    return io_buffer


# from https://huggingface.co/spaces/coqui/voice-chat-with-mistral/blob/main/app.py
def wave_header_chunk(frame_input=b"", channels=1, sample_width=2, sample_rate=32000):
    # This will create a wave header then append the frame input
    # It should be first on a streaming wav file
    # Other frames better should not have it (else you will hear some artifacts each chunk start)
    wav_buf = BytesIO()
    with wave.open(wav_buf, "wb") as vfout:
        vfout.setnchannels(channels)
        vfout.setsampwidth(sample_width)
        vfout.setframerate(sample_rate)
        vfout.writeframes(frame_input)

    wav_buf.seek(0)
    return wav_buf.read()


def get_real_ip(request: Request) -> str:
    """获取真实IP地址"""
    if "x-forwarded-for" in request.headers:
        # 当有多级代理时，x-forwarded-for 的值是 "client, proxy1, proxy2"，取第一个
        return request.headers["x-forwarded-for"].split(",")[0].strip()
    if "x-real-ip" in request.headers:
        return request.headers["x-real-ip"]
    return request.client.host


def handle_control(command: str):
    if command == "restart":
        os.execl(sys.executable, sys.executable, *argv)
    elif command == "exit":
        os.kill(os.getpid(), signal.SIGTERM)
        exit(0)


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

def check_params(req: dict):
    text: str = req.get("text", "")
    text_lang: str = req.get("text_lang", "")
    ref_audio_path: str = req.get("ref_audio_path", "")
    streaming_mode: bool = req.get("streaming_mode", False)
    media_type: str = req.get("media_type", "wav")
    prompt_lang: str = req.get("prompt_lang", "")
    text_split_method: str = req.get("text_split_method", "cut5")
    model_name: str = req.get("model_name", "")
    emotion: str = req.get("emotion", "默认")
    version: str = req.get("version", "v4")

    

    if text in [None, ""]:
        return JSONResponse(status_code=400, content={"message": "text is required"})
    
    # 如果没有提供 text_lang，自动使用智能语言识别模式
    if text_lang in [None, ""]:
        text_lang = "auto"
        req["text_lang"] = "auto"  # 更新请求参数
    
    if text_lang.lower() not in tts_config.languages:
        return JSONResponse(
            status_code=400,
            content={"message": f"text_lang: {text_lang} is not supported in version {tts_config.version}"},
        )
    
    # 如果提供了 model_name，允许在没有 ref_audio_path 的情况下继续（稍后会自动获取）
    # 只有在既没有 model_name 也没有 ref_audio_path 的情况下才报错
    if ref_audio_path in [None, ""] and model_name == "":
        return JSONResponse(status_code=400, content={"message": "Either ref_audio_path or model_name is required"})
    
    # prompt_lang 的验证逻辑：
    # 1. 如果提供了 model_name，可以在后续自动获取
    # 2. 如果提供了 ref_audio_path，也可以从文件名提取 prompt_text（暂不验证 prompt_lang）
    # 3. 只有在既没有 model_name 也没有 ref_audio_path 时才需要 prompt_lang
    if model_name != "" and prompt_lang == "":
        # 这里不报错，在 tts_handle 中会自动获取
        pass
    elif ref_audio_path not in [None, ""] and prompt_lang == "":
        # 提供了 ref_audio_path，prompt_lang 可以从文件名提取（暂不验证）
        pass
    elif prompt_lang != "" and prompt_lang.lower() not in tts_config.languages:
        return JSONResponse(
            status_code=400,
            content={"message": f"prompt_lang: {prompt_lang} is not supported in version {tts_config.version}"},
        )
    elif model_name == "" and ref_audio_path in [None, ""] and prompt_lang == "":
        # 既没有 model_name 也没有 ref_audio_path 且没有 prompt_lang，这是错误的情况
        return JSONResponse(status_code=400, content={"message": "prompt_lang is required when neither ref_audio_path nor model_name is provided"})
    
    if media_type not in ["wav", "raw", "ogg", "aac"]:
        return JSONResponse(status_code=400, content={"message": f"media_type: {media_type} is not supported"})
    elif media_type == "ogg" and not streaming_mode:
        return JSONResponse(status_code=400, content={"message": "ogg format is not supported in non-streaming mode"})

    if text_split_method not in cut_method_names:
        return JSONResponse(
            status_code=400, content={"message": f"text_split_method:{text_split_method} is not supported"}
        )

    
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
                "top_k": 5,                   # int. top k sampling
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
    print(f"🔶 tts_handle 函数被调用 - ID: {request_id[:8] if len(request_id) > 8 else request_id}..., Text: {req.get('text', '')[:30]}...")
    
    # 检查是否正在处理相同的请求（防止浏览器重复提交）
    if request_id in PROCESSING_REQUESTS:
        wait_time = time.time() - PROCESSING_REQUESTS[request_id]
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
    
    # 获取用户可访问的模型
    final_model_name, redirect_info = get_model_for_user(user_info['key'], text_lang, model_name)
    
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
    
    check_res = check_params(req)
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
            
            # 创建带有重定向头的新Response对象（使用ASCII字符）
            headers = {
                "X-Model-Redirected": "true",
                "X-Original-Model": "unauthorized_model",
                "X-Final-Model": redirect_info["final_model"],
                "X-Redirect-Reason": "model_not_authorized"
            }
            
            return Response(
                content=response_body,
                status_code=status_code,
                headers=headers,
                media_type="application/json"
            )
        
        return check_res

    if streaming_mode or return_fragment:
        req["return_fragment"] = True

    try:
        # 4. 记录请求日志
        if API_CONFIG.get('security', {}).get('log_requests', True):
            client_ip = req.get("client_ip", "unknown")
            print(f"📊 API调用 - IP: {client_ip}, Key: {user_info['key'][:8]}..., Model: {model_name}, Text: {req.get('text', '')[:20]}...")
        
        # 5. 执行TTS推理
        tts_start_time = time.time()
        tts_generator = tts_pipeline.run(req)

        if streaming_mode:

            def streaming_generator(tts_generator: Generator, media_type: str):
                if_frist_chunk = True
                for sr, chunk in tts_generator:
                    if if_frist_chunk and media_type == "wav":
                        yield wave_header_chunk(sample_rate=sr)
                        media_type = "raw"
                        if_frist_chunk = False
                    yield pack_audio(BytesIO(), chunk, sr, media_type).getvalue()

            # 添加重定向信息到响应头（使用ASCII字符）
            headers = {}
            if redirect_info["redirected"]:
                headers["X-Model-Redirected"] = "true"
                headers["X-Original-Model"] = redirect_info["original_model"]
                headers["X-Final-Model"] = redirect_info["final_model"]
                headers["X-Redirect-Reason"] = "model_not_authorized"
                
            response = StreamingResponse(
                streaming_generator(
                    tts_generator,
                    media_type,
                ),
                media_type=f"audio/{media_type}",
                headers=headers
            )
        else:
            # 添加重定向信息到响应头
            headers = {}
            if redirect_info["redirected"]:
                headers["X-Model-Redirected"] = "true"
                headers["X-Original-Model"] = redirect_info["original_model"]
                headers["X-Final-Model"] = redirect_info["final_model"]
                headers["X-Redirect-Reason"] = "model_not_authorized"
                
            sr, audio_data = next(tts_generator)
            audio_data = pack_audio(BytesIO(), audio_data, sr, media_type).getvalue()
            response = Response(audio_data, media_type=f"audio/{media_type}", headers=headers)
        
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
        
        print(f"⏱️  处理时间 - 总计: {total_time:.2f}秒, TTS合成: {tts_time:.2f}秒")
        
        # 清理处理标记
        if request_id in PROCESSING_REQUESTS:
            del PROCESSING_REQUESTS[request_id]
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
                "X-Final-Model": redirect_info["final_model"],
                "X-Redirect-Reason": "model_not_authorized"
            }
            return JSONResponse(
                status_code=400,
                content={"message": "tts failed", "Exception": str(e)},
                headers=headers
            )
        
        return JSONResponse(status_code=400, content={"message": "tts failed", "Exception": str(e)})


@APP.get("/control")
async def control(command: str = None):
    if command is None:
        return JSONResponse(status_code=400, content={"message": "command is required"})
    handle_control(command)


@APP.get("/tts")
async def tts_get_endpoint(
    request: Request,
    text: str = None,
    text_lang: str = None,
    ref_audio_path: str = None,
    aux_ref_audio_paths: list = None,
    prompt_lang: str = None,
    prompt_text: str = "",
    top_k: int = 5,
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
    streaming_mode: bool = False,
    parallel_infer: bool = True,
    repetition_penalty: float = 1.35,
    sample_steps: int = 32,
    super_sampling: bool = False,
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
    
    print(f"🟢 POST /tts 端点被调用 - ID: {request_id[:8]}..., IP: {client_ip}, Text: {req.get('text', '')[:30]}...")
    
    # 如果 text_lang 为空，自动设置为智能语言识别模式
    if not req.get("text_lang"):
        req["text_lang"] = "auto"
    
    return await tts_handle(req)


@APP.get("/set_refer_audio")
async def set_refer_aduio(refer_audio_path: str = None):
    try:
        tts_pipeline.set_ref_audio(refer_audio_path)
    except Exception as e:
        return JSONResponse(status_code=400, content={"message": "set refer audio failed", "Exception": str(e)})
    return JSONResponse(status_code=200, content={"message": "success"})


# @APP.post("/set_refer_audio")
# async def set_refer_aduio_post(audio_file: UploadFile = File(...)):
#     try:
#         # 检查文件类型，确保是音频文件
#         if not audio_file.content_type.startswith("audio/"):
#             return JSONResponse(status_code=400, content={"message": "file type is not supported"})

#         os.makedirs("uploaded_audio", exist_ok=True)
#         save_path = os.path.join("uploaded_audio", audio_file.filename)
#         # 保存音频文件到服务器上的一个目录
#         with open(save_path , "wb") as buffer:
#             buffer.write(await audio_file.read())

#         tts_pipeline.set_ref_audio(save_path)
#     except Exception as e:
#         return JSONResponse(status_code=400, content={"message": f"set refer audio failed", "Exception": str(e)})
#     return JSONResponse(status_code=200, content={"message": "success"})


@APP.get("/set_gpt_weights")
async def set_gpt_weights(weights_path: str = None):
    load_start = time.time()
    try:
        if weights_path in ["", None]:
            return JSONResponse(status_code=400, content={"message": "gpt weight path is required"})
        
        tts_pipeline.init_t2s_weights(weights_path)
        
        # 记录GPT模型加载成功
        try:
            stats_manager = get_stats_manager()
            stats_manager.log_system_event(
                event_type="model_switch",
                event_name="GPT模型切换",
                details=f"模型路径: {weights_path}",
                status="success",
                duration=time.time() - load_start
            )
        except:
            pass
            
    except Exception as e:
        # 记录GPT模型加载失败
        try:
            stats_manager = get_stats_manager()
            stats_manager.log_system_event(
                event_type="model_switch",
                event_name="GPT模型切换失败",
                details=f"模型路径: {weights_path}, 错误: {str(e)}",
                status="failed",
                duration=time.time() - load_start
            )
        except:
            pass
        return JSONResponse(status_code=400, content={"message": "change gpt weight failed", "Exception": str(e)})

    return JSONResponse(status_code=200, content={"message": "success"})


@APP.get("/set_sovits_weights")
async def set_sovits_weights(weights_path: str = None):
    load_start = time.time()
    try:
        if weights_path in ["", None]:
            return JSONResponse(status_code=400, content={"message": "sovits weight path is required"})
        
        tts_pipeline.init_vits_weights(weights_path)
        
        # 记录SoVITS模型加载成功
        try:
            stats_manager = get_stats_manager()
            stats_manager.log_system_event(
                event_type="model_switch",
                event_name="SoVITS模型切换",
                details=f"模型路径: {weights_path}",
                status="success",
                duration=time.time() - load_start
            )
        except:
            pass
            
    except Exception as e:
        # 记录SoVITS模型加载失败
        try:
            stats_manager = get_stats_manager()
            stats_manager.log_system_event(
                event_type="model_switch",
                event_name="SoVITS模型切换失败",
                details=f"模型路径: {weights_path}, 错误: {str(e)}",
                status="failed",
                duration=time.time() - load_start
            )
        except:
            pass
        return JSONResponse(status_code=400, content={"message": "change sovits weight failed", "Exception": str(e)})
    
    return JSONResponse(status_code=200, content={"message": "success"})


if __name__ == "__main__":
    try:
        if host == "None":  # 在调用时使用 -a None 参数，可以让api监听双栈
            host = None
        uvicorn.run(app=APP, host=host, port=port, workers=1, proxy_headers=True, forwarded_allow_ips='*')
    except Exception:
        traceback.print_exc()
        os.kill(os.getpid(), signal.SIGTERM)
        exit(0)
