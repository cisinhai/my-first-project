import os
import time
import json
import http.client
from urllib.parse import urlparse
import subprocess
import re

# 全局变量，存储 AnythingLLM 工作区文件列表
anythingllm_files = []

# 读取 .env 文件
def load_env():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if not os.path.exists(env_path):
        print(f"[ERROR] 错误: .env 文件不存在，请放在当前脚本同一文件夹下")
        return None
    
    env_vars = {}
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                env_vars[key.strip()] = value.strip()
    return env_vars

# ====================== 工具函数 ======================
def list_files(directory):
    try:
        files = []
        for item in os.listdir(directory):
            item_path = os.path.join(directory, item)
            if os.path.isfile(item_path):
                file_info = {
                    "name": item,
                    "size": os.path.getsize(item_path),
                    "last_modified": os.path.getmtime(item_path),
                    "is_file": True
                }
            else:
                file_info = {"name": item, "is_file": False}
            files.append(file_info)
        return json.dumps({"success": True, "files": files}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

def rename_file(directory, old_name, new_name):
    try:
        old_path = os.path.join(directory, old_name)
        new_path = os.path.join(directory, new_name)
        if os.path.exists(old_path):
            os.rename(old_path, new_path)
            return json.dumps({"success": True, "message": f"文件已重命名为 {new_name}"}, ensure_ascii=False)
        else:
            return json.dumps({"success": False, "error": "文件不存在"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

def delete_file(directory, file_name):
    try:
        file_path = os.path.join(directory, file_name)
        if os.path.exists(file_path):
            os.remove(file_path)
            return json.dumps({"success": True, "message": "文件已删除"}, ensure_ascii=False)
        else:
            return json.dumps({"success": False, "error": "文件不存在"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

def create_file(directory, file_name, content=""):
    try:
        file_path = os.path.join(directory, file_name)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return json.dumps({"success": True, "message": f"文件 {file_name} 已创建成功"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

def read_file(directory, file_name):
    try:
        file_path = os.path.join(directory, file_name)
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return json.dumps({"success": True, "content": content}, ensure_ascii=False)
        else:
            return json.dumps({"success": False, "error": "文件不存在"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

def curl_request(url):
    try:
        result = subprocess.run(['curl', '-s', url], capture_output=True, timeout=30)
        if result.returncode == 0:
            try:
                content = result.stdout.decode('utf-8')
            except UnicodeDecodeError:
                content = result.stdout.decode('gbk', errors='replace')
            return json.dumps({"success": True, "content": content}, ensure_ascii=False)
        else:
            try:
                error = result.stderr.decode('utf-8')
            except UnicodeDecodeError:
                error = result.stderr.decode('gbk', errors='replace')
            return json.dumps({"success": False, "error": error}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

# ====================== AnythingLLM 查询 ======================
def anythingllm_query(query):
    try:
        env_vars = load_env()
        if not env_vars:
            return json.dumps({"success": False, "error": ".env 文件不存在"}, ensure_ascii=False)

        api_key = env_vars.get('ANYTHINGLLM_API_KEY')
        workspace_slug = env_vars.get('ANYTHINGLLM_WORKSPACE_SLUG')
        base_url = env_vars.get('ANYTHING_LLM_BASE_URL', 'http://localhost:3001')

        if not api_key or not workspace_slug:
            return json.dumps({"success": False, "error": "缺少配置"}, ensure_ascii=False)

        url = urlparse(base_url)
        conn = http.client.HTTPConnection(url.netloc, timeout=10)

        data = json.dumps({"message": query})
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

        path = f"{url.path.rstrip('/')}/api/v1/workspace/{workspace_slug}/chat"
        if path.startswith('/'):
            path = path[1:]

        conn.request("POST", f"/{path}", data, headers)
        response = conn.getresponse()
        content = response.read().decode('utf-8')
        conn.close()

        if 200 <= response.status < 300:
            return json.dumps({"success": True, "content": content}, ensure_ascii=False)
        else:
            return json.dumps({"success": False, "error": f"HTTP {response.status}"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

# ====================== 获取 AnythingLLM 工作区文件列表 ======================
def get_anythingllm_files():
    try:
        env_vars = load_env()
        if not env_vars:
            return []

        api_key = env_vars.get('ANYTHINGLLM_API_KEY')
        workspace_slug = env_vars.get('ANYTHINGLLM_WORKSPACE_SLUG')
        base_url = env_vars.get('ANYTHING_LLM_BASE_URL', 'http://localhost:3001')

        if not api_key or not workspace_slug:
            return []

        url = urlparse(base_url)
        conn = http.client.HTTPConnection(url.netloc, timeout=10)

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

        # 尝试获取工作区文件列表（使用适当的 API 端点）
        path = f"{url.path.rstrip('/')}/api/v1/workspace/{workspace_slug}/documents"
        if path.startswith('/'):
            path = path[1:]

        conn.request("GET", f"/{path}", headers=headers)
        response = conn.getresponse()
        content = response.read().decode('utf-8')
        conn.close()

        if 200 <= response.status < 300:
            try:
                data = json.loads(content)
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict) and 'documents' in data:
                    return data['documents']
                else:
                    # 如果无法解析，返回空列表
                    return []
            except json.JSONDecodeError:
                return []
        else:
            return []
    except Exception as e:
        return []

# ====================== 搜索聊天历史 ======================
def search_chat_history(query):
    try:
        log_dir = r"D:\chat-log"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        log_file = os.path.join(log_dir, "log.txt")
        if not os.path.exists(log_file):
            with open(log_file, 'w', encoding='utf-8') as f:
                f.write("# 聊天历史关键信息\n")

        with open(log_file, 'r', encoding='utf-8') as f:
            content = f.read()

        return json.dumps({"success": True, "content": content, "query": query}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

# ====================== 工具定义 ======================
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "列出指定目录下的所有文件和文件夹",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "要列出的目录路径，例如 D:\\test"
                    }
                },
                "required": ["directory"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_file",
            "description": "在指定目录下创建一个新文件并写入内容",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "文件所在的目录路径"
                    },
                    "file_name": {
                        "type": "string",
                        "description": "要创建的文件名，例如 test.txt"
                    },
                    "content": {
                        "type": "string",
                        "description": "要写入文件的内容，默认为空字符串",
                        "default": ""
                    }
                },
                "required": ["directory", "file_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_file",
            "description": "删除指定目录下的指定文件",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "文件所在的目录路径"
                    },
                    "file_name": {
                        "type": "string",
                        "description": "要删除的文件名"
                    }
                },
                "required": ["directory", "file_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rename_file",
            "description": "重命名指定目录下的文件",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "文件所在的目录路径"
                    },
                    "old_name": {
                        "type": "string",
                        "description": "原文件名"
                    },
                    "new_name": {
                        "type": "string",
                        "description": "新文件名"
                    }
                },
                "required": ["directory", "old_name", "new_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取指定目录下文件的内容",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "文件所在的目录路径"
                    },
                    "file_name": {
                        "type": "string",
                        "description": "要读取的文件名"
                    }
                },
                "required": ["directory", "file_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "curl_request",
            "description": "访问指定的网页URL并返回内容",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "要访问的网页URL，例如 https://www.baidu.com"
                    }
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_chat_history",
            "description": "搜索聊天历史记录，当用户需要查找聊天历史时使用",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "用户的搜索查询，例如 '查找关于文件操作的记录'"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "anythingllm_query",
            "description": "查询 AnythingLLM 工作区聊天助手，当用户询问 AnythingLLM 相关问题或需要查询特定知识时使用",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "要查询的问题或话题"
                    }
                },
                "required": ["query"]
            }
        }
    }
]

