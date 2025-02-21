'''
Author: diudiu62
Date: 2025-02-20 16:42:49
LastEditTime: 2025-02-21 18:36:26
'''
import os
import uuid
from pydantic import BaseModel
from httpx import AsyncClient
from ..provider import TTSProvider
from ..entites import ProviderType
from ..register import register_provider_adapter
from astrbot.core import logger




class CosyVoiceAudioRequest(BaseModel):
    tts_text: str
    mode: str
    sft_dropdown: str= None
    prompt_text: str= None
    instruct_text: str= None
    seed: int= 0
    stream: bool = False
    speed: float = 1.0
    prompt_voice: str = None
    prompt_voice_bytes: bytes = None



@register_provider_adapter(
    "cosyvoice_tts_api", "CosyVoice API", provider_type=ProviderType.TEXT_TO_SPEECH
)
class ProviderCosyVoiceTTSAPI(TTSProvider):
    def __init__(self, provider_config: dict, provider_settings: dict) -> None:
        super().__init__(provider_config, provider_settings)
        
        # 检查配置是否有效
        self.api_base: str = provider_config.get("api_base", "http://localhost:50000")
        self.prompt_text: str = provider_config.get("prompt_text", "")
       
        self.timeout: int = provider_config.get("timeout", 120)
        self.mode_uid: str = provider_config.get("mode_uid", "zero_shot")
        
        # 检查 prompt_file 是否存在
        self.prompt_file: str = os.path.join("data", "audio_template", provider_config.get("prompt_file", "zero_shot"))

        self.prompt_voice_bytes: bytes = None

        self.headers = {
            "Content-Type": "application/json",
        }
        
        # 初始化存放克隆音频文件的文件夹
        if not os.path.exists('data/audio_template'):
            os.makedirs('data/audio_template')

    async def _generate_request(self, text: str) -> CosyVoiceAudioRequest:
        # 读取克隆音频文件
        with open(self.prompt_file, "rb") as f:
            self.prompt_voice_bytes = f.read()

        return CosyVoiceAudioRequest(
            tts_text=text,
            mode = self.mode_uid,
            prompt_text = self.prompt_text,
            prompt_voice = "参考音频/说得好像您带我以来我考好过几次一样.WAV",
            # prompt_voice_bytes = self.prompt_voice_bytes,
        )

    async def get_audio(self, text: str) -> str:
        path = f"data/temp/cosyvoice_tts_api_{uuid.uuid4()}.wav"
        request = await self._generate_request(text)

        async with AsyncClient(base_url=self.api_base) as client:
            response = await client.post(
                "/text-tts",
                json=request.model_dump(),  # 传递请求体
                headers=self.headers,
                timeout=self.timeout
            )

            if response.status_code == 200:
                # 获取返回的音频内容
                audio_content = response.content
                # 保存音频文件
                with open(path, "wb") as f:
                    f.write(audio_content)
                return path
            
            raise Exception(f"CosyVoice API请求失败: {response.text}。请求URL: {self.api_base}/text-tts，请求体: {request.model_dump()}")




        