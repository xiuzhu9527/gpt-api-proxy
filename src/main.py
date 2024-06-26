import os
import sys

import uvicorn
from dotenv import load_dotenv

sys.path.append(".")
sys.path.append("..")
from src.api_proxy import app

load_dotenv()

if __name__ == '__main__':
	port = int(os.environ.get('SERVER_PORT', 6080))
	uvicorn.run(app, host="127.0.0.1", port=port)
