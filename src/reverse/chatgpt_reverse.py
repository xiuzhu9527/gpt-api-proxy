import os
import uuid
import json
import time
from abc import ABC
from typing import Iterator, AsyncIterator, Any

from dotenv import load_dotenv
from openai.types import Completion, CompletionChoice
from openai.types.chat import ChatCompletion, ChatCompletionChunk
from openai.types.chat.chat_completion_chunk import Choice as ChatChunkChoice
from openai.types.chat.chat_completion_chunk import ChoiceDelta
from openai.types.chat.chat_completion import Choice as ChatChoice
from openai.types.chat.chat_completion_message import ChatCompletionMessage

from src.reverse.base_reverse import BaseReverse


load_dotenv()

BASE_URL = "https://chat.openai.com"
CHAT_URL = f"{BASE_URL}/backend-anon/conversation"
SESSION_URL = f"{BASE_URL}/backend-anon/sentinel/chat-requirements"

REFRESH_INTERVAL = int(os.environ.get('REFRESH_INTERVAL', 60))


class NewCompletionChoice(CompletionChoice):
	finish_reason: Any = None


class ChatGPTReverse(BaseReverse, ABC):

	llm_type = 'chatgpt'

	def __init__(self):
		self.token_tuple = (None, 0)
		super().__init__()

	def get_base_headers(self):
		base_headers = {
			"content-type": "application/json",
			"oai-language": "zh-CN",
			"sec-ch-ua": '"Google Chrome";v="123", "Not:A-Brand";v="8", "Chromium";v="123"',
			"user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
		}
		chatgpt_access_token = os.environ.get('CHATGPT_ACCESS_TOKEN')
		if chatgpt_access_token:
			base_headers['Authorization'] = f"Bearer {chatgpt_access_token}"
		return base_headers

	def generate_request_body(self, messages: list):
		body = {
			"action": "next",
			"messages": messages,
			"parent_message_id": str(uuid.uuid4()),
			"model": "text-davinci-002-render-sha",
			"timezone_offset_min": -180,
			"suggestions": [],
			"history_and_training_disabled": True,
			"conversation_mode": {"kind": "primary_assistant"},
			"websocket_request_id": str(uuid.uuid4())
		}
		return body

	def rev_exec_before(self):
		# get and refresh chat token
		cur_time = int(time.time())
		if cur_time - self.token_tuple[1] > REFRESH_INTERVAL:
			res = self.post_request(SESSION_URL, data={}, headers=self.get_base_headers(), proxies=self.proxy)
			token = res.json()['token']
			self.token_tuple = (token, cur_time)
			self.headers['Openai-Sentinel-Chat-Requirements-Token'] = self.token_tuple[0]

	def rev_exec(self, body: dict):
		response = self.post_request(CHAT_URL, json=body, headers=self.headers, proxies=self.proxy)
		return response

	def rev_exec_after(self):
		pass

	async def to_openai_async_iterator(self, chunks: Iterator) -> AsyncIterator:
		c_id = f"chatcmpl-{str(uuid.uuid4())}"

		per_parts = []

		for chunk in chunks:
			if not chunk:
				continue
			if chunk == b'data: [DONE]':
				yield "data: [DONE]\n"
				continue
			json_data = json.loads(chunk[len("data:"):])

			role = json_data['message']['author']['role']
			if role != "assistant":
				continue

			finish_reason = None
			if json_data['message']['status'] == 'finished_successfully':
				finish_reason = 'stop'

			choices = []
			parts = json_data['message']['content']['parts']
			for i, p in enumerate(parts):

				parts_len = len(per_parts)
				if parts_len > i:
					p = p[len(per_parts[i]):]

				choice = NewCompletionChoice(index=i, text=p, finish_reason=finish_reason)
				choices.append(choice)
			per_parts = parts

			completion = Completion(
				id=c_id,
				created=int(time.time()),
				choices=choices,
				model='gpt-3.5-turbo',
				object='text_completion'
			)
			yield f"data: {completion.model_dump_json(exclude_unset=True)}\n"

	def to_openai_nostream_content(self, chunks: Iterator):
		c_id = f"chatcmpl-{str(uuid.uuid4())}"

		for chunk in chunks:
			if not chunk or chunk == b'data: [DONE]':
				continue
			json_data = json.loads(chunk[len("data:"):])
			role = json_data['message']['author']['role']
			if role != "assistant":
				continue
			if json_data['message']['status'] == 'finished_successfully':
				choices = []
				parts = json_data['message']['content']['parts']
				for i, p in enumerate(parts):
					choice = NewCompletionChoice(index=i, text=p, finish_reason='stop')
					choices.append(choice)

				completion = Completion(
					id=c_id,
					created=int(time.time()),
					choices=choices,
					model='gpt-3.5-turbo',
					object='text_completion'
				)
				return completion.model_dump(exclude_unset=True)
		return None

	async def to_openai_chat_async_iterator(self, chunks: Iterator) -> AsyncIterator:
		c_id = f"chatcmpl-{str(uuid.uuid4())}"
		per_parts = []
		for chunk in chunks:
			if not chunk:
				continue
			if chunk == b'data: [DONE]':
				yield "data: [DONE]\n"
				continue
			json_data = json.loads(chunk[len("data:"):])

			role = json_data['message']['author']['role']
			if role != "assistant":
				continue

			choices = []
			parts = json_data['message']['content']['parts']
			for i, p in enumerate(parts):
				parts_len = len(per_parts)
				if parts_len > i:
					p = p[len(per_parts[i]):]
				delta = ChoiceDelta(role='assistant', content=p)
				if json_data['message']['status'] == 'finished_successfully':
					choice = ChatChunkChoice(index=i, delta=delta)
				else:
					choice = ChatChunkChoice(index=i, delta=delta, finish_reason='stop')
				choices.append(choice)
			per_parts = parts

			completion = ChatCompletionChunk(
				id=c_id,
				created=int(time.time()),
				choices=choices,
				model='gpt-3.5-turbo',
				object='chat.completion.chunk'
			)
			yield f"data: {completion.model_dump_json(exclude_unset=True)}\n"

	def to_openai_chat_nostream_content(self, chunks: Iterator):
		c_id = f"chatcmpl-{str(uuid.uuid4())}"
		for chunk in chunks:
			if not chunk or chunk == b'data: [DONE]':
				continue
			json_data = json.loads(chunk[len("data:"):])
			role = json_data['message']['author']['role']
			if role != "assistant":
				continue
			if json_data['message']['status'] == 'finished_successfully':
				choices = []
				parts = json_data['message']['content']['parts']
				for i, p in enumerate(parts):
					chat_msg = ChatCompletionMessage(role='assistant', content=p)
					choice = ChatChoice(index=i, message=chat_msg, finish_reason='stop')
					choices.append(choice)

				completion = ChatCompletion(
					id=c_id,
					created=int(time.time()),
					choices=choices,
					model='gpt-3.5-turbo',
					object='chat.completion'
				)
				return completion.model_dump(exclude_unset=True)
		return None