# ====================== 系统提示词 ======================
def build_system_prompt(user_info):
    global anythingllm_files
    file_count = len(anythingllm_files)
    return f"""你是我的个人助手，请记住我的身份信息：{user_info}
要求：
1. 不要提及你的模型名称或公司信息
2. 回答要简洁准确
3. 可以调用工具来帮助完成任务
4. 默认将 AnythingLLM 工作区作为"我的仓库"
5. 当用户询问"我的仓库里有多少文件"或类似问题时，直接返回 AnythingLLM 工作区的文件数量：{file_count}
6. 所有和"文件数量"、"仓库文件"相关的问题，直接返回 AnythingLLM 里的文件数量
7. 其他所有问题，都调用 AnythingLLM 的知识库 API 回答，不要出现反问用户路径的情况"""

# ====================== 流式调用（彻底修复版） ======================
def call_llm_stream(env_vars, messages, user_info, is_tool_round=False):
    start_time = time.time()
    url = urlparse(env_vars['BASE_URL'])
    host = url.netloc
    base_path = url.path.rstrip('/')
    path = f"{base_path}/chat/completions"

    # 添加系统提示
    system_msg = {"role": "system", "content": build_system_prompt(user_info)}
    final_messages = [system_msg] + messages

    data = {
        "model": env_vars["MODEL"],
        "messages": final_messages,
        "tools": TOOLS,
        "tool_choice": "auto",
        "temperature": 0.7,
        "max_tokens": int(env_vars.get("MAX_TOKENS", 2048)),
        "stream": True
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {env_vars.get('API_KEY', '')}"
    }

    timeout = int(env_vars.get('TIMEOUT', '120'))
    
    if url.scheme == 'https':
        conn = http.client.HTTPSConnection(host, timeout=timeout)
    else:
        conn = http.client.HTTPConnection(host, timeout=timeout)

    full_content = ""
    tool_calls = []
    has_content = False

    try:
        conn.request("POST", path, json.dumps(data), headers)
        response = conn.getresponse()
        
        # 检查HTTP状态码
        if response.status != 200:
            try:
                error_content = response.read().decode('utf-8')
            except:
                try:
                    error_content = response.read().decode('latin-1')
                except:
                    error_content = "无法解码错误信息"
            print(f"\n[ERROR] HTTP {response.status}: {error_content}")
            return None, None, 0, 0, 0

        if not is_tool_round:
            print("[AI] AI 正在思考...", end="", flush=True)

        # 改进的JSON解析：累积缓冲区，逐行处理
        buffer = ""
        partial_json = ""
        break_processing = False
        
        for chunk in response.fp:
            try:
                chunk_str = chunk.decode('utf-8')
            except UnicodeDecodeError:
                try:
                    chunk_str = chunk.decode('latin-1')
                except:
                    continue
            
            buffer += chunk_str
            
            # 按行分割
            while '\n' in buffer:
                line_end = buffer.find('\n')
                line = buffer[:line_end].strip()
                buffer = buffer[line_end + 1:]
                
                if not line:
                    continue
                
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        # 收到结束标志，跳出所有循环
                        break_processing = True
                        break
                    
                    # 累积可能不完整的JSON
                    partial_json += data_str
                    
                    # 尝试解析完整的JSON对象
                    try:
                        # 尝试解析累积的JSON
                        jd = json.loads(partial_json)
                        # 解析成功，清空累积器
                        partial_json = ""
                        
                        if "choices" in jd and len(jd["choices"]) > 0:
                            delta = jd["choices"][0].get("delta", {})
                            
                            # 处理内容
                            if "content" in delta and delta["content"]:
                                token = delta["content"]
                                full_content += token
                                has_content = True
                                if not is_tool_round and not tool_calls:
                                    if not has_content or len(full_content) == len(token):
                                        print("\r" + " " * 30 + "\r", end="", flush=True)
                                        print("[AI] AI 回复：", end="", flush=True)
                                    print(token, end="", flush=True)
                            
                            # 处理工具调用
                            if "tool_calls" in delta and delta["tool_calls"]:
                                for tc in delta["tool_calls"]:
                                    index = tc.get("index", 0)
                                    while index >= len(tool_calls):
                                        tool_calls.append({
                                            "id": "",
                                            "type": "function",
                                            "function": {
                                                "name": "",
                                                "arguments": ""
                                            }
                                        })
                                    
                                    if "id" in tc and tc["id"]:
                                        tool_calls[index]["id"] = tc["id"]
                                    
                                    if "function" in tc:
                                        if "name" in tc["function"] and tc["function"]["name"]:
                                            tool_calls[index]["function"]["name"] += tc["function"]["name"]
                                        if "arguments" in tc["function"] and tc["function"]["arguments"]:
                                            tool_calls[index]["function"]["arguments"] += tc["function"]["arguments"]
                    except json.JSONDecodeError as e:
                        # JSON不完整，继续累积
                        # 但如果累积器太大（超过10KB），清空它避免内存问题
                        if len(partial_json) > 10240:
                            partial_json = ""
                        # 不再打印错误信息，避免干扰用户
                        pass
                
            # 检查是否需要跳出外层循环
            if break_processing:
                break

        if not is_tool_round and has_content:
            print("\n")
        elif not is_tool_round and not has_content and not tool_calls:
            print("\n[WARN] AI 未返回任何内容")

    except Exception as e:
        print(f"\n[ERROR] 连接失败：{str(e)}")
        return None, None, 0, 0, 0
    finally:
        conn.close()

    duration = time.time() - start_time
    total_tokens = len(full_content) // 3 if full_content else 0
    speed = total_tokens / duration if duration > 0 else 0

    if tool_calls:
        for tc in tool_calls:
            if not tc["function"]["arguments"]:
                tc["function"]["arguments"] = "{}"
    
    return full_content, tool_calls, total_tokens, duration, speed

