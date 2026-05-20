import os
import time
import json
import http.client
import re
from urllib.parse import urlparse
import urllib.request

# 技能目录路径
SKILLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.agents', 'skills')

# ====================== 读取 .env 文件 ======================
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

# ====================== 工具函数定义 ======================
def search_files_with_keyword(directory, keyword):
    """搜索目录下包含指定关键词的文件"""
    result = []
    try:
        # 去除关键词两端的引号（处理LLM可能添加的引号）
        keyword = keyword.strip().strip("'").strip('"')
        
        # 如果是相对路径，转换为绝对路径
        if not os.path.isabs(directory):
            directory = os.path.abspath(directory)
        
        # 检查目录是否存在
        if not os.path.exists(directory):
            return {"success": False, "error": f"目录不存在: {directory}"}
        
        for root, dirs, files in os.walk(directory):
            for filename in files:
                filepath = os.path.join(root, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        if keyword in content:
                            result.append({
                                'filename': filename,
                                'path': filepath,
                                'line_count': len(content.split('\n'))
                            })
                except Exception as e:
                    continue
        return {"success": True, "result": result}
    except Exception as e:
        return {"success": False, "error": str(e)}

def read_file(filepath):
    """读取文件内容"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        return {"success": True, "content": content}
    except Exception as e:
        return {"success": False, "error": str(e)}

def write_file(filepath, content):
    """写入文件内容"""
    try:
        # 确保目录存在
        dir_path = os.path.dirname(filepath)
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return {"success": True, "message": "文件写入成功"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def fetch_web_page(url):
    """获取网页内容"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as response:
            content = response.read().decode('utf-8', errors='ignore')
        return {"success": True, "content": content}
    except Exception as e:
        return {"success": False, "error": str(e)}

# 工具注册
TOOLS = {
    "search_files": {
        "name": "search_files",
        "description": "搜索目录下包含指定关键词的文件",
        "function": search_files_with_keyword,
        "parameters": [
            {"name": "directory", "type": "string", "description": "要搜索的目录路径"},
            {"name": "keyword", "type": "string", "description": "要搜索的关键词"}
        ]
    },
    "read_file": {
        "name": "read_file",
        "description": "读取指定文件的内容",
        "function": read_file,
        "parameters": [
            {"name": "filepath", "type": "string", "description": "文件路径"}
        ]
    },
    "write_file": {
        "name": "write_file",
        "description": "向指定文件写入内容",
        "function": write_file,
        "parameters": [
            {"name": "filepath", "type": "string", "description": "文件路径"},
            {"name": "content", "type": "string", "description": "要写入的内容"}
        ]
    },
    "fetch_web_page": {
        "name": "fetch_web_page",
        "description": "获取指定URL的网页内容",
        "function": fetch_web_page,
        "parameters": [
            {"name": "url", "type": "string", "description": "网页URL"}
        ]
    }
}

# ====================== 链式调用上下文管理器 ======================
class ChainedCallContext:
    def __init__(self, max_iterations=10):
        self.max_iterations = max_iterations
        self.current_iteration = 0
        self.call_history = []
        self.variables = {}
    
    def add_call(self, tool_name, arguments, result):
        """记录一次工具调用"""
        # 限制result长度，避免提示词过长
        max_result_length = 500
        result_str = str(result)
        if len(result_str) > max_result_length:
            result = result_str[:max_result_length] + "..."
        
        self.call_history.append({
            "iteration": self.current_iteration,
            "tool_name": tool_name,
            "arguments": arguments,
            "result": result,
            "timestamp": time.time()
        })
        
        # 只保留最近3条历史记录，避免提示词过长
        max_history = 3
        if len(self.call_history) > max_history:
            self.call_history = self.call_history[-max_history:]
    
    def get_history_summary(self):
        """获取调用历史摘要"""
        summary = []
        for call in self.call_history:
            result_str = str(call["result"])
            summary.append({
                "tool_name": call["tool_name"],
                "arguments": call["arguments"],
                "result": result_str[:100] + "..." if len(result_str) > 100 else result_str
            })
        return summary
    
    def set_variable(self, name, value):
        """设置中间变量"""
        self.variables[name] = value
    
    def get_variable(self, name, default=None):
        """获取中间变量"""
        return self.variables.get(name, default)
    
    def increment_iteration(self):
        """增加迭代次数"""
        self.current_iteration += 1
    
    def is_max_iterations_reached(self):
        """检查是否达到最大迭代次数"""
        return self.current_iteration >= self.max_iterations
    
    def reset(self):
        """重置上下文"""
        self.current_iteration = 0
        self.call_history = []
        self.variables = {}

# ====================== 系统提示词构建 ======================
def build_system_prompt():
    # 创建不包含函数对象的工具元数据，用于JSON序列化
    tools_metadata = {}
    for tool_name, tool_info in TOOLS.items():
        tools_metadata[tool_name] = {
            "name": tool_info["name"],
            "description": tool_info["description"],
            "parameters": tool_info["parameters"]
        }
    
    tools_info = json.dumps(tools_metadata, ensure_ascii=False, indent=2)
    
    return f"""你是一个具备链式工具调用能力的智能助手。你可以根据用户的请求，自主决定调用工具的顺序，并将前一个工具的输出作为后一个工具的输入。

可用工具列表：
{tools_info}

链式调用规则：
1. 你可以按照任务需求，依次调用多个工具
2. 前一个工具的执行结果可以作为后一个工具的输入参数
3. 你需要根据中间结果自主判断是否需要继续调用工具或完成任务
4. 如果任务已完成或无法继续，输出最终答案

输出格式要求：
- 当任务完成时，输出JSON格式：
  {{
    "done": true,
    "answer": "最终回答内容"
  }}
  
- 当需要继续调用工具时，输出JSON格式：
  {{
    "done": false,
    "tool_call": {{
      "name": "工具名称",
      "arguments": {{
        "参数名": "参数值"
      }}
    }}
  }}

请严格按照上述JSON格式输出，不要添加任何额外内容。"""

# ====================== 分析提示词构建 ======================
def build_analysis_prompt(user_request, context):
    """构建分析提示词"""
    history_summary = context.get_history_summary()
    
    prompt = f"""用户原始请求：
{user_request}

已执行的工具调用历史：
{json.dumps(history_summary, ensure_ascii=False, indent=2)}

当前上下文变量：
{json.dumps(context.variables, ensure_ascii=False, indent=2)}

决策规则：
1. 分析用户请求和已执行的步骤
2. 决定下一步操作：继续调用工具或完成任务
3. 如果需要调用工具，请选择合适的工具和参数
4. 如果任务已完成，请总结结果

请根据上述信息，按照指定格式输出决策。"""
    
    return prompt

# ====================== LLM调用函数 ======================
def call_llm(env_vars, prompt):
    """调用LLM获取决策"""
    base_url = env_vars.get('BASE_URL', 'http://localhost:1234')
    url = urlparse(base_url)
    host = url.netloc
    path = "/v1/chat/completions"

    messages = [
        {"role": "system", "content": build_system_prompt()},
        {"role": "user", "content": prompt}
    ]

    data = {
        "model": env_vars.get("MODEL", "qwen/qwen3.5-2b"),
        "messages": messages,
        "temperature": float(env_vars.get("TEMPERATURE", 0.7)),
        "max_tokens": int(env_vars.get("MAX_TOKENS", 2048)),
        "stream": False
    }

    headers = {"Content-Type": "application/json"}
    
    api_key = env_vars.get('API_KEY', '')
    if api_key and api_key != 'your_api_key_here':
        headers["Authorization"] = f"Bearer {api_key}"

    timeout = int(env_vars.get('TIMEOUT', '120'))
    
    if url.scheme == 'https':
        conn = http.client.HTTPSConnection(host, timeout=timeout)
    else:
        conn = http.client.HTTPConnection(host, timeout=timeout)

    try:
        conn.request("POST", path, json.dumps(data), headers)
        response = conn.getresponse()
        
        if response.status != 200:
            error_content = response.read().decode('utf-8', errors='ignore')
            print(f"[ERROR] HTTP {response.status}: {error_content}")
            return None

        response_data = response.read().decode('utf-8')
        jd = json.loads(response_data)
        
        if "choices" in jd and len(jd["choices"]) > 0:
            content = jd["choices"][0].get("message", {}).get("content", "")
            return content
        
        return None
    except Exception as e:
        print(f"[ERROR] LLM调用失败：{str(e)}")
        return None
    finally:
        conn.close()

# ====================== 解析LLM响应 ======================
def parse_llm_response(response):
    """解析LLM响应"""
    if not response:
        return None
    
    # 尝试提取JSON内容
    try:
        # 移除可能的markdown代码块标记
        response = response.strip()
        if response.startswith('```json'):
            response = response[7:]
        if response.endswith('```'):
            response = response[:-3]
        
        result = json.loads(response.strip())
        return result
    except json.JSONDecodeError:
        # 如果不是有效JSON，尝试查找JSON片段
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            try:
                result = json.loads(json_match.group())
                return result
            except:
                pass
        return None

# ====================== 执行工具调用 ======================
def execute_tool(tool_name, arguments):
    """执行工具调用"""
    if tool_name not in TOOLS:
        return {"success": False, "error": f"未知工具: {tool_name}"}
    
    tool_info = TOOLS[tool_name]
    tool_func = tool_info["function"]
    
    try:
        # 获取参数
        params = []
        for param_info in tool_info["parameters"]:
            param_name = param_info["name"]
            if param_name in arguments:
                params.append(arguments[param_name])
            else:
                return {"success": False, "error": f"缺少参数: {param_name}"}
        
        # 执行工具
        result = tool_func(*params)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}

# ====================== 链式调用执行函数 ======================
def execute_chained_tool_call(env_vars, user_request, max_iterations=10):
    """执行链式工具调用"""
    print(f"[INFO] 开始链式工具调用，最大迭代次数: {max_iterations}")
    print(f"[INFO] 用户请求: {user_request}")
    
    # 初始化上下文
    context = ChainedCallContext(max_iterations=max_iterations)
    
    while not context.is_max_iterations_reached():
        print(f"\n[INFO] ========== 第 {context.current_iteration + 1} 轮 ==========")
        
        # 构建分析提示词
        prompt = build_analysis_prompt(user_request, context)
        
        # 调用LLM获取决策
        response = call_llm(env_vars, prompt)
        if not response:
            print("[ERROR] LLM未返回响应")
            break
        
        print(f"[DEBUG] LLM响应: {response[:200]}...")
        
        # 解析响应
        decision = parse_llm_response(response)
        if not decision:
            print("[ERROR] 无法解析LLM响应")
            break
        
        # 检查是否完成
        if decision.get("done", False):
            answer = decision.get("answer", "")
            print(f"[INFO] 任务完成！")
            print(f"[RESULT] {answer}")
            return answer
        
        # 执行工具调用
        tool_call = decision.get("tool_call", {})
        tool_name = tool_call.get("name")
        arguments = tool_call.get("arguments", {})
        
        if not tool_name:
            print("[ERROR] 工具名称为空")
            break
        
        print(f"[INFO] 调用工具: {tool_name}")
        print(f"[INFO] 参数: {arguments}")
        
        # 执行工具
        result = execute_tool(tool_name, arguments)
        print(f"[INFO] 工具执行结果: {str(result)[:200]}...")
        
        # 记录到上下文
        context.add_call(tool_name, arguments, result)
        
        # 将结果保存为变量供后续使用
        if result.get("success", False):
            context.set_variable(f"last_result_{tool_name}", result.get("result", result.get("content", result)))
        
        # 增加迭代次数
        context.increment_iteration()
    
    # 如果达到最大迭代次数仍未完成
    if context.is_max_iterations_reached():
        print(f"[WARN] 已达到最大迭代次数 ({max_iterations})，任务未完成")
    
    return None

# ====================== 测试函数 ======================
def test_chained_calls():
    """测试链式工具调用"""
    env_vars = load_env()
    if not env_vars:
        print("[ERROR] 无法加载环境变量")
        return
    
    print("=" * 60)
    print("测试1: 文件搜索链式调用")
    print("=" * 60)
    user_request1 = "请查找practice06目录下所有包含'def'关键词的文件，并总结这些文件的主要内容"
    execute_chained_tool_call(env_vars, user_request1)
    
    # 创建测试文件
    test_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(test_dir, '1.txt'), 'w') as f:
        f.write('10')
    with open(os.path.join(test_dir, '2.txt'), 'w') as f:
        f.write('20')
    
    print("\n" + "=" * 60)
    print("测试2: 多文件操作")
    print("=" * 60)
    user_request2 = f"读取{os.path.join(test_dir, '1.txt')}和{os.path.join(test_dir, '2.txt')}两个文件，文件内容的都是正整数，把两个数相加的和写入{os.path.join(test_dir, 'result.txt')}文件。"
    execute_chained_tool_call(env_vars, user_request2)
    
    print("\n" + "=" * 60)
    print("测试3: 网页处理链式调用")
    print("=" * 60)
    user_request3 = "访问 https://www.nsu.edu.cn/HTML/news/2024/06/article_3974.html 并总结页面内容，保存到practice07/summary.txt"
    execute_chained_tool_call(env_vars, user_request3)

# ====================== 主函数 ======================
def main():
    env_vars = load_env()
    if not env_vars:
        return

    print("=" * 60)
    print("[OK] 链式工具调用助手已启动")
    print(f"模型：{env_vars.get('MODEL', '未配置')}")
    print(f"地址：{env_vars.get('BASE_URL', '未配置')}")
    print("=" * 60)

    while True:
        prompt = input("\n请输入问题（输入 exit 退出，输入 test 运行测试）：")
        if prompt.lower() == "exit":
            break
        if prompt.lower() == "test":
            test_chained_calls()
            continue

        # 执行链式工具调用
        result = execute_chained_tool_call(env_vars, prompt)
        if result:
            print(f"\n[最终回答] {result}")
        else:
            print("\n[AI] 抱歉，未能完成任务")

if __name__ == "__main__":
    main()
