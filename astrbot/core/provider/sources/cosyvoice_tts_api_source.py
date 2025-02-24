'''
Author: diudiu62
Date: 2025-02-20 16:42:49
LastEditTime: 2025-02-24 17:55:47
'''
import os
import uuid
import asyncio
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
        path = f"data/temp/cosyvoice_tts_api_{uuid.uuid4()}.wav"
        request = await self._generate_request(text)

        async with AsyncClient(base_url=self.cosyvoice_tts_api) as client:
            response = await self._make_api_call(client, request)

            if response.status_code != 200:
                raise CosyVoiceAPIError(f"请求失败: {response.text}")

            audio_content = response.content
            await self._save_audio_file(path, audio_content)

            # 检查音频文件长度是否小于1秒，如果小于，则添加静音
            if await self.get_audio_length(path) < 1:
                return await self.add_silence_to_audio(path, 1)  # 添加1秒静音
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
        process = await asyncio.create_subprocess_exec(
            'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1', file_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await process.communicate()
        return float(stdout)

    async def add_silence_to_audio(self, file_path: str, duration: float) -> str:
        """使用ffmpeg为音频文件添加静音。"""
        new_path = f"{file_path}.silence.wav"
        process = await asyncio.create_subprocess_exec(
            'ffmpeg', '-i', file_path,
            '-af', f'apad=pad_dur={duration}', new_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await process.communicate()
        return new_path