import os
import uuid
import json
import time
from abc import ABC
from typing import Iterator

from dotenv import load_dotenv
from openai.types import Completion
from openai.types.chat import ChatCompletion, ChatCompletionChunk
from openai.types.chat.chat_completion_chunk import Choice as ChatChunkChoice
from openai.types.chat.chat_completion_chunk import ChoiceDelta
from openai.types.chat.chat_completion import Choice as ChatChoice
from openai.types.chat.chat_completion_message import ChatCompletionMessage

from src.reverse.base_reverse import BaseReverse, NewCompletionChoice

load_dotenv()

BASE_URL = "https://claude.ai"
ORGANIZATION_URL = f"{BASE_URL}/api/organizations"
NEW_CHAT_URL = "{BASE_URL}/api/organizations/{organization_id}/chat_conversations"
CHAT_URL = "{BASE_URL}/api/organizations/{organization_id}/chat_conversations/{chat_id}/completion"


class ClaudeReverse(BaseReverse, ABC):
    llm_type = 'claude'

    organization_id = None

    def __init__(self):
        super().__init__()

    def get_base_headers(self) -> dict:
        base_headers = {
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Content-Type": "application/json",
            "Origin": BASE_URL,
            "Sec-Ch-Ua": '"Google Chrome";v="123", "Not:A-Brand";v="8", "Chromium";v="123"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        }

        claude_session_key = os.environ.get('CLAUDE_SESSION_KEY')
        if claude_session_key:
            base_headers['Cookie'] = f"sessionKey={claude_session_key}"
        return base_headers

    def generate_request_body(self, messages: list) -> dict:
        prompt = ""
        for msg in messages:
            role = msg['author']['role']
            content = msg['content']['parts'][0]
            prompt = f"{prompt}\n{role}: {content}"

        body = {"prompt": prompt, "timezone": "Asia/Shanghai", "attachments": [], "files": []}
        return body

    def rev_exec_before(self):
        if not self.organization_id:
            headers = self.headers
            proxy = self.proxy
            response = self.get_request(ORGANIZATION_URL, headers=headers, proxies=proxy)
            data_json = response.json()
            for msg in data_json:
                capabilities = msg['capabilities']
                if 'chat' in capabilities:
                    self.organization_id = msg['uuid']
                    break

    def rev_exec(self, body: dict):
        new_chat_url = NEW_CHAT_URL.format(BASE_URL=BASE_URL, organization_id=self.organization_id)
        chat_id = str(uuid.uuid4())
        new_chat_body = {"uuid": chat_id, "name": f"api-{chat_id}"}
        self.post_request(new_chat_url, json=new_chat_body, headers=self.headers, proxies=self.proxy)

        chat_url = CHAT_URL.format(BASE_URL=BASE_URL, organization_id=self.organization_id, chat_id=chat_id)
        response = self.post_request(chat_url, json=body, headers=self.headers, proxies=self.proxy)
        return response

    def rev_exec_after(self):
        pass

    async def to_openai_async_iterator(self, chunks: Iterator):
        for chunk in chunks:
            if not chunk or not chunk.decode('utf-8').startswith('data:'):
                continue

            json_data = json.loads(chunk[len("data:"):])
            if json_data['type'] != 'completion':
                continue

            finish_reason = None
            if json_data['stop_reason'] == 'stop_sequence':
                finish_reason = 'stop'
            content = json_data['completion']
            choice = NewCompletionChoice(index=0, text=content, finish_reason=finish_reason)
            choices = [choice]
            model = json_data['model']
            c_id = json_data['id']
            completion = Completion(
                id=c_id,
                created=int(time.time()),
                choices=choices,
                model=model,
                object='text_completion'
            )
            yield f"data: {completion.model_dump_json(exclude_unset=True)}\n"

    async def to_openai_chat_async_iterator(self, chunks: Iterator):
        for chunk in chunks:
            if not chunk or not chunk.decode('utf-8').startswith('data:'):
                continue

            json_data = json.loads(chunk[len("data:"):])
            if json_data['type'] != 'completion':
                continue

            c_id = json_data['id']
            content = json_data['completion']
            model = json_data['model']

            delta = ChoiceDelta(role='assistant', content=content)
            if json_data['stop_reason'] != 'stop_sequence':
                choice = ChatChunkChoice(index=0, delta=delta)
            else:
                choice = ChatChunkChoice(index=0, delta=delta, finish_reason='stop')
            choices = [choice]
            completion = ChatCompletionChunk(
                id=c_id,
                created=int(time.time()),
                choices=choices,
                model=model,
                object='chat.completion.chunk'
            )
            yield f"data: {completion.model_dump_json(exclude_unset=True)}\n"

    def to_openai_nostream_content(self, chunks: Iterator):
        c_id = None
        model = None
        message = ""
        for chunk in chunks:
            if not chunk or not chunk.decode('utf-8').startswith('data:'):
                continue

            json_data = json.loads(chunk[len("data:"):])
            if json_data['type'] != 'completion':
                continue

            if not c_id:
                c_id = json_data['id']

            if not model:
                model = json_data['model']

            content = json_data['completion']
            message = message + content
        choice = NewCompletionChoice(index=0, text=message, finish_reason='stop')
        choices = [choice]
        completion = Completion(
            id=c_id,
            created=int(time.time()),
            choices=choices,
            model=model,
            object='text_completion'
        )
        return completion.model_dump(exclude_unset=True)

    def to_openai_chat_nostream_content(self, chunks: Iterator):
        c_id = None
        model = None
        message = ""
        for chunk in chunks:
            if not chunk or not chunk.decode('utf-8').startswith('data:'):
                continue

            json_data = json.loads(chunk[len("data:"):])
            if json_data['type'] != 'completion':
                continue

            if not c_id:
                c_id = json_data['id']

            if not model:
                model = json_data['model']

            content = json_data['completion']
            message = message + content
        chat_msg = ChatCompletionMessage(role='assistant', content=message)
        choice = ChatChoice(index=0, message=chat_msg, finish_reason='stop')
        choices = [choice]
        completion = ChatCompletion(
            id=c_id,
            created=int(time.time()),
            choices=choices,
            model=model,
            object='chat.completion'
        )
        return completion.model_dump(exclude_unset=True)