# ====================== 自动提取用户身份信息 ======================
def extract_user_info(messages):
    user_info = []
    for msg in messages:
        if msg["role"] == "user":
            content = msg["content"]
            if "我是" in content:
                user_info.append(content.split("我是", 1)[1].strip())
            elif "我叫" in content:
                user_info.append(content.split("我叫", 1)[1].strip())
    
    user_info = list(set(user_info))
    if not user_info:
        return "普通用户"
    return "，".join(user_info)

# ====================== 保存关键信息 ======================
def save_key_information(user_question, ai_answer, user_info):
    log_dir = r"D:\chat-log"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    log_file = os.path.join(log_dir, "log.txt")
    if not os.path.exists(log_file):
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write("# 聊天历史关键信息\n")
    
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"\n=== {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
        f.write(f"用户身份：{user_info}\n")
        f.write(f"用户提问：{user_question}\n")
        f.write(f"AI回答：{ai_answer}\n")

# ====================== 聊天历史压缩 ======================
def compress_chat_history(messages):
    if len(messages) <= 10:
        return messages
    
    print("\n[INFO] 检测到聊天历史过长，开始压缩...")
    messages_to_keep = messages[-10:]
    print("[OK] 聊天历史压缩完成")
    return messages_to_keep

# ====================== 主循环 ======================
def main():
    global anythingllm_files
    env_vars = load_env()
    if not env_vars: 
        return

    # 移除调试输出
    print("=" * 50)
    print("[OK] AI 工具助手已启动")
    print(f"模型：{env_vars['MODEL']}")
    print(f"地址：{env_vars['BASE_URL']}")
    print("=" * 50)

    # 启动时获取 AnythingLLM 工作区文件列表
    anythingllm_files = get_anythingllm_files()

    messages = []
    user_info = "普通用户"

    while True:
        prompt = input("\n请输入问题（输入 exit 退出）：")
        if prompt.lower() == "exit": 
            break

        # 检查是否是文件数量相关问题
        file_count_patterns = [
            "多少文件", "文件数量", "仓库文件", "我的仓库", "文件个数",
            "有多少文件", "仓库中有多少文件", "工作区文件"
        ]
        is_file_count_question = any(pattern in prompt for pattern in file_count_patterns)

        if is_file_count_question:
            # 直接返回文件数量
            file_count = len(anythingllm_files)
            response = f"您的仓库中有 {file_count} 个文件"
            print(f"[AI] AI 回复：{response}")
            save_key_information(prompt, response, user_info)
            messages.append({"role": "assistant", "content": response})
            print("=" * 50)
            print(f"⏱ 耗时：0.00s  |  📊 Tokens：0  |  ⚡ 速度：0.00 token/s")
            print("=" * 50)
        else:
            # 其他问题，调用 AnythingLLM API
            print("[AI] AI 正在思考...", end="", flush=True)
            result = anythingllm_query(prompt)
            try:
                result_data = json.loads(result)
                if result_data.get("success"):
                    # 尝试解析 AnythingLLM 的响应
                    try:
                        anythingllm_response = json.loads(result_data.get("content", "{}"))
                        if isinstance(anythingllm_response, dict):
                            # 检查是否有 textResponse 字段
                            if "textResponse" in anythingllm_response:
                                response = anythingllm_response["textResponse"]
                            # 检查是否有 message 字段
                            elif "message" in anythingllm_response:
                                response = anythingllm_response["message"]
                            else:
                                # 尝试提取字符串内容
                                response = str(anythingllm_response)
                        else:
                            response = result_data.get("content", "")
                    except json.JSONDecodeError:
                        response = result_data.get("content", "")
                    # 清理响应内容，移除可能的 JSON 结构
                    if isinstance(response, str):
                        # 移除可能的 JSON 标记
                        response = response.strip()
                        # 如果是完整的 JSON 字符串，尝试提取文本
                        if response.startswith('{') and response.endswith('}'):
                            try:
                                json_response = json.loads(response)
                                if "textResponse" in json_response:
                                    response = json_response["textResponse"]
                                elif "message" in json_response:
                                    response = json_response["message"]
                            except json.JSONDecodeError:
                                pass
                    print(f"\r" + " " * 30 + "\r", end="", flush=True)
                    print(f"[AI] AI 回复：{response}")
                    save_key_information(prompt, response, user_info)
                    messages.append({"role": "assistant", "content": response})
                    print("=" * 50)
                    print(f"⏱ 耗时：0.00s  |  📊 Tokens：0  |  ⚡ 速度：0.00 token/s")
                    print("=" * 50)
                else:
                    print(f"\r" + " " * 30 + "\r", end="", flush=True)
                    print(f"[AI] AI 回复：抱歉，暂时无法回答您的问题")
                    save_key_information(prompt, "抱歉，暂时无法回答您的问题", user_info)
                    messages.append({"role": "assistant", "content": "抱歉，暂时无法回答您的问题"})
                    print("=" * 50)
                    print(f"⏱ 耗时：0.00s  |  📊 Tokens：0  |  ⚡ 速度：0.00 token/s")
                    print("=" * 50)
            except json.JSONDecodeError:
                print(f"\r" + " " * 30 + "\r", end="", flush=True)
                print(f"[AI] AI 回复：抱歉，暂时无法回答您的问题")
                save_key_information(prompt, "抱歉，暂时无法回答您的问题", user_info)
                messages.append({"role": "assistant", "content": "抱歉，暂时无法回答您的问题"})
                print("=" * 50)
                print(f"⏱ 耗时：0.00s  |  📊 Tokens：0  |  ⚡ 速度：0.00 token/s")
                print("=" * 50)

if __name__ == "__main__":
    main()