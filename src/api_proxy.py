
import os
import sys
import time
import uuid

import requests

from fastapi import FastAPI, Request
from dotenv import load_dotenv
from starlette.responses import StreamingResponse

sys.path.append(".")
sys.path.append("..")
from src import chatgpt_adapter

load_dotenv()


BASE_URL = "https://chat.openai.com"
CHAT_URL = f"{BASE_URL}/backend-anon/conversation"
SESSION_URL = f"{BASE_URL}/backend-anon/sentinel/chat-requirements"

REFRESH_INTERVAL = int(os.environ.get('REFRESH_INTERVAL', 60))

app = FastAPI()

token_tuple = (None, 0)


@app.get('/')
async def application():
    return "I'm GPT API Proxy"


@app.post('/v1/completions')
async def completion(req: Request):
    headers = get_base_headers()
    proxy = get_proxy_info()
    await refresh_chat_token(headers, proxy)
    headers['Openai-Sentinel-Chat-Requirements-Token'] = token_tuple[0]

    request_body = await req.json()
    prompt = request_body['prompt']

    prompts = []
    if isinstance(prompt, str):
        prompts.append(prompt)
    elif isinstance(prompt, list):
        prompts.extend(prompt)

    messages = []
    for p in prompts:
        msg_temp = {
            "author": {"role": "user"},
            "content": {"content_type": "text", "parts": [p]}
        }
        messages.append(msg_temp)

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

    is_stream = request_body.get('stream')
    response = post_request(CHAT_URL, json=body, headers=headers, proxies=proxy)
    return openai_data_format(response, is_stream)


@app.post('/v1/chat/completions')
async def chat_completion(req: Request):
    headers = get_base_headers()
    proxy = get_proxy_info()

    await refresh_chat_token(headers, proxy)
    headers['Openai-Sentinel-Chat-Requirements-Token'] = token_tuple[0]

    request_body = await req.json()

    body = {
        "action": "next",
        "messages": [
          {
            "author": {"role": message["role"]},
            "content": {"content_type": "text", "parts": [message["content"]]},
          }
          for message in request_body["messages"]
        ],
        "parent_message_id": str(uuid.uuid4()),
        "model": "text-davinci-002-render-sha",
        "timezone_offset_min": -180,
        "suggestions": [],
        "history_and_training_disabled": True,
        "conversation_mode": {"kind": "primary_assistant"},
        "websocket_request_id": str(uuid.uuid4())
    }

    is_stream = request_body.get('stream')
    response = post_request(CHAT_URL, json=body, headers=headers, proxies=proxy)
    return openai_data_format(response, is_stream, is_chat=True)


async def refresh_chat_token(headers, proxy):
    global token_tuple
    # get and refresh chat token
    cur_time = int(time.time())
    if cur_time - token_tuple[1] > REFRESH_INTERVAL:
        res = post_request(SESSION_URL, data={}, headers=headers, proxies=proxy)
        token = res.json()['token']
        token_tuple = (token, cur_time)


def post_request(url, data=None, headers=None, proxies=None, **kwargs):
    response = requests.post(url, data=data, headers=headers, proxies=proxies, **kwargs)
    response.raise_for_status()
    return response


def openai_data_format(response, is_stream=False, is_chat=False):
    if is_stream:
        media_type = "text/event-stream"
        res_headers = {"Cache-Control": "no-cache", "Connection": "keep-alive"}
        if is_chat:
            async_iter = chatgpt_adapter.to_openai_chat_async_iterator(response.iter_lines())
        else:
            async_iter = chatgpt_adapter.to_openai_async_iterator(response.iter_lines())
        return StreamingResponse(
            async_iter,
            media_type=media_type,
            headers=res_headers)
    else:
        if is_chat:
            content = chatgpt_adapter.to_openai_chat_nostream_content(response.iter_lines())
        else:
            content = chatgpt_adapter.to_openai_nostream_content(response.iter_lines())
        return content


def get_base_headers():
    headers = {
        "accept": "*/*",
        "accept-language": "zh-CN,zh;q=0.9",
        "cache-control": "no-cache",
        "content-type": "application/json",
        "oai-language": "zh-CN",
        "origin": BASE_URL,
        "pragma": "no-cache",
        "referer": BASE_URL,
        "sec-ch-ua": '"Google Chrome";v="123", "Not:A-Brand";v="8", "Chromium";v="123"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "macOS",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    chatgpt_access_token = os.environ.get('CHATGPT_ACCESS_TOKEN')
    if chatgpt_access_token:
        headers['Authorization'] = f"Bearer {chatgpt_access_token}"
    return headers


def get_proxy_info():
    proxy = {}
    enable = os.environ.get('PROXY_ENABLE', 'false')
    if enable and enable.upper() == 'TRUE':
        proxy_host = os.environ.get('PROXY_HOST')
        proxy_port = os.environ.get('PROXY_PORT')
        proxy['http'] = f"http://{proxy_host}:{proxy_port}"
        proxy['https'] = f"http://{proxy_host}:{proxy_port}"
    return proxy
