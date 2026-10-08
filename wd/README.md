# wd

这个文件夹对应本机目录 `D:\学习\wd`，里面是课程里的最小可用练习。

## 内容

- `PetHospitalServer`：宠物医院可执行程序。双击 `pethospital.exe`，地址是 http://127.0.0.1:8080/
- `PetHospitalMCP`：宠物医院 MCP，只提供 `list_pets`。运行 `python server.py`，地址是 http://127.0.0.1:8081/mcp
- `AnythingLLMMCP`：读取 AnythingLLM 第一个工作区的文件信息。运行 `python server.py`，地址是 http://127.0.0.1:8082/mcp
- `AnythingLLMWebPage`：给第一个工作区上传文件并做向量嵌入。运行 `python server.py`，打开 http://127.0.0.1:8083/
- `Playground`：两个 MCP 的配置，以及 AnythingLLM 的 `baseUrl` 和 `apiKey`
- `Agent\Practice01`：最简单的大模型对话。先在该目录填写 `config.ini`，再运行 `python chat.py`。`stream = false` 是一次性输出，`true` 是打字机输出。Ctrl+C 退出

## 说明

AnythingLLM 需要本机先启动，并在 `Playground\anythingllm.json` 填入自己的密钥。`Practice01\config.ini` 里当前用的是一个不校验密钥的公共免费接口，不保证一直可用。
