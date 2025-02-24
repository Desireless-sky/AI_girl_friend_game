# 导入所需库
import pygame  # 游戏开发库
import requests  # HTTP请求库
import json  # JSON处理
import sqlite3  # 嵌入式数据库
from pygame.locals import *  # pygame常量
from threading import Thread  # 多线程
from queue import Queue  # 线程安全队列

# ================== 配置部分 ==================
pygame.init()  # 初始化pygame

# 屏幕尺寸设置
SCREEN_SIZE = (1200, 800)
# 字体文件路径（需要支持中文）
FONT_PATH = "SmileySans-Oblique.ttf"  
# DeepSeek API密钥（注意：实际开发中不应明文存储）
DEEPSEEK_API_KEY = ""#写入你的api
# API端点地址
API_URL = "https://api.deepseek.com/v1/chat/completions"

# ================== 动画系统 ==================
class CharacterAnimation:
    def __init__(self):
        # 角色动画状态字典
        self.states = {
            'idle': self.load_frames("assets/idle_", 4),  # 待机状态
            'happy': self.load_frames("assets/happy_", 3),  # 开心状态
            'sad': self.load_frames("assets/sad_", 2)  # 悲伤状态
        }
        self.current_state = 'idle'  # 当前动画状态
        self.frame_index = 0  # 当前帧索引
        self.animation_speed = 1.0  # 动画播放速度
        self.last_update = pygame.time.get_ticks()  # 最后更新时间

    def load_frames(self, base_path, count):
        """加载并缩放动画帧"""
        # 加载指定数量的图片文件
        frames = [pygame.image.load(f"{base_path}{i}.png").convert_alpha() for i in range(1, count+1)]
        # 统一缩放所有帧到500x500大小
        return [pygame.transform.scale(frame, (500, 500)) for frame in frames]

    def update(self):
        """更新动画帧"""
        now = pygame.time.get_ticks()
        # 每1000毫秒更新一帧（1秒）
        if now - self.last_update > 1000:
            self.frame_index = (self.frame_index + 1) % len(self.states[self.current_state])
            self.last_update = now

    def get_current_frame(self):
        """获取当前动画帧"""
        return self.states[self.current_state][self.frame_index]

