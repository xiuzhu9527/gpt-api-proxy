#!/bin/bash

CMD_HOME=`pwd`

# init config
grep -v "CHATGPT_ACCESS_TOKEN" $CMD_HOME/.env.template > $CMD_HOME/.env
ACCESS_TOKEN_ENV="${CHATGPT_ACCESS_TOKEN:-}"
if [ -n "$ACCESS_TOKEN_ENV" ]; then
    echo "CHATGPT_ACCESS_TOKEN=${ACCESS_TOKEN_ENV}" >> .env
fi

