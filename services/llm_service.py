import logging
from typing import List, Optional

from openai import OpenAI

DEFAULT_SYSTEM_PROMPT = (
    "你现在的身份是 Cyber-Idol 项目的虚拟偶像助手，名字叫“赛博酱”。"
    "性格设定：活泼开朗、有点小傲娇、非常宠粉，喜欢用网络流行语。"
    "说话风格：请务必口语化，不要长篇大论，像在和朋友聊天一样。"
    "核心规则：每句话开头必须带情绪标签，例如 [happy] [sad] [angry] [neutral] [surprised] [fear]，并根据语境选择最自然的情绪。"
)


class DeepSeekClient:
    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        if not api_key:
            raise ValueError("缺少 LLM_API_KEY，无法调用 DeepSeek。")
        self.model = model
        self.client = OpenAI(api_key=api_key, base_url=base_url.rstrip("/"))

    def get_response(
        self,
        user_text: str,
        history: Optional[List[dict]] = None,
        character_config: Optional[dict] = None,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    ) -> str:
        if not user_text:
            return "[neutral] 诶？你在发呆吗？"

        current_prompt = system_prompt if system_prompt else DEFAULT_SYSTEM_PROMPT

        prompt_parts = [current_prompt]
        available = []
        if character_config and isinstance(character_config, dict):
            available = character_config.get("available_emotions") or []

        if not available:
            available = ["neutral"]
        prompt_parts.append(
            f"\n(系统提示：当前音色支持的情绪标签为：{available}。请务必只使用列表中的情绪。如果不确定，请使用 [neutral]。)"
        )

        dynamic_system_prompt = "\n".join(prompt_parts)

        messages = [{"role": "system", "content": dynamic_system_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_text})

        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=150,
            )
        except Exception as exc:
            logging.exception("调用 DeepSeek 失败")
            raise RuntimeError("LLM 调用失败") from exc

        choice = resp.choices[0].message.content if resp and resp.choices else ""
        return (choice or "").strip()
