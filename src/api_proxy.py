
import os
import sys
import logging

from fastapi import FastAPI, Request, HTTPException
from dotenv import load_dotenv

sys.path.append(".")
sys.path.append("..")
from src.reverse.base_reverse import BaseReverse

logger = logging.getLogger(__name__)

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
    try:
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

        is_stream = request_body.get('stream')

        model = request_body.get('model')
        reverse_instance = get_reverse_by_model(model)
        return await reverse_instance.do_run(messages, is_stream=is_stream)
    except Exception as e:
        error_msg = f"error: {str(e)}"
        logger.error(error_msg)
        print("print: " + error_msg)
        raise HTTPException(status_code=1004, detail=error_msg)


@app.post('/v1/chat/completions')
async def chat_completion(req: Request):
    try:
        request_body = await req.json()
        is_stream = request_body.get('stream')
        messages = [
            {
                "author": {"role": message["role"]},
                "content": {"content_type": "text", "parts": [message["content"]]},
            }
            for message in request_body["messages"]
        ]

        model = request_body.get('model')
        reverse_instance = get_reverse_by_model(model)
        return await reverse_instance.do_run(messages, is_stream=is_stream, is_chat=True)
    except Exception as e:
        error_msg = f"error: {str(e)}"
        logger.error(error_msg)
        print("print: " + error_msg)
        raise HTTPException(status_code=1004, detail=error_msg)


def get_reverse_by_model(model: str):
    llm_type = 'chatgpt'
    if model.startswith('claude'):
        llm_type = 'claude'
    return get_instance_by_type(llm_type)


def get_instance_by_type(llm_type):
    subclasses = BaseReverse.__subclasses__()
    for subclass in subclasses:
        if subclass.llm_type == llm_type:
            instance = subclass()
            return instance
