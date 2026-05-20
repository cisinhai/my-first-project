import os
import time
import json
import http.client
from urllib.parse import urlparse

# 技能目录路径
SKILLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.agents', 'skills')

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

# ====================== 技能管理函数 ======================

def list_available_skills():
    """
    读取 .agents/skills 目录下的所有一级子目录，提取每个技能的 name 和 description
    """
    skills = []
    
    if not os.path.exists(SKILLS_DIR):
        print(f"[WARN] 技能目录不存在: {SKILLS_DIR}")
        return skills
    
    try:
        for skill_dir in os.listdir(SKILLS_DIR):
            skill_path = os.path.join(SKILLS_DIR, skill_dir)
            if os.path.isdir(skill_path):
                skill_file = os.path.join(skill_path, 'SKILL.md')
                if os.path.exists(skill_file):
                    try:
                        with open(skill_file, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        # 提取 YAML front matter (--- 之间的内容)
                        if content.startswith('---'):
                            end_index = content.find('---', 3)
                            if end_index != -1:
                                front_matter = content[3:end_index].strip()
                                # 解析 YAML 格式的 name 和 description
                                name = ''
                                description = ''
                                for line in front_matter.split('\n'):
                                    if line.startswith('name:'):
                                        name = line.split(':', 1)[1].strip().strip('"').strip("'")
                                    elif line.startswith('description:'):
                                        description = line.split(':', 1)[1].strip().strip('"').strip("'")
                                
                                if name:
                                    skills.append({
                                        'name': name,
                                        'description': description
                                    })
                    except Exception as e:
                        print(f"[WARN] 读取技能文件失败 {skill_file}: {str(e)}")
        print(f"[OK] 成功加载 {len(skills)} 个技能")
    except Exception as e:
        print(f"[ERROR] 读取技能目录失败: {str(e)}")
    
    return skills

def load_skill_content(skill_name):
    """
    加载指定技能的正文内容（YAML front matter 之后的部分）
    """
    try:
        # 查找匹配的技能目录
        for skill_dir in os.listdir(SKILLS_DIR):
            skill_path = os.path.join(SKILLS_DIR, skill_dir)
            if os.path.isdir(skill_path):
                skill_file = os.path.join(skill_path, 'SKILL.md')
                if os.path.exists(skill_file):
                    with open(skill_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # 提取 YAML front matter 中的 name
                    if content.startswith('---'):
                        end_index = content.find('---', 3)
                        if end_index != -1:
                            front_matter = content[3:end_index].strip()
                            for line in front_matter.split('\n'):
                                if line.startswith('name:'):
                                    current_name = line.split(':', 1)[1].strip().strip('"').strip("'")
                                    if current_name == skill_name:
                                        # 返回 YAML front matter 之后的内容
                                        return content[end_index+3:].strip()
        print(f"[WARN] 未找到技能: {skill_name}")
        return None
    except Exception as e:
        print(f"[ERROR] 加载技能内容失败 {skill_name}: {str(e)}")
        return None

# ====================== 系统提示词构建 ======================
def build_system_prompt(user_info, skills_json):
    return f"""你是我的个人助手，请记住我的身份信息：{user_info}

你可以使用以下技能来帮助完成任务：
{skills_json}

当用户的请求涉及撰写、修改或润色通知时，请使用"通知撰写助手"技能。

要求：
1. 不要提及你的模型名称或公司信息
2. 回答要简洁准确
3. 可以调用工具来帮助完成任务
4. 当用户询问与通知相关的任务时，请使用通知撰写助手技能，并按照技能要求生成通知
5. 通知不能以"通知"二字开头，必须冠以部门前缀，如"采购部通知""宣传部通知"等
6. 如果用户没有告知所在部门，就使用"XX部"代替
7. 所有其他问题，根据上下文直接回答"""

# ====================== 检查是否需要使用技能 ======================
def check_skill_needed(user_input, skills):
    """
    检查用户输入是否需要使用某个技能
    返回需要使用的技能名称，如果不需要则返回 None
    """
    user_input_lower = user_input.lower()
    
    # 检查通知相关的请求
    notice_keywords = ['通知', '写通知', '撰写通知', '修改通知', '润色通知']
    for keyword in notice_keywords:
        if keyword in user_input:
            for skill in skills:
                if '通知' in skill.get('name', '') or '通知' in skill.get('description', ''):
                    return skill.get('name')
    
    return None

# ====================== 构建带技能的提示词 ======================
def build_prompt_with_skill(user_input, skill_name):
    """
    构建包含技能内容的提示词
    """
    skill_content = load_skill_content(skill_name)
    if skill_content:
        return f"""根据以下技能要求处理用户请求：

技能名称：{skill_name}

技能内容：
{skill_content}

用户请求：
{user_input}

请按照技能要求生成响应。"""
    return user_input

# ====================== 流式调用（简化版）======================
def call_llm_stream(env_vars, messages, user_info, skills_json):
    """
    简化版LLM流式调用函数
    支持 LM Studio 和其他 OpenAI 兼容的本地大模型
    """
    start_time = time.time()
    
    # 解析URL
    base_url = env_vars.get('BASE_URL', 'http://localhost:1234')
    url = urlparse(base_url)
    host = url.netloc
    path = "/v1/chat/completions"

    # 添加系统提示
    system_msg = {"role": "system", "content": build_system_prompt(user_info, skills_json)}
    final_messages = [system_msg] + messages

    data = {
        "model": env_vars.get("MODEL", "qwen/qwen3.5-2b"),
        "messages": final_messages,
        "temperature": float(env_vars.get("TEMPERATURE", 0.7)),
        "max_tokens": int(env_vars.get("MAX_TOKENS", 2048)),
        "stream": True
    }

    headers = {
        "Content-Type": "application/json"
    }
    
    api_key = env_vars.get('API_KEY', '')
    if api_key and api_key != 'your_api_key_here':
        headers["Authorization"] = f"Bearer {api_key}"

    timeout = int(env_vars.get('TIMEOUT', '120'))
    
    if url.scheme == 'https':
        conn = http.client.HTTPSConnection(host, timeout=timeout)
    else:
        conn = http.client.HTTPConnection(host, timeout=timeout)

    full_content = ""

    try:
        print(f"[DEBUG] 正在连接到 LLM: {url.scheme}://{host}{path}")
        conn.request("POST", path, json.dumps(data), headers)
        response = conn.getresponse()
        
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

        print("[AI] AI 正在思考...", end="", flush=True)

        buffer = ""
        
        while True:
            chunk = response.fp.read(1024)
            if not chunk:
                break
                
            try:
                buffer += chunk.decode('utf-8')
            except UnicodeDecodeError:
                buffer += chunk.decode('latin-1')
            
            while '\n' in buffer:
                line_end = buffer.find('\n')
                line = buffer[:line_end].strip()
                buffer = buffer[line_end + 1:]
                
                if not line:
                    continue
                
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                        
                    try:
                        jd = json.loads(data_str)
                        if "choices" in jd and len(jd["choices"]) > 0:
                            delta = jd["choices"][0].get("delta", {})
                            if "content" in delta and delta["content"]:
                                token = delta["content"]
                                full_content += token
                                if len(full_content) == len(token):
                                    print("\r" + " " * 30 + "\r", end="", flush=True)
                                    print("[AI] AI 回复：", end="", flush=True)
                                print(token, end="", flush=True)
                    except json.JSONDecodeError:
                        pass
        
        if full_content:
            print("\n")
        else:
            print("\n[WARN] AI 未返回任何内容")

    except ConnectionRefusedError:
        print(f"\n[ERROR] 无法连接到 LLM 服务器，请检查：")
        print(f"  1. LM Studio 是否已启动")
        print(f"  2. BASE_URL 配置是否正确（当前：{base_url}）")
        print(f"  3. 防火墙是否允许连接")
        return None, None, 0, 0, 0
    except Exception as e:
        print(f"\n[ERROR] 连接失败：{str(e)}")
        import traceback
        traceback.print_exc()
        return None, None, 0, 0, 0
    finally:
        conn.close()

    duration = time.time() - start_time
    total_tokens = len(full_content) // 3 if full_content else 0
    speed = total_tokens / duration if duration > 0 else 0

    return full_content, None, total_tokens, duration, speed

# ====================== 主循环 ======================
def main():
    env_vars = load_env()
    if not env_vars: 
        return

    print("=" * 50)
    print("[OK] AI 技能助手已启动")
    print(f"模型：{env_vars.get('MODEL', '未配置')}")
    print(f"地址：{env_vars.get('BASE_URL', '未配置')}")
    print("=" * 50)

    # 加载技能列表
    skills = list_available_skills()
    skills_json = json.dumps({"skills": skills}, ensure_ascii=False, indent=2)
    print(f"[OK] 已加载 {len(skills)} 个技能")
    print(f"[DEBUG] 技能列表: {skills_json}")

    messages = []
    user_info = "普通用户"

    while True:
        prompt = input("\n请输入问题（输入 exit 退出）：")
        if prompt.lower() == "exit": 
            break

        # 检查是否需要使用技能
        skill_name = check_skill_needed(prompt, skills)
        
        if skill_name:
            # 使用技能处理请求
            print(f"[INFO] 检测到需要使用技能：{skill_name}")
            skill_prompt = build_prompt_with_skill(prompt, skill_name)
            messages.append({"role": "user", "content": skill_prompt})
            
            # 调用本地LLM
            content, tool_calls, total_tokens, duration, speed = call_llm_stream(
                env_vars, messages, user_info, skills_json
            )
            
            if content:
                print(f"\n")
                messages.append({"role": "assistant", "content": content})
                print("=" * 50)
                print(f"⏱ 耗时：{duration:.2f}s  |  📊 Tokens：{total_tokens}  |  ⚡ 速度：{speed:.2f} token/s")
                print("=" * 50)
            else:
                print(f"\n[AI] AI 回复：抱歉，暂时无法回答您的问题")
                messages.append({"role": "assistant", "content": "抱歉，暂时无法回答您的问题"})
                print("=" * 50)
                print(f"⏱ 耗时：0.00s  |  📊 Tokens：0  |  ⚡ 速度：0.00 token/s")
                print("=" * 50)
        else:
            # 其他问题，调用本地LLM
            messages.append({"role": "user", "content": prompt})
            
            # 调用本地LLM
            content, tool_calls, total_tokens, duration, speed = call_llm_stream(
                env_vars, messages, user_info, skills_json
            )
            
            if content:
                print(f"\n")
                messages.append({"role": "assistant", "content": content})
                print("=" * 50)
                print(f"⏱ 耗时：{duration:.2f}s  |  📊 Tokens：{total_tokens}  |  ⚡ 速度：{speed:.2f} token/s")
                print("=" * 50)
            else:
                print(f"\n[AI] AI 回复：抱歉，暂时无法回答您的问题")
                messages.append({"role": "assistant", "content": "抱歉，暂时无法回答您的问题"})
                print("=" * 50)
                print(f"⏱ 耗时：0.00s  |  📊 Tokens：0  |  ⚡ 速度：0.00 token/s")
                print("=" * 50)

if __name__ == "__main__":
    main()