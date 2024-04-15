import json
import re
import time
import asyncio
from aiohttp import ClientSession
from aiohttp import web


async def fetch(req):
    if req.method == "OPTIONS":
        return web.Response(body="", headers={'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*'}, status=204)

    body = {}
    try:
        body = await req.json()
    except:
        url_params = req.url.query
        body = {
            "messages": [{"role": "user", "content": url_params.get('q', 'hello')}],
            "model": "command-r",
            "temperature": 0.5,
            "presence_penalty": 0,
            "frequency_penalty": 0,
            "stream": True
        }

    data = {"chat_history": []}
    try:
        for i in range(len(body["messages"]) - 1):
            data["chat_history"].append({"role": "CHATBOT" if body["messages"][i]["role"] == "assistant" else body["messages"][i]["role"].upper(),
                                         "message": body["messages"][i]["content"]})
        data["message"] = body["messages"][-1]["content"]
    except Exception as e:
        return web.Response(text=str(e))

    data["stream"] = body.get("stream", False)

    if body["model"].startswith("net-"):
        data["connectors"] = [{"id": "web-search"}]
    for key, value in body.items():
        if not re.match(r"^(model|messages|stream)", key, re.IGNORECASE):
            data[key] = value
    if re.match(r"^(net-)?command", body["model"]):
        data["model"] = body["model"].replace("net-", "")
    if not data.get("model"):
        data["model"] = "command-r"

    headers = {'content-type': 'application/json'}
    if req.headers.get('authorization'):
        headers["Authorization"] = req.headers.get('authorization')
    else:
        url_params = req.url.query
        headers["Authorization"] = "bearer " + url_params.get('key')

    async with ClientSession() as session:
        async with session.post('https://api.cohere.ai/v1/chat', json=data, headers=headers) as resp:
            if resp.status != 200:
                return resp

            created = int(time.time())

            if not data["stream"]:
                try:
                    ddd = await resp.json()
                except Exception as e:
                    ddd = {"error": str(e)}
                response_data = {
                    "id": "chatcmpl-QXlha2FBbmROaXhpZUFyZUF3ZXNvbWUK",
                    "object": "chat.completion",
                    "created": created,
                    "model": data["model"],
                    "choices": [
                        {
                            "index": 0,
                            "delta": {
                                "role": "assistant",
                                "content": ddd.get("text", ddd.get("error"))
                            },
                            "logprobs": None,
                            "finish_reason": "stop"
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": 0
                    },
                    "system_fingerprint": None
                }
                headers = {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': '*'
                }
                return web.json_response(response_data, headers=headers, status=resp.status)

            async def stream_response(resp):
                writer = web.StreamResponse()
                writer.headers['Access-Control-Allow-Origin'] = '*'
                writer.headers['Access-Control-Allow-Headers'] = '*'
                writer.headers['Content-Type'] = 'text/event-stream; charset=UTF-8'
                await writer.prepare(req)

                async for chunk in resp.content.iter_any():
                    try:
                        chunk_str = chunk.decode('utf-8')
                    except UnicodeDecodeError:
                        try:
                            chunk_str = chunk.decode('latin-1')
                        except UnicodeDecodeError:
                            chunk_str = chunk.decode('gbk', errors='ignore')  # 忽略无法解码的字符

                    try:
                        chunk_json = json.loads(chunk_str)
                    except json.JSONDecodeError as e:
                        print(f"Failed to parse JSON chunk: {e}")
                        continue

                    wrapped_chunk = {
                        "id": "chatcmpl-QXlha2FBbmROaXhpZUFyZUF3ZXNvbWUK",
                        "object": "chat.completion",
                        "created": int(time.time()),
                        "model": data["model"],
                        "choices": [
                            {
                                "index": 0,
                                "delta": {
                                    "role": "assistant",
                                    "content": chunk_json.get("text", chunk_json.get("error"))
                                },
                                "finish_reason": "stop",
                            }
                        ],
                        "usage": {
                            "prompt_tokens": 0,
                            "completion_tokens": 0,
                            "total_tokens": 0
                        },
                        "system_fingerprint": None
                    }

                    event_data = f"data: {json.dumps(wrapped_chunk, ensure_ascii=False)}\n\n"
                    await writer.write(event_data.encode('utf-8'))

                return writer

            return await stream_response(resp)

async def onRequest(request):
    return await fetch(request)

async def sleep(ms):
    await asyncio.sleep(ms / 1000)

app = web.Application()
app.router.add_route("*", "/v1/chat/completions", onRequest)

if __name__ == '__main__':
    web.run_app(app, host='127.0.0.1', port=3030)