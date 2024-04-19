import os
from abc import ABC, abstractmethod
from typing import Iterator, Any

import requests
from starlette.responses import StreamingResponse
from openai.types import CompletionChoice


class NewCompletionChoice(CompletionChoice):
    finish_reason: Any = None


class BaseReverse(ABC):
    type: str = None

    def __init__(self):
        self.headers = self.get_base_headers()
        self.proxy = self.get_proxy_info()

    @abstractmethod
    def get_base_headers(self) -> dict:
        raise NotImplementedError

    @abstractmethod
    def generate_request_body(self, messages: list) -> dict:
        raise NotImplementedError

    @abstractmethod
    def rev_exec_before(self):
        raise NotImplementedError

    @abstractmethod
    def rev_exec(self, body: dict):
        raise NotImplementedError

    @abstractmethod
    def rev_exec_after(self):
        raise NotImplementedError

    @abstractmethod
    async def to_openai_async_iterator(self, chunks: Iterator):
        raise NotImplementedError

    @abstractmethod
    async def to_openai_chat_async_iterator(self, chunks: Iterator):
        raise NotImplementedError

    @abstractmethod
    def to_openai_nostream_content(self, chunks: Iterator):
        raise NotImplementedError

    @abstractmethod
    def to_openai_chat_nostream_content(self, chunks: Iterator):
        raise NotImplementedError

    def to_openai_response(self, chunks, is_stream: bool = False, is_chat: bool = False):
        if is_chat and is_stream:
            media_type = "text/event-stream"
            async_iter = self.to_openai_chat_async_iterator(chunks)
            return StreamingResponse(async_iter, media_type=media_type)
        elif is_chat and not is_stream:
            return self.to_openai_chat_nostream_content(chunks)
        elif not is_chat and is_stream:
            media_type = "text/event-stream"
            async_iter = self.to_openai_async_iterator(chunks)
            return StreamingResponse(async_iter, media_type=media_type)
        elif not is_chat and not is_stream:
            return self.to_openai_nostream_content(chunks)
        raise Exception("Illegal parameter")

    async def do_run(self, messages: list, is_stream: bool = False, is_chat: bool = False):
        try:
            body = self.generate_request_body(messages)
            self.rev_exec_before()
            response = self.rev_exec(body)
            return self.to_openai_response(response.iter_lines(), is_stream, is_chat)
        except Exception as e:
            raise e
        finally:
            self.rev_exec_after()

    def post_request(self, url, data=None, headers=None, proxies=None, **kwargs):
        response = requests.post(url, data=data, headers=headers, proxies=proxies, **kwargs)
        response.raise_for_status()
        return response

    def get_request(self, url, params=None, headers=None, proxies=None, **kwargs):
        response = requests.get(url, params=params, headers=headers, proxies=proxies, **kwargs)
        response.raise_for_status()
        return response

    def get_proxy_info(self):
        proxy = {}
        enable = os.environ.get('PROXY_ENABLE', 'false')
        if enable and enable.upper() == 'TRUE':
            proxy_host = os.environ.get('PROXY_HOST')
            proxy_port = os.environ.get('PROXY_PORT')
            proxy['http'] = f"http://{proxy_host}:{proxy_port}"
            proxy['https'] = f"http://{proxy_host}:{proxy_port}"
        return proxy
