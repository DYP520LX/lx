import configparser
import json
import urllib.request

cfg = configparser.ConfigParser()
cfg.read("config.ini", encoding="utf-8")
base_url = cfg.get("llm", "base_url").rstrip("/")
api_key = cfg.get("llm", "api_key")
model = cfg.get("llm", "model")
stream = cfg.get("llm", "stream").lower() == "true"

messages = []
while True:
    question = input("你：")
    messages.append({"role": "user", "content": question})
    body = {
        "model": model,
        "messages": messages,
        "stream": stream,
    }
    req = urllib.request.Request(
        base_url + "/chat/completions",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        method="POST",
    )
    req.add_header("Authorization", "Bearer " + api_key)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as resp:
        if not stream:
            data = json.loads(resp.read().decode("utf-8"))
            reply = data["choices"][0]["message"]["content"]
            print(reply)
        else:
            parts = []
            for raw in resp:
                line = raw.decode("utf-8").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                piece = json.loads(data)["choices"][0]["delta"].get("content") or ""
                if piece:
                    parts.append(piece)
                    print(piece, end="", flush=True)
            reply = "".join(parts)
            print()
    messages.append({"role": "assistant", "content": reply})
