import uuid
import json
import time
from typing import Iterator, AsyncIterator, Any

from openai.types import Completion, CompletionChoice
from openai.types.chat import ChatCompletion, ChatCompletionChunk
from openai.types.chat.chat_completion_chunk import Choice as ChatChunkChoice
from openai.types.chat.chat_completion_chunk import ChoiceDelta
from openai.types.chat.chat_completion import Choice as ChatChoice
from openai.types.chat.chat_completion_message import ChatCompletionMessage


class NewCompletionChoice(CompletionChoice):
	finish_reason: Any = None


async def to_openai_async_iterator(chunks: Iterator) -> AsyncIterator:
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


def to_openai_nostream_content(chunks: Iterator):
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


async def to_openai_chat_async_iterator(chunks: Iterator) -> AsyncIterator:
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


def to_openai_chat_nostream_content(chunks: Iterator):
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

