#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成示例音频文件用于演示"""

import wave
import struct
import math
import os
import sys

# 确保输出使用 UTF-8
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

def generate_tone(frequency, duration, sample_rate=44100):
    """生成指定频率和时长的正弦波"""
    frames = []
    for i in range(int(sample_rate * duration)):
        value = int(32767.0 * math.sin(2.0 * math.pi * frequency * (float(i) / sample_rate)))
        frames.append(struct.pack('<h', value))
    return b''.join(frames)

def create_sample_audio(filename, duration=3):
    """创建示例音频（模拟播客）"""
    sample_rate = 44100

    # 创建一个包含不同频率的音频，模拟人类语音
    audio_data = b''

    # 节奏1：低音
    audio_data += generate_tone(100, 0.5, sample_rate)
    # 节奏2：中音
    audio_data += generate_tone(200, 0.5, sample_rate)
    # 节奏3：高音
    audio_data += generate_tone(300, 0.5, sample_rate)
    # 节奏4：低中音
    audio_data += generate_tone(150, 0.5, sample_rate)

    # 重复以达到指定时长
    while len(audio_data) < sample_rate * 2 * duration:
        audio_data += generate_tone(150, 0.5, sample_rate)
        audio_data += generate_tone(250, 0.5, sample_rate)

    # 写入 WAV 文件
    with wave.open(filename, 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_data[:sample_rate * 2 * duration])

# 生成示例文件
os.makedirs('samples', exist_ok=True)

print("生成示例音频文件...")
create_sample_audio('samples/original_voice.wav', duration=6)
create_sample_audio('samples/podcast_host.wav', duration=10)
create_sample_audio('samples/podcast_guest.wav', duration=8)

print("✓ samples/original_voice.wav - 原始录音样本（6秒）")
print("✓ samples/podcast_host.wav - 主持人语音（10秒）")
print("✓ samples/podcast_guest.wav - 嘉宾语音（8秒）")
print("\n所有示例文件已生成！")
