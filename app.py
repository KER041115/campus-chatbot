# app.py
from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import os
from dotenv import load_dotenv
import google.generativeai as genai

# 加载环境变量
load_dotenv()

app = Flask(__name__)
CORS(app)

# ============================================
# 配置 Gemini AI
# ============================================
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    print("⚠️ 警告：未在 .env 中找到 GOOGLE_API_KEY，请检查！")
    # 如果你没有 .env 文件，可以直接在这里赋值，但强烈建议使用 .env
    # GOOGLE_API_KEY = "你的API密钥"

genai.configure(api_key=GOOGLE_API_KEY)
# 使用效果更好且配额充足的模型
model = genai.GenerativeModel('gemini-3.5-flash')
# ============================================
# 前端界面
# ============================================
@app.route('/')
def index():
    html = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>PSMZA AI Assistant</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        .app-container {
            width: 100%;
            max-width: 800px;
            height: 90vh;
            max-height: 700px;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.15);
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px 24px;
            text-align: center;
            flex-shrink: 0;
        }
        .header h1 {
            font-size: 24px;
            font-weight: 600;
            letter-spacing: 0.5px;
        }
        .header p {
            font-size: 14px;
            opacity: 0.9;
            margin-top: 4px;
        }
        .quick-actions {
            display: flex;
            gap: 10px;
            padding: 12px 16px;
            background: #f8f9fa;
            border-bottom: 1px solid #e9ecef;
            flex-wrap: wrap;
            flex-shrink: 0;
        }
        .quick-actions button {
            padding: 6px 14px;
            border: none;
            background: white;
            border-radius: 20px;
            font-size: 13px;
            font-weight: 500;
            color: #495057;
            box-shadow: 0 1px 3px rgba(0,0,0,0.06);
            cursor: pointer;
            transition: all 0.2s;
            border: 1px solid #dee2e6;
        }
        .quick-actions button:hover {
            background: #667eea;
            color: white;
            border-color: #667eea;
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(102, 126, 234, 0.3);
        }
        #chat {
            flex: 1;
            overflow-y: auto;
            padding: 20px 24px;
            display: flex;
            flex-direction: column;
            gap: 12px;
            background: #fafcff;
        }
        #chat::-webkit-scrollbar { width: 4px; }
        #chat::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 2px; }
        
        .message {
            max-width: 80%;
            padding: 10px 16px;
            border-radius: 16px;
            line-height: 1.5;
            word-wrap: break-word;
            animation: fadeIn 0.3s ease;
            font-size: 15px;
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(8px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .message.user {
            align-self: flex-end;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-bottom-right-radius: 4px;
        }
        .message.bot {
            align-self: flex-start;
            background: white;
            color: #1e293b;
            border-bottom-left-radius: 4px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.06);
        }
        .message.typing {
            align-self: flex-start;
            background: white;
            color: #94a3b8;
            border-bottom-left-radius: 4px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.06);
            display: flex;
            gap: 4px;
            padding: 12px 18px;
        }
        .message.typing span {
            display: inline-block;
            width: 8px;
            height: 8px;
            background: #94a3b8;
            border-radius: 50%;
            animation: typing 1.4s infinite both;
        }
        .message.typing span:nth-child(2) { animation-delay: 0.2s; }
        .message.typing span:nth-child(3) { animation-delay: 0.4s; }
        @keyframes typing {
            0%, 60%, 100% { transform: translateY(0); }
            30% { transform: translateY(-6px); }
        }
        .input-area {
            padding: 16px 20px;
            background: white;
            border-top: 1px solid #e9ecef;
            display: flex;
            gap: 12px;
            flex-shrink: 0;
            align-items: center;
        }
        .input-area input {
            flex: 1;
            padding: 12px 16px;
            border: 2px solid #e2e8f0;
            border-radius: 30px;
            font-size: 15px;
            outline: none;
            transition: border 0.2s;
        }
        .input-area input:focus {
            border-color: #667eea;
        }
        .input-area button {
            padding: 10px 24px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 30px;
            font-size: 15px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.15s, opacity 0.15s;
            white-space: nowrap;
        }
        .input-area button:hover {
            transform: scale(1.02);
        }
        .input-area button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }
        .footer {
            text-align: center;
            padding: 8px;
            font-size: 12px;
            color: #94a3b8;
            background: #f8f9fa;
            border-top: 1px solid #e9ecef;
            flex-shrink: 0;
        }
    </style>
