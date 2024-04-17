import os

import uvicorn
from dotenv import load_dotenv

from api_proxy import app
from api_proxy import router

load_dotenv()

if __name__ == '__main__':
    app.include_router(router)
    port = int(os.environ.get('SERVER_PORT', 6080))
    uvicorn.run(app, host="127.0.0.1", port=port)
