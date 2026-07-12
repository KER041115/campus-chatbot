# app.py - 完整修复版
# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify, render_template_string, Response, stream_with_context
from flask_cors import CORS
import requests
import json
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

KEYLESSAI_URL = "https://keylessai.thryx.workers.dev/v1/chat/completions"
USE_GEMINI = os.getenv("USE_GEMINI", "false").lower() == "true"
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

SYSTEM_PROMPT_EN = """You are a helpful campus assistant for Politeknik Sultan Mizan Zainal Abidin (PSMZA).
Answer student questions about courses, registration, fees, schedules, and campus facilities.
Be friendly, accurate, and concise. Respond in English or Malay based on the user's language.
If you don't know the answer, say I do not have that information yet. Please contact the administrative office."""

SYSTEM_PROMPT_BM = """Anda adalah pembantu kampus yang mesra untuk Politeknik Sultan Mizan Zainal Abidin (PSMZA).
Jawab soalan pelajar tentang kursus, pendaftaran, yuran, jadual, dan kemudahan kampus.
Bersikap mesra, tepat, dan ringkas. Balas dalam Bahasa Melayu atau Inggeris berdasarkan bahasa pengguna.
Jika anda tidak tahu jawapannya, katakan Saya belum mempunyai maklumat itu. Sila hubungi pejabat pentadbiran."""

conversations = {}
feedbacks = []

def call_ai(messages, stream=False):
    if not USE_GEMINI:
        payload = {"model": "gpt-4o", "messages": messages, "stream": stream}
        if stream:
            return requests.post(KEYLESSAI_URL, json=payload, headers={"Content-Type": "application/json"}, stream=True, timeout=60)
        else:
            response = requests.post(KEYLESSAI_URL, json=payload, headers={"Content-Type": "application/json"}, timeout=60)
            if response.status_code == 200:
                return response.json()['choices'][0]['message']['content']
            return None
    else:
        try:
            import google.generativeai as genai
            genai.configure(api_key=GOOGLE_API_KEY)
            model = genai.GenerativeModel('gemini-2.0-flash-lite')
            response = model.generate_content(messages[-1]['content'])
            return response.text
        except Exception as e:
            print(f"Gemini error: {e}")
            return None

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json()
    user_message = data.get('message', '').strip()
    session_id = data.get('session_id', 'default')
    language = data.get('language', 'en')
    if not user_message:
        return jsonify({'error': 'Message is required'}), 400
    system_prompt = SYSTEM_PROMPT_EN if language == 'en' else SYSTEM_PROMPT_BM
    if session_id not in conversations:
        conversations[session_id] = [{"role": "system", "content": system_prompt}]
    conversations[session_id].append({"role": "user", "content": user_message})
    if len(conversations[session_id]) > 20:
        conversations[session_id] = [conversations[session_id][0]] + conversations[session_id][-10:]
    try:
        reply = call_ai(conversations[session_id], stream=False)
        if reply:
            conversations[session_id].append({"role": "assistant", "content": reply})
            return jsonify({'reply': reply, 'session_id': session_id})
        error_msg = "AI service unavailable. Please try again later." if language == 'en' else "Perkhidmatan AI tidak tersedia. Sila cuba lagi nanti."
        return jsonify({'error': error_msg}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/chat/stream', methods=['POST'])
def chat_stream():
    data = request.get_json()
    user_message = data.get('message', '').strip()
    session_id = data.get('session_id', 'default')
    language = data.get('language', 'en')
    if not user_message:
        return jsonify({'error': 'Message is required'}), 400
    system_prompt = SYSTEM_PROMPT_EN if language == 'en' else SYSTEM_PROMPT_BM
    if session_id not in conversations:
        conversations[session_id] = [{"role": "system", "content": system_prompt}]
    conversations[session_id].append({"role": "user", "content": user_message})
    if len(conversations[session_id]) > 20:
        conversations[session_id] = [conversations[session_id][0]] + conversations[session_id][-10:]
    def generate():
        try:
            payload = {"model": "gpt-4o", "messages": conversations[session_id], "stream": True}
            response = requests.post(KEYLESSAI_URL, json=payload, headers={"Content-Type": "application/json"}, stream=True, timeout=60)
            full_reply = ""
            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        data_str = line[6:]
                        if data_str == '[DONE]':
                            break
                        try:
                            chunk = json.loads(data_str)
                            if 'choices' in chunk and len(chunk['choices']) > 0:
                                delta = chunk['choices'][0].get('delta', {})
                                content = delta.get('content', '')
                                if content:
                                    full_reply += content
                                    yield f"data: {json.dumps({'content': content})}\n\n"
                        except json.JSONDecodeError:
                            pass
            if full_reply:
                conversations[session_id].append({"role": "assistant", "content": full_reply})
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/api/feedback', methods=['POST'])
def feedback():
    data = request.get_json()
    feedbacks.append({
        'session_id': data.get('session_id', ''),
        'message': data.get('message', '')[:200],
        'rating': data.get('rating', ''),
        'timestamp': datetime.now().isoformat()
    })
    if len(feedbacks) > 100:
        feedbacks.pop(0)
    return jsonify({'status': 'ok'})

@app.route('/api/feedback/stats', methods=['GET'])
def feedback_stats():
    total = len(feedbacks)
    helpful = len([f for f in feedbacks if f['rating'] == 'helpful'])
    unhelpful = len([f for f in feedbacks if f['rating'] == 'unhelpful'])
    return jsonify({'total': total, 'helpful': helpful, 'unhelpful': unhelpful, 'rate': f"{helpful/total*100:.1f}%" if total > 0 else "N/A"})

@app.route('/api/reset', methods=['POST'])
def reset_session():
    data = request.get_json()
    session_id = data.get('session_id', 'default')
    if session_id in conversations:
        del conversations[session_id]
    return jsonify({'status': 'ok'})

@app.route('/')
def index():
    html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PSMZA AI Assistant</title>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #f0f4ff 0%, #e8edf5 100%);
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
            max-height: 750px;
            background: white;
            border-radius: 24px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.12);
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 16px 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-shrink: 0;
            flex-wrap: wrap;
            gap: 8px;
        }
        .header-left { display: flex; align-items: center; gap: 12px; }
        .header .status-dot {
            width: 10px; height: 10px; background: #4ade80; border-radius: 50%;
            display: inline-block; animation: pulse 2s infinite;
        }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
        .header h1 { font-size: 18px; font-weight: 600; }
        .header .subtitle { font-size: 12px; opacity: 0.8; }
        .header-actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
        .header-actions .lang-btn {
            background: rgba(255,255,255,0.2); border: 1px solid rgba(255,255,255,0.3);
            color: white; padding: 5px 12px; border-radius: 16px; cursor: pointer;
            font-size: 12px; font-weight: 600; transition: all 0.2s;
        }
        .header-actions .lang-btn:hover { background: rgba(255,255,255,0.3); }
        .header-actions .lang-btn.active { background: white; color: #667eea; border-color: white; }
        .header-actions .reset-btn {
            background: rgba(255,255,255,0.2); border: none; color: white;
            padding: 6px 12px; border-radius: 8px; cursor: pointer; font-size: 13px;
            transition: background 0.2s;
        }
        .header-actions .reset-btn:hover { background: rgba(255,255,255,0.3); }
        .quick-questions {
            padding: 10px 16px; background: #f8fafc; border-bottom: 1px solid #e2e8f0;
            display: flex; gap: 8px; flex-wrap: wrap; flex-shrink: 0;
        }
        .quick-questions button {
            padding: 6px 14px; border: 1px solid #e2e8f0; background: white;
            border-radius: 20px; font-size: 12px; cursor: pointer; transition: all 0.2s; color: #334155;
        }
        .quick-questions button:hover { background: #667eea; color: white; border-color: #667eea; transform: translateY(-1px); }
        .messages {
            flex: 1; overflow-y: auto; padding: 16px 20px; display: flex; flex-direction: column;
            gap: 12px; background: #fafcff;
        }
        .messages::-webkit-scrollbar { width: 4px; }
        .messages::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 2px; }
        .message {
            max-width: 85%; padding: 12px 16px; border-radius: 16px; font-size: 14px;
            line-height: 1.6; word-wrap: break-word; animation: fadeIn 0.3s ease;
        }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        .message.user {
            align-self: flex-end; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white; border-bottom-right-radius: 4px;
        }
        .message.bot {
            align-self: flex-start; background: white; color: #1e293b;
            border-bottom-left-radius: 4px; box-shadow: 0 1px 4px rgba(0,0,0,0.06);
        }
        .message.bot code { background: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-size: 13px; }
        .message.bot pre { background: #f1f5f9; padding: 12px; border-radius: 8px; overflow-x: auto; margin: 8px 0; }
        .message.bot ul, .message.bot ol { padding-left: 20px; margin: 8px 0; }
        .message-actions { display: flex; gap: 10px; margin-top: 8px; opacity: 0.6; transition: opacity 0.2s; flex-wrap: wrap; }
        .message:hover .message-actions { opacity: 1; }
        .message-actions button {
            background: none; border: none; font-size: 12px; cursor: pointer;
            color: #94a3b8; padding: 2px 6px; border-radius: 4px; transition: all 0.2s;
        }
        .message-actions button:hover { color: #667eea; background: #f1f5f9; }
        .typing-indicator {
            display: none; align-self: flex-start; background: white; padding: 12px 18px;
            border-radius: 16px; border-bottom-left-radius: 4px; box-shadow: 0 1px 4px rgba(0,0,0,0.06);
            gap: 4px;
        }
        .typing-indicator.active { display: flex; }
        .typing-indicator span {
            display: inline-block; width: 8px; height: 8px; background: #94a3b8;
            border-radius: 50%; animation: typing 1.4s infinite both;
        }
        .typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
        .typing-indicator span:nth-child(3) { animation-delay: 0.4s; }
        @keyframes typing {
            0%, 60%, 100% { transform: translateY(0); }
            30% { transform: translateY(-6px); }
        }
        .input-area {
            padding: 12px 16px; background: white; border-top: 1px solid #e2e8f0;
            display: flex; gap: 10px; align-items: center; flex-shrink: 0;
        }
        .input-area input {
            flex: 1; padding: 10px 16px; border: 2px solid #e2e8f0; border-radius: 24px;
            font-size: 14px; outline: none; transition: border 0.2s;
        }
        .input-area input:focus { border-color: #667eea; }
        .input-area .voice-btn {
            background: none; border: none; font-size: 22px; cursor: pointer;
            padding: 6px 8px; border-radius: 50%; transition: background 0.2s; color: #64748b;
        }
        .input-area .voice-btn:hover { background: #f1f5f9; }
        .input-area .voice-btn.recording { color: #ef4444; background: #fee2e2; animation: pulse 1s infinite; }
        .input-area .send-btn {
            padding: 10px 24px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white; border: none; border-radius: 24px; font-size: 14px; font-weight: 600;
            cursor: pointer; transition: transform 0.2s, opacity 0.2s; white-space: nowrap;
        }
        .input-area .send-btn:hover { transform: scale(1.02); }
        .input-area .send-btn:disabled { opacity: 0.6; cursor: not-allowed; transform: none; }
        .input-area .send-btn .spinner {
            display: inline-block; width: 16px; height: 16px;
            border: 2px solid rgba(255,255,255,0.3); border-top: 2px solid white;
            border-radius: 50%; animation: spin 0.8s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .footer-stats {
            padding: 6px 16px; background: #f8fafc; border-top: 1px solid #e2e8f0;
            font-size: 11px; color: #94a3b8; display: flex; justify-content: space-between;
            flex-shrink: 0; flex-wrap: wrap; gap: 4px;
        }
        @media (max-width: 600px) {
            .app-container { max-height: 100vh; border-radius: 0; height: 100vh; }
            .quick-questions button { font-size: 11px; padding: 4px 12px; }
            .header h1 { font-size: 15px; }
            .header-actions .lang-btn { font-size: 11px; padding: 3px 10px; }
        }
    </style>
</head>
<body>
    <div class="app-container">
        <div class="header">
            <div class="header-left">
                <span class="status-dot"></span>
                <div>
                    <h1>PSMZA AI Assistant</h1>
                    <div class="subtitle" id="headerSubtitle">Campus Information and Support</div>
                </div>
            </div>
            <div class="header-actions">
                <button class="lang-btn active" id="langEn" onclick="switchLanguage('en')">EN</button>
                <button class="lang-btn" id="langBm" onclick="switchLanguage('bm')">BM</button>
                <button class="reset-btn" onclick="resetChat()">New Chat</button>
            </div>
        </div>
        <div class="quick-questions" id="quickQuestions">
            <button onclick="askQuick('How to register for courses?')">Course Registration</button>
            <button onclick="askQuick('What are the tuition fees?')">Tuition Fees</button>
            <button onclick="askQuick('When is the semester break?')">Academic Calendar</button>
            <button onclick="askQuick('How to apply for hostel?')">Hostel Application</button>
        </div>
        <div class="messages" id="messages">
            <div class="message bot" id="welcomeMessage">
                Hello! I'm your campus AI assistant.<br>
                Ask me about <strong>courses, registration, fees, schedules,</strong> or any campus-related questions!
                <div class="message-actions">
                    <button onclick="copyMessage(this)">Copy</button>
                </div>
            </div>
        </div>
        <div class="typing-indicator" id="typing">
            <span></span><span></span><span></span>
        </div>
        <div class="input-area">
            <button class="voice-btn" id="voiceBtn" onclick="toggleVoice()" title="Voice Input">Mic</button>
            <input type="text" id="userInput" placeholder="Type your question..." />
            <button class="send-btn" id="sendBtn" onclick="sendMessage()">Send</button>
        </div>
        <div class="footer-stats">
            <span id="footerInfo">AI answers are based on campus information</span>
            <span id="feedbackStats">Feedback: 0</span>
        </div>
    </div>
    <script>
        var translations = {
            en: {
                headerSubtitle: 'Campus Information and Support',
                welcome: "Hello! I'm your campus AI assistant.<br>Ask me about <strong>courses, registration, fees, schedules,</strong> or any campus-related questions!",
                quickQuestions: ['Course Registration', 'Tuition Fees', 'Academic Calendar', 'Hostel Application'],
                quickActions: ['How to register for courses?', 'What are the tuition fees?', 'When is the semester break?', 'How to apply for hostel?'],
                placeholder: 'Type your question...',
                sendBtn: 'Send',
                resetBtn: 'New Chat',
                footerInfo: 'AI answers are based on campus information',
                copyBtn: 'Copy',
                helpful: 'Helpful',
                unhelpful: 'Not helpful',
                typing: 'Typing...',
                error: 'Connection error. Please try again.',
                feedbackThanks: 'Thank you!',
                feedbackRecorded: 'Feedback recorded',
                resetConfirm: 'Chat reset! How can I help you?'
            },
            bm: {
                headerSubtitle: 'Maklumat dan Sokongan Kampus',
                welcome: "Hai! Saya pembantu AI kampus anda.<br>Tanya saya tentang <strong>kursus, pendaftaran, yuran, jadual,</strong> atau apa-apa soalan berkaitan kampus!",
                quickQuestions: ['Pendaftaran Kursus', 'Yuran Pengajian', 'Kalendar Akademik', 'Permohonan Asrama'],
                quickActions: ['Bagaimana untuk mendaftar kursus?', 'Berapa yuran pengajian?', 'Bila cuti semester?', 'Bagaimana memohon asrama?'],
                placeholder: 'Taip soalan anda...',
                sendBtn: 'Hantar',
                resetBtn: 'Sesi Baru',
                footerInfo: 'Jawapan AI adalah berdasarkan maklumat kampus',
                copyBtn: 'Salin',
                helpful: 'Berguna',
                unhelpful: 'Tidak berguna',
                typing: 'Sedang menaip...',
                error: 'Ralat sambungan. Sila cuba lagi.',
                feedbackThanks: 'Terima kasih!',
                feedbackRecorded: 'Maklum balas direkod',
                resetConfirm: 'Sesi baharu! Bagaimana saya boleh membantu?'
            }
        };

        var currentLang = 'en';
        var sessionId = 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 6);
        var isStreaming = false;
        var isRecording = false;
        var recognition = null;

        var messagesContainer = document.getElementById('messages');
        var userInput = document.getElementById('userInput');
        var sendBtn = document.getElementById('sendBtn');
        var typingIndicator = document.getElementById('typing');
        var voiceBtn = document.getElementById('voiceBtn');
        var welcomeMessage = document.getElementById('welcomeMessage');

        function switchLanguage(lang) {
            currentLang = lang;
            document.getElementById('langEn').classList.toggle('active', lang === 'en');
            document.getElementById('langBm').classList.toggle('active', lang === 'bm');
            var t = translations[lang];
            document.getElementById('headerSubtitle').textContent = t.headerSubtitle;
            welcomeMessage.innerHTML = t.welcome;
            var qq = document.getElementById('quickQuestions');
            var btns = qq.querySelectorAll('button');
            btns.forEach(function(btn, i) {
                btn.textContent = t.quickQuestions[i];
                btn.onclick = function() { askQuick(t.quickActions[i]); };
            });
            userInput.placeholder = t.placeholder;
            sendBtn.textContent = t.sendBtn;
            document.getElementById('resetBtn').textContent = t.resetBtn;
            document.getElementById('footerInfo').textContent = t.footerInfo;
            document.querySelectorAll('.message.bot .message-actions button').forEach(function(btn) {
                var text = btn.textContent;
                if (text.includes('Copy') || text.includes('Salin')) btn.textContent = t.copyBtn;
                else if (text.includes('Helpful') || text.includes('Berguna')) btn.innerHTML = t.helpful;
                else if (text.includes('Not helpful') || text.includes('Tidak berguna')) btn.innerHTML = t.unhelpful;
            });
        }

        function addMessage(text, isUser, messageId) {
            var div = document.createElement('div');
            div.className = 'message ' + (isUser ? 'user' : 'bot');
            div.id = messageId || 'msg_' + Date.now();
            if (isUser) {
                div.textContent = text;
            } else {
                div.innerHTML = marked.parse(text);
                var t = translations[currentLang];
                var actions = document.createElement('div');
                actions.className = 'message-actions';
                actions.innerHTML = '<button onclick="copyMessage(this)">' + t.copyBtn + '</button><button onclick="feedback(this, &quot;helpful&quot;)">' + t.helpful + '</button><button onclick="feedback(this, &quot;unhelpful&quot;)">' + t.unhelpful + '</button>';
                div.appendChild(actions);
            }
            messagesContainer.appendChild(div);
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
            return div;
        }

        function showTyping(show) {
            typingIndicator.classList.toggle('active', show);
        }

        async function sendMessage() {
            var message = userInput.value.trim();
            if (!message || isStreaming) return;
            userInput.value = '';
            addMessage(message, true);
            showTyping(true);
            sendBtn.disabled = true;
            sendBtn.innerHTML = '...';
            isStreaming = true;
            try {
                await sendStreamingMessage(message);
            } catch (error) {
                var t = translations[currentLang];
                addMessage(t.error, false);
            } finally {
                showTyping(false);
                sendBtn.disabled = false;
                sendBtn.textContent = translations[currentLang].sendBtn;
                isStreaming = false;
            }
        }

        async function sendStreamingMessage(message) {
            var response = await fetch('/api/chat/stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: message, session_id: sessionId, language: currentLang })
            });
            if (!response.ok) throw new Error('HTTP ' + response.status);
            var reader = response.body.getReader();
            var decoder = new TextDecoder();
            var botDiv = null;
            var fullText = '';
            var t = translations[currentLang];
            while (true) {
                var result = await reader.read();
                if (result.done) break;
                var chunk = decoder.decode(result.value);
                var lines = chunk.split('\n');
                for (var i = 0; i < lines.length; i++) {
                    var line = lines[i];
                    if (line.startsWith('data: ')) {
                        var dataStr = line.slice(6);
                        if (dataStr === '[DONE]') continue;
                        try {
                            var data = JSON.parse(dataStr);
                            if (data.error) throw new Error(data.error);
                            if (data.done) {
                                if (botDiv) {
                                    var actions = botDiv.querySelector('.message-actions');
                                    if (actions) {
                                        actions.innerHTML = '<button onclick="copyMessage(this)">' + t.copyBtn + '</button><button onclick="feedback(this, &quot;helpful&quot;)">' + t.helpful + '</button><button onclick="feedback(this, &quot;unhelpful&quot;)">' + t.unhelpful + '</button>';
                                    }
                                }
                                break;
                            }
                            if (data.content) {
                                fullText += data.content;
                                if (!botDiv) {
                                    botDiv = addMessage(fullText, false);
                                } else {
                                    botDiv.innerHTML = marked.parse(fullText);
                                    var actions2 = document.createElement('div');
                                    actions2.className = 'message-actions';
                                    actions2.innerHTML = '<span style="color:#94a3b8;font-size:12px;">' + t.typing + '</span>';
                                    botDiv.appendChild(actions2);
                                }
                                messagesContainer.scrollTop = messagesContainer.scrollHeight;
                            }
                        } catch (e) {}
                    }
                }
            }
            if (!fullText) {
                addMessage('No response received. Please try again.', false);
            }
        }

        function askQuick(question) {
            userInput.value = question;
            sendMessage();
        }

        function copyMessage(btn) {
            var messageDiv = btn.closest('.message');
            var t = translations[currentLang];
            var text = messageDiv.textContent.replace(t.copyBtn, '').replace(t.helpful, '').replace(t.unhelpful, '').trim();
            navigator.clipboard.writeText(text).then(function() {
                var original = btn.textContent;
                btn.textContent = 'Copied!';
                setTimeout(function() { btn.textContent = original; }, 2000);
            }).catch(function() {
                var range = document.createRange();
                range.selectNode(messageDiv);
                window.getSelection().removeAllRanges();
                window.getSelection().addRange(range);
                document.execCommand('copy');
                btn.textContent = 'Copied!';
                setTimeout(function() { btn.textContent = t.copyBtn; }, 2000);
            });
        }

        async function feedback(btn, rating) {
            var messageDiv = btn.closest('.message');
            var t = translations[currentLang];
            var text = messageDiv.textContent.replace(t.copyBtn, '').replace(t.helpful, '').replace(t.unhelpful, '').trim();
            try {
                await fetch('/api/feedback', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ session_id: sessionId, message: text.slice(0, 200), rating: rating })
                });
                var buttons = messageDiv.querySelectorAll('.message-actions button');
                buttons.forEach(function(b) { b.style.opacity = '0.4'; b.style.pointerEvents = 'none'; });
                if (rating === 'helpful') {
                    btn.style.opacity = '1';
                    btn.innerHTML = ' <span class="feedback-text">' + t.feedbackThanks + '</span>';
                } else {
                    btn.style.opacity = '1';
                    btn.innerHTML = ' <span class="feedback-text">' + t.feedbackRecorded + '</span>';
                }
                updateFeedbackStats();
            } catch (e) {}
        }

        async function updateFeedbackStats() {
            try {
                var response = await fetch('/api/feedback/stats');
                var data = await response.json();
                document.getElementById('feedbackStats').textContent = 'Helpful: ' + data.helpful + ' | Not helpful: ' + data.unhelpful;
            } catch (e) {}
        }

        async function resetChat() {
            try {
                await fetch('/api/reset', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ session_id: sessionId })
                });
            } catch (e) {}
            while (messagesContainer.children.length > 0) {
                messagesContainer.removeChild(messagesContainer.lastChild);
            }
            var t = translations[currentLang];
            var welcome = document.createElement('div');
            welcome.className = 'message bot';
            welcome.innerHTML = t.resetConfirm;
            messagesContainer.appendChild(welcome);
            sessionId = 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 6);
        }

        function toggleVoice() {
            if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
                alert('Voice input not supported. Please use Chrome.');
                return;
            }
            if (isRecording) {
                if (recognition) recognition.stop();
                return;
            }
            var SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            recognition = new SpeechRecognition();
            recognition.lang = currentLang === 'bm' ? 'ms-MY' : 'en-US';
            recognition.interimResults = true;
            recognition.continuous = false;
            recognition.onstart = function() {
                isRecording = true;
                voiceBtn.classList.add('recording');
                voiceBtn.textContent = 'Stop';
            };
            recognition.onresult = function(event) {
                var transcript = '';
                for (var i = event.resultIndex; i < event.results.length; i++) {
                    transcript += event.results[i][0].transcript;
                }
                userInput.value = transcript;
            };
            recognition.onend = function() {
                isRecording = false;
                voiceBtn.classList.remove('recording');
                voiceBtn.textContent = 'Mic';
                if (userInput.value.trim()) {
                    sendMessage();
                }
            };
            recognition.onerror = function() {
                isRecording = false;
                voiceBtn.classList.remove('recording');
                voiceBtn.textContent = 'Mic';
            };
            recognition.start();
        }

        userInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });

        var API_BASE = window.location.origin;
        updateFeedbackStats();
        setInterval(updateFeedbackStats, 30000);
    </script>
</body>
</html>
    """
    return render_template_string(html)

if __name__ == '__main__':
    print("=" * 50)
    print("PSMZA Campus AI Assistant - Bilingual (EN + BM)")
    print("=" * 50)
    print("Local URL: http://127.0.0.1:5000")
    print("Network URL: http://0.0.0.0:5000")
    print("=" * 50)
    print("Features:")
    print("  - Multi-turn conversation")
    print("  - Quick question buttons")
    print("  - Markdown rendering")
    print("  - Copy message")
    print("  - Helpful/Unhelpful feedback")
    print("  - Voice input (Chrome)")
    print("  - Typewriter effect (streaming)")
    print("  - Bilingual (EN + BM) with toggle")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)