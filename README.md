# GPT-API-Proxy


> 声明：本项目基于GPL-3.0协议，仅供学习研究使用，不允许用做商业行为。

## 关于
GPT-API-Proxy是一个免费的ChatGPT API反向代理，提供对ChatGPT3.5、Claude3-sonnet等模型免费的API自托管访问。采用逆向工程的思想，绕过前端直接调用后端的接口。

## 功能
+ 支持open api流式和非流式的访问
+ 支持ChatGPT3.5
+ 支持Claude3-sonnet

## 部署
> - 在国内ChatGPT、Claude均被墙所以请自行解决科学上网或者有国外服务器
> - python version >= 3.9

### 手动部署
Setp1: 下载项目到本地或者服务器
```shell
git clone https://github.com/xiuzhu9527/gpt-api-proxy.git
```

Setp2: 创建.env文件，设置配置参数
```shell
cd gpt-api-proxy
cp .env.template .env
```
如果在科学上网的环境下需要设置PROXY_ENABLE=true, 并设置PROXY_HOST和PROXY_PORT，一般PROXY_HOST为127.0.0.1，PROXY_PORT需要查看所使用的VPN软件代理设置的端口是多少
如果需要配置访问ChatGPT，则设置参数CHATGPT_ACCESS_TOKEN，access token访问https://chat.openai.com/api/auth/session获取
如果需要配置访问Claude, 则设置参数CLAUDE_SESSION_KEY，可以从claude web控制台的Cookie中获取

Setp3：启动
```shell
python src/main.py
```