</head>
<body>
    <div class="app-container">
        <div class="header">
            <h1>🎓 PSMZA AI Assistant</h1>
            <p>Ask about courses, registration, fees, and campus life</p>
        </div>
        <div class="quick-actions">
            <button onclick="sendQuick('How do I register for courses?')">📝 Registration</button>
            <button onclick="sendQuick('What are the tuition fees for this semester?')">💰 Fees</button>
            <button onclick="sendQuick('When is the semester break?')">📅 Calendar</button>
            <button onclick="sendQuick('How to apply for a hostel?')">🏠 Hostel</button>
        </div>
        <div id="chat">
            <div class="message bot">
                👋 Hello! I'm your campus AI assistant.<br> How can I help you today?
            </div>
        </div>
        <div class="input-area">
            <input type="text" id="userInput" placeholder="Type your question..." />
            <button id="sendBtn" onclick="sendMessage()">Send</button>
        </div>
        <div class="footer">Powered by Google Gemini AI</div>
    </div>

    <script>
        const chatDiv = document.getElementById('chat');
        const userInput = document.getElementById('userInput');
        const sendBtn = document.getElementById('sendBtn');
        let isWaiting = false;

        function addMessage(text, isUser) {
            const div = document.createElement('div');
            div.className = 'message ' + (isUser ? 'user' : 'bot');
            div.textContent = text;
            chatDiv.appendChild(div);
            chatDiv.scrollTop = chatDiv.scrollHeight;
        }

        function showTyping(show) {
            let typingDiv = document.querySelector('.message.typing');
            if (show) {
                if (!typingDiv) {
                    typingDiv = document.createElement('div');
                    typingDiv.className = 'message typing';
                    typingDiv.innerHTML = '<span></span><span></span><span></span>';
                    chatDiv.appendChild(typingDiv);
                    chatDiv.scrollTop = chatDiv.scrollHeight;
                }
            } else {
                if (typingDiv) typingDiv.remove();
            }
        }

        async function sendMessage() {
            const message = userInput.value.trim();
            if (!message || isWaiting) return;

            userInput.value = '';
            addMessage(message, true);
            showTyping(true);
            isWaiting = true;
            sendBtn.disabled = true;

            try {
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: message })
                });
                const data = await response.json();
                showTyping(false);
                if (data.error) {
                    addMessage('❌ ' + data.error, false);
                } else {
                    addMessage(data.reply, false);
                }
            } catch (error) {
                showTyping(false);
                addMessage('❌ Connection error. Please try again.', false);
            } finally {
                isWaiting = false;
                sendBtn.disabled = false;
            }
        }

        function sendQuick(question) {
            userInput.value = question;
            sendMessage();
        }

        userInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') sendMessage();
        });
    </script>
</body>
</html>
    '''
    return render_template_string(html)

# ============================================
# API 接口
# ============================================
@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        user_message = data.get('message', '').strip()
        if not user_message:
            return jsonify({'error': 'Message is required'}), 400

        # 调用 Google Gemini
        response = model.generate_content(user_message)
        reply = response.text

        return jsonify({'reply': reply})

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================
# 启动服务
# ============================================
if __name__ == '__main__':
    print("=" * 50)
    print("🎓 PSMZA AI Assistant (Enhanced)")
    print("=" * 50)
    print("📍 Local URL: http://127.0.0.1:5000")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=True)