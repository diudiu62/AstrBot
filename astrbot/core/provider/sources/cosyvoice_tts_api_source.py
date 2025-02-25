'''
Author: diudiu62
Date: 2025-02-20 16:42:49
LastEditTime: 2025-02-25 14:30:22
'''
from datetime import datetime
import os
import wave
from pydantic import BaseModel
from httpx import AsyncClient
from ..provider import TTSProvider
from ..entites import ProviderType
from ..register import register_provider_adapter
from astrbot.core import logger

class CosyVoiceAudioRequest(BaseModel):
    tts_text: str
    mode: str
    prompt_text: str
    prompt_voice: str

class CosyVoiceAPIError(Exception):
    """自定义异常类，用于CosyVoice API相关错误。"""
    pass

@register_provider_adapter("cosyvoice_tts_api", "CosyVoice API", provider_type=ProviderType.TEXT_TO_SPEECH)
class ProviderCosyVoiceTTSAPI(TTSProvider):
    def __init__(self, provider_config: dict, provider_settings: dict) -> None:
        super().__init__(provider_config, provider_settings)
        # 获取API相关配置
        self.cosyvoice_tts_api = provider_config.get("cosyvoice_tts_api", "http://localhost:50000")
        self.prompt_text = provider_config.get("prompt_text", "")
        self.timeout = int(provider_config.get("timeout", 120))
        self.mode_uid = provider_config.get("mode_uid", "zero_shot")
        self.prompt_file_path = os.path.join("data", "audio_templates", provider_config.get("prompt_file", ""))
        self.prompt_remote_file_path = None
        # 确保音频模板存放路径存在
        os.makedirs('data/audio_templates', exist_ok=True)

    async def _generate_request(self, text: str) -> CosyVoiceAudioRequest:
        """生成语音合成请求对象。"""
        if not self.prompt_remote_file_path:
            await self._update_prompt_file(self.prompt_file_path)

        return CosyVoiceAudioRequest(
            tts_text=text,
            mode=self.mode_uid,
            prompt_text=self.prompt_text,
            prompt_voice=self.prompt_remote_file_path,
        )

    async def get_audio(self, text: str) -> str:
        """获取合成语音的音频文件路径。"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # 获取当前时间戳
        path = f"data/temp/cosyvoice_tts_api_{timestamp}.wav"  # 形成新的路径格式
        request = await self._generate_request(text)

        async with AsyncClient(base_url=self.cosyvoice_tts_api) as client:
            response = await self._make_api_call(client, request)

            if response.status_code != 200:
                raise CosyVoiceAPIError(f"请求失败: {response.text}")

            audio_content = response.content
            await self._save_audio_file(path, audio_content)

            # 检查音频文件长度是否小于1秒，如果小于，则添加静音
            if await self.get_audio_length(path) < 1:
                new_path = await self.add_silence_to_audio(path, 1)  # 添加1秒静音
                os.remove(path)  # 删除原音频文件
                return new_path
            return path
        
    async def _make_api_call(self, client: AsyncClient, request: CosyVoiceAudioRequest):
        """向API发送请求并返回响应。"""
        return await client.post(
            "/text-tts",
            json=request.model_dump(),  # 将请求体转换为字典
            headers={"Content-Type": "application/json"},
            timeout=self.timeout
        )

    async def _save_audio_file(self, path: str, audio_content: bytes):
        """将音频内容保存为文件。"""
        with open(path, "wb") as f:
            f.write(audio_content)

    async def _update_prompt_file(self, file_path: str) -> None:
        """上传音频文件到服务器以供克隆使用。"""
        if not os.path.exists(file_path):
            raise CosyVoiceAPIError("指定的音频文件不存在。")
        
        print(f"上传音频文件: {file_path}")

        async with AsyncClient(base_url=self.cosyvoice_tts_api) as client:
            with open(file_path, 'rb') as f:
                response = await client.post("/upload_prompt_audio", files={"file": f})

            if response.status_code == 200:
                self.prompt_remote_file_path = response.json().get("path")
            else:
                raise CosyVoiceAPIError(f"上传失败: {response.text}")

    async def get_audio_length(self, file_path: str) -> float:
        """获取音频文件的持续时间（秒）。"""
        with wave.open(file_path, 'rb') as wf:  # 这里使用 wave 库
            duration = wf.getnframes() / wf.getframerate()  # 获取总帧数/采样率
        return duration

    async def add_silence_to_audio(self, input_path: str, silence_duration: float) -> str:
        """在 WAV 文件末尾添加静音并返回新文件路径。"""
        output_path = f"{input_path}.silence.wav"

        # 打开原音频文件
        with wave.open(input_path, 'rb') as wf:
            params = wf.getparams()  # 获取音频参数
            num_frames = int(silence_duration * params.framerate)  # 计算静音帧数
            silence_frames = b'\x00' * num_frames * params.nchannels * 2  # 生成静音数据，2 字节为采样位深

            # 创建写入的新音频文件
            with wave.open(output_path, 'wb') as out_wf:
                out_wf.setparams(params)  # 设置与原文件相同的参数
                out_wf.writeframes(wf.readframes(wf.getnframes()))  # 写入原音频数据
                out_wf.writeframes(silence_frames)  # 添加静音

        return output_path