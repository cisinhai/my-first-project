import os
import time
import json
import http.client
from urllib.parse import urlparse

# 读取 .env 文件
def load_env():
    """从项目根目录的 .env 文件加载环境变量"""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if not os.path.exists(env_path):
        print(f"错误: .env 文件不存在，请创建并配置")
        return None
    
    env_vars = {}
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                key, value = line.split('=', 1)
                env_vars[key.strip()] = value.strip()
    return env_vars

# 流式调用 LM Studio
def call_llm_stream(env_vars, prompt):
    start_time = time.time()
    url = urlparse(env_vars['BASE_URL'])
    host = url.netloc
    path = "/v1/chat/completions"

    # 流式输出核心：stream=True
    data = {
        "model": env_vars["MODEL"],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": float(env_vars.get("TEMPERATURE", 0.7)),
        "max_tokens": int(env_vars.get("MAX_TOKENS", 10000)),
        "stream": True
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {env_vars.get('API_KEY', '')}"
    }

    # 使用 HTTP + 超长超时
    conn = http.client.HTTPConnection(host, timeout=120)
    full_content = ""

    try:
        conn.request("POST", path, json.dumps(data), headers)
        response = conn.getresponse()

        print("AI 正在思考并回复：", end="", flush=True)

        # 逐字流式输出
        for line in response.fp:
            line = line.decode("utf-8").strip()
            if not line:
                continue
            if line.startswith("data: "):
                data_part = line[6:]
                if data_part == "[DONE]":
                    break
                try:
                    json_data = json.loads(data_part)
                    token = json_data["choices"][0]["delta"].get("content", "")
                    if token:
                        print(token, end="", flush=True)
                        full_content += token
                except:
                    continue

        print("\n")
    except Exception as e:
        print(f"连接失败：{str(e)}")
        return None, 0, 0, 0
    finally:
        conn.close()

    duration = time.time() - start_time
    total_tokens = len(full_content) // 3
    token_speed = total_tokens / duration if duration > 0 else 0
    return full_content, total_tokens, duration, token_speed

def main():
    env_vars = load_env()
    if not env_vars:
        return

    prompt = input("请输入你的问题：")

    print("=" * 60)
    print("✅ 已连接本地大模型")
    print(f"模型：{env_vars['MODEL']}")
    print(f"地址：{env_vars['BASE_URL']}")
    print("=" * 60)

    content, total_tokens, duration, token_speed = call_llm_stream(env_vars, prompt)

    if content:
        print("=" * 60)
        print(f"✅ 回复完成！")
        print(f"耗时：{duration:.2f}s")
        print(f"总Tokens：{total_tokens}")
        print(f"速度：{token_speed:.2f} tokens/s")

if __name__ == "__main__":
    main()