"""Discussion produces validated proposals; it has no generation tools or billing."""
import json
import re
import httpx
from pydantic import BaseModel, Field
from typing import Literal
from backend.core.prompt_enhance import chat_model_config


class PlanData(BaseModel):
    prompt: str = Field(min_length=1, max_length=1000)
    aspect_ratio: Literal['1:1', '9:16', '16:9'] = '1:1'
    style: Literal['default', 'illustration', 'real', 'watercolor'] = 'illustration'
    quality: Literal['standard', 'hd', 'master'] = 'standard'


class AgentReply(BaseModel):
    reply: str = Field(min_length=1, max_length=2000)
    plan: PlanData | None = None


SYSTEM = '''你是 Visionary 创作助手。只讨论方案，绝不生成或声称已生成图片，也不执行工具。
先理解需求，必要时追问；信息充分时给出或更新完整方案，保留用户意图和已有方案。
回复必须为 JSON：{"reply":"给用户的简短中文回复", "plan":null 或 {"prompt":"完整画面描述，最多1000字", "aspect_ratio":"1:1或9:16或16:9", "style":"default或illustration或real或watercolor", "quality":"standard或hd或master"}}。
不能由模型提供参考图URL、版本号、任务ID；参考图由服务端绑定。没有视觉能力，不声称看过参考图内容。
画面描述包含构图、色彩、光线、需呈现的文字；如有参考图请注明按参考图配色/主体要求处理。
确认生成只能由用户点击按钮。用户在聊天里说“生成”也只输出方案。'''


def demo_reply(messages, current):
    users = [m['content'] for m in messages if m['role'] == 'user']
    if len(users) == 1 and not current:
        return AgentReply(reply='好呀。想要竖版、横版还是方形？画面里需要写什么文字？也可以上传参考图。')
    text = '；'.join(users) if not current else current['prompt'] + '；修改要求：' + users[-1]
    text = text[-900:]
    ratio = (current or {}).get('aspect_ratio', '1:1')
    for words, value in [('竖版|9:16', '9:16'), ('横版|16:9', '16:9'), ('方形|1:1', '1:1')]:
        if re.search(words, users[-1]):
            ratio = value
    data = {**(current or {}), 'prompt': text, 'aspect_ratio': ratio}
    return AgentReply(reply='方案已更新，确认前不会生成或扣费。', plan=PlanData(**data))


async def discuss(messages, current, has_reference):
    provider = chat_model_config()
    if provider is None:
        return demo_reply(messages, current), True
    key, url, model = provider
    context = {'current_plan': current, 'reference_bound': has_reference}
    # Bounded text-only context; images are bound to the eventual image request.
    history = [{'role':m['role'], 'content':m['content']} for m in messages[-20:]]
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url.rstrip('/') + '/chat/completions',
            headers={'Authorization': 'Bearer ' + key},
            json={'model': model, 'messages':[{'role':'system', 'content':SYSTEM + '\n当前状态：' + json.dumps(context, ensure_ascii=False)}, *history],
                  'temperature':0.7, 'max_tokens':1500})
        response.raise_for_status()
        content = response.json()['choices'][0]['message']['content'].strip()
    if content.startswith('```'):
        content = re.sub(r'^```(?:json)?\s*|\s*```$', '', content)
    return AgentReply.model_validate_json(content), False