# ================== 记忆系统 ==================
class MemorySystem:
    def __init__(self):
        # 连接SQLite数据库
        self.conn = sqlite3.connect('memory.db')
        self._init_db()  # 初始化数据库
        self.context = []  # 上下文缓存

    def _init_db(self):
        """初始化数据库表"""
        self.conn.execute('''CREATE TABLE IF NOT EXISTS history
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
              role TEXT NOT NULL,
              content TEXT NOT NULL,
              timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')

    def add_message(self, role, content):
        """添加消息到上下文和数据库"""
        self.context.append({"role": role, "content": content})
        # 执行数据库插入
        self.conn.execute("INSERT INTO history (role, content) VALUES (?,?)",
                         (role, content))
        self.conn.commit()

    def get_context(self, max_length=5):
        """获取最近的对话上下文"""
        return self.context[-max_length:]

# ================== 对话系统 ==================
class AIChat:
    def __init__(self, memory):
        self.memory = memory  # 记忆系统实例
        # API请求头
        self.headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }

    def send_request(self, message):
        """发送请求到AI接口"""
        # 构建对话上下文
        context = [{"role": "system", "content": "你是一个温柔体贴的少女，说话风格可爱"}] 
        context += self.memory.get_context()
        context.append({"role": "user", "content": message})

        # 构造请求载荷
        payload = {
            "model": "deepseek-chat",
            "messages": context,
            "temperature": 0.7  # 控制回复随机性
        }

        try:
            # 发送POST请求
            response = requests.post(API_URL, headers=self.headers, json=payload)
            response.raise_for_status()  # 检查HTTP错误
            data = response.json()
            reply = data['choices'][0]['message']['content']
            
            # 保存对话记录
            self.memory.add_message("user", message)
            self.memory.add_message("assistant", reply)
            
            return reply
        except Exception as e:
            return f"错误：{str(e)}"

# ================== 游戏界面 ==================
class ChatUI:
    def __init__(self, rect):
        self.rect = rect  # UI区域矩形
        try:  # 字体加载优化
            self.font = pygame.freetype.Font(FONT_PATH, 24)
        except:
            self.font = pygame.freetype.SysFont('simhei', 24)  # 备选黑体
        self.history = []  # 聊天历史
        self.input_text = ""  # 输入文本
        self.cursor_visible = True  # 光标可见性
        self.cursor_timer = 0  # 光标计时器
        self.active = False  # 输入框激活状态
        self.composing_text = ""  # 输入法组合文本

    def update(self, dt):
        """更新光标状态"""
        self.cursor_timer += dt
        if self.cursor_timer > 500:  # 每500毫秒切换一次
            self.cursor_visible = not self.cursor_visible
            self.cursor_timer = 0

    def draw(self, surface):
        """绘制UI到指定表面"""
        # 半透明背景
        bg_surface = pygame.Surface(self.rect.size, pygame.SRCALPHA)
        pygame.draw.rect(bg_surface, (255, 255, 255, 200), bg_surface.get_rect())
        surface.blit(bg_surface, self.rect.topleft)
        
        # 绘制历史消息
        y = self.rect.top + 20
        for msg in self.history[-5:]:  # 显示最近5条
            color = (0, 0, 200) if msg['role'] == 'user' else (100, 100, 100)
            text_surface = self._render_multiline(msg['text'], color, self.rect.width-40)
            surface.blit(text_surface, (self.rect.left+20, y))
            y += text_surface.get_height() + 10
        
        # 绘制输入框
        input_rect = pygame.Rect(self.rect.left+10, self.rect.bottom-80, 
                               self.rect.width-20, 60)
        pygame.draw.rect(surface, (200, 200, 200), input_rect, 2)
        
        # 绘制输入文本（包含输入法组合文本）
        display_text = self.input_text + self.composing_text
        if self.cursor_visible and self.active:
            display_text += "|"  # 光标显示
        text_surface = self._render_multiline(display_text, (0, 0, 0), input_rect.width-20)
        surface.blit(text_surface, (input_rect.left+10, input_rect.top+10))

    def _render_multiline(self, text, color, max_width):
        """渲染多行文本"""
        lines = []  # 分行结果
        current_line = []  # 当前行内容
        current_width = 0  # 当前行宽度
        
        # 逐个字符处理
        for char in text:
            # 获取字符宽度信息
            metrics = self.font.get_metrics(char)
            char_width = metrics[0][4] if metrics else self.font.get_rect(char).width
            
            if current_width + char_width > max_width:  # 超过最大宽度换行
                lines.append(''.join(current_line))
                current_line = [char]
                current_width = char_width
            else:
                current_line.append(char)
                current_width += char_width
                
        if current_line:  # 添加最后一行
            lines.append(''.join(current_line))
        
        # 创建总表面
        total_surface = pygame.Surface((max_width, len(lines)*30), pygame.SRCALPHA)
        y = 0
        for line in lines:
            text_surf, _ = self.font.render(line, color)
            total_surface.blit(text_surf, (0, y))
            y += 30  # 行间距
            
        return total_surface

class DatabaseManager:
    """数据库管理类（线程安全）"""
    def __init__(self):
        self.conn = sqlite3.connect('memory.db', check_same_thread=False)
        self._init_db()
        self.queue = Queue()  # 操作队列
        self.start_background_thread()  # 启动后台线程

    def _init_db(self):
        """初始化数据库表"""
        self.conn.execute('''CREATE TABLE IF NOT EXISTS history
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
              role TEXT NOT NULL,
              content TEXT NOT NULL,
              timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')

    def add_message(self, role, content):
        """添加消息到队列"""
        self.queue.put(('add_message', {'role': role, 'content': content}))

    def get_context(self, max_length=5):
        """从数据库获取上下文"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM history ORDER BY id DESC LIMIT ?", (max_length,))
        rows = cursor.fetchall()
        # 反转顺序保证时间正序
        context = [{"role": row[1], "content": row[2]} for row in reversed(rows)]
        return context

    def start_background_thread(self):
        """启动后台处理线程"""
        Thread(target=self.process_queue, daemon=True).start()

    def process_queue(self):
        """处理队列中的数据库操作"""
        while True:
            action, params = self.queue.get()
            if action == 'add_message':
                # 执行数据库插入
                self.conn.execute("INSERT INTO history (role, content) VALUES (?,?)",
                                 (params['role'], params['content']))
                self.conn.commit()
            self.queue.task_done()

class MemorySystem:
    """记忆系统（封装数据库管理）"""
    def __init__(self):
        self.db_manager = DatabaseManager()
        self.context = []  # 内存中的上下文缓存

    def add_message(self, role, content):
        """添加消息到内存和数据库"""
        self.context.append({"role": role, "content": content})
        self.db_manager.add_message(role, content)

    def get_context(self, max_length=5):
        """从数据库获取上下文"""
        return self.db_manager.get_context(max_length)


# ================== 主游戏循环 ==================
def main():

    try:# 加载图标文件（推荐使用.ico格式，或者32x32/64x64像素的PNG）
        window_icon = pygame.image.load("assets/logo.ico")  # 或者.png
        pygame.display.set_icon(window_icon)  # 必须在set_mode之前调用
    except Exception as e:
        print(f"无法加载窗口图标: {str(e)}")
    # 初始化游戏窗口
    screen = pygame.display.set_mode(SCREEN_SIZE)
    pygame.display.set_caption("AI少女陪伴系统")
    clock = pygame.time.Clock()  # 游戏时钟
    
    # 输入法初始化
    left_width = int(SCREEN_SIZE[0] * 0.6)  # 左侧动画区域宽度
    right_width = SCREEN_SIZE[0] - left_width
    input_rect = pygame.Rect(left_width+10, SCREEN_SIZE[1]-80, right_width-20, 60)
    pygame.key.set_text_input_rect(input_rect)  # 设置输入法区域
    pygame.key.start_text_input()  # 启用文本输入
    
    # 初始化各系统组件
    anim = CharacterAnimation()  # 角色动画
    memory = MemorySystem()  # 记忆系统
    chat_ui = ChatUI(pygame.Rect(left_width, 0, right_width, SCREEN_SIZE[1]))  # 聊天UI
    ai_chat = AIChat(memory)  # AI对话系统
    
    current_reply = None  # 当前回复
    request_thread = None  # 请求线程
    
    def async_chat(text):
        """异步发送聊天请求"""
        nonlocal current_reply
        current_reply = ai_chat.send_request(text)
    
    running = True
    while running:  # 主循环
        dt = clock.tick(60)  # 限制60帧
        
        # 事件处理
        for event in pygame.event.get():
            if event.type == QUIT:
                running = False
            elif event.type == KEYDOWN:
                if event.key == K_ESCAPE:
                    running = False
                elif event.key == K_RETURN and chat_ui.active:  # 回车发送
                    if chat_ui.input_text.strip():
                        # 启动新线程处理请求
                        request_thread = Thread(target=async_chat, args=(chat_ui.input_text,))
                        request_thread.start()
                        # 添加用户消息到历史
                        chat_ui.history.append({'role': 'user', 'text': chat_ui.input_text})
                        chat_ui.input_text = ""
                        chat_ui.composing_text = ""
                elif event.key == K_BACKSPACE and chat_ui.active:  # 退格删除
                    chat_ui.input_text = chat_ui.input_text[:-1]
                elif event.key == K_TAB:  # 切换输入框激活状态
                    chat_ui.active = not chat_ui.active
                    pygame.key.set_text_input_rect(input_rect)
            elif event.type == TEXTEDITING and chat_ui.active:  # 输入法组合文本
                chat_ui.composing_text = event.text
            elif event.type == TEXTINPUT and chat_ui.active:  # 普通文本输入
                chat_ui.input_text += event.text
                chat_ui.composing_text = ""
        
        # 更新状态
        anim.update()  # 更新动画
        chat_ui.update(dt)  # 更新UI
        
        # 处理AI回复
        if current_reply and (request_thread is None or not request_thread.is_alive()):
            chat_ui.history.append({'role': 'assistant', 'text': current_reply})
            current_reply = None
        
        # 渲染画面
        screen.fill((240, 240, 240))  # 背景色
        char_frame = anim.get_current_frame()  # 获取当前动画帧
        frame_rect = char_frame.get_rect(center=(left_width//2, SCREEN_SIZE[1]//2))
        screen.blit(char_frame, frame_rect)  # 绘制角色
        chat_ui.draw(screen)  # 绘制UI
        pygame.display.flip()  # 更新显示

if __name__ == "__main__":
    main()