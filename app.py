from flask import Flask, request, render_template_string, jsonify, send_from_directory
import requests
import datetime
import os
from functools import wraps
from collections import defaultdict
import time
import random
import hashlib

app = Flask(__name__)
app.secret_key = 'everyday-best-secret-key-2025'

# Конфигурация Telegram бота
BOT_TOKEN = "7979134834:AAFrlEVWSPaaf3XQezHylDBb4QBiRNOAR20"
CHAT_ID = "-1002968186080"

# Защита от DDoS
REQUEST_LIMIT = 15
REQUEST_WINDOW = 60

# Хранилища
ip_requests = defaultdict(list)
captcha_sessions = {}

# Эмодзи для капчи-пазлов
puzzle_emojis = {
    '🐱': 'cat',
    '🐶': 'dog', 
    '🐰': 'rabbit',
    '🐻': 'bear',
    '🐵': 'monkey',
    '🐯': 'tiger',
    '🦁': 'lion',
    '🐮': 'cow',
    '🐷': 'pig',
    '🐸': 'frog'
}

def check_request_limit(ip):
    """Проверяет лимит запросов для IP"""
    now = time.time()
    ip_requests[ip] = [timestamp for timestamp in ip_requests[ip] if now - timestamp < REQUEST_WINDOW]
    
    if len(ip_requests[ip]) >= REQUEST_LIMIT:
        return False
    ip_requests[ip].append(now)
    return True

def get_client_ip():
    """Получает реальный IP клиента"""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    return request.remote_addr

def get_country_code(ip):
    """Определяет страну по IP используя несколько API"""
    # Попробуем ipapi.co
    try:
        response = requests.get(f'http://ipapi.co/{ip}/country/', timeout=2)
        if response.status_code == 200:
            country = response.text.strip()
            if country and country != 'Undefined':
                return country
    except:
        pass
    
    # Попробуем ip-api.com
    try:
        response = requests.get(f'http://ip-api.com/json/{ip}', timeout=2)
        if response.status_code == 200:
            data = response.json()
            if data['status'] == 'success':
                return data['countryCode']
    except:
        pass
    
    # Fallback по IP диапазонам
    if ip.startswith(('46.', '176.', '37.', '91.', '195.')):
        return 'UA'
    elif ip.startswith(('77.', '178.', '95.', '31.', '5.')):
        return 'RU'
    elif ip.startswith(('192.168.', '10.', '172.')):
        return 'LAN'
    elif ip == '127.0.0.1':
        return 'LOCAL'
    
    return 'Unknown'

def get_browser_info(user_agent):
    """Определяет браузер и ОС"""
    ua = user_agent.lower()
    
    # Определение ОС
    if 'windows' in ua:
        os_name = 'Windows'
    elif 'mac' in ua:
        os_name = 'Mac OS'
    elif 'linux' in ua:
        os_name = 'Linux'
    elif 'android' in ua:
        os_name = 'Android'
    elif 'iphone' in ua or 'ipad' in ua:
        os_name = 'iOS'
    else:
        os_name = 'Unknown'
    
    # Определение браузера
    if 'chrome' in ua and 'edg' not in ua:
        browser = 'Chrome'
    elif 'firefox' in ua:
        browser = 'Firefox'
    elif 'safari' in ua and 'chrome' not in ua:
        browser = 'Safari'
    elif 'edg' in ua:
        browser = 'Edge'
    elif 'opera' in ua:
        browser = 'Opera'
    else:
        browser = 'Unknown'
    
    return os_name, browser

def is_suspicious_user_agent(user_agent):
    """Проверяет подозрительный User-Agent"""
    if not user_agent or len(user_agent) < 10:
        return True
        
    ua = user_agent.lower()
    
    bots = ['bot', 'crawler', 'spider', 'scraper', 'python', 'curl', 'wget', 'scan']
    if any(bot in ua for bot in bots):
        return True
        
    suspicious_patterns = ['sql', 'admin', 'shell', 'cmd', 'exploit']
    if any(pattern in ua for pattern in suspicious_patterns):
        return True
        
    return False

def generate_puzzle_captcha(ip):
    """Генерирует капчу-пазл"""
    # Выбираем случайное целевое животное
    target_emoji = random.choice(list(puzzle_emojis.keys()))
    session_id = hashlib.md5(f"{ip}{time.time()}".encode()).hexdigest()[:16]
    
    # Создаем список эмодзи для пазла (включая целевое)
    puzzle_emojis_list = [target_emoji]
    while len(puzzle_emojis_list) < 6:
        random_emoji = random.choice(list(puzzle_emojis.keys()))
        if random_emoji not in puzzle_emojis_list:
            puzzle_emojis_list.append(random_emoji)
    
    random.shuffle(puzzle_emojis_list)
    
    captcha_sessions[session_id] = {
        'ip': ip,
        'target_emoji': target_emoji,
        'target_name': puzzle_emojis[target_emoji],
        'puzzle_emojis': puzzle_emojis_list,
        'created_at': time.time(),
        'attempts': 0
    }
    
    return session_id, target_emoji, puzzle_emojis[target_emoji], puzzle_emojis_list

def verify_puzzle_captcha(session_id, selected_position):
    """Проверяет капчу-пазл"""
    if session_id not in captcha_sessions:
        return False
        
    session = captcha_sessions[session_id]
    
    # Очистка старых сессий
    if time.time() - session['created_at'] > 300:
        del captcha_sessions[session_id]
        return False
    
    session['attempts'] += 1
    
    if session['attempts'] > 3:
        del captcha_sessions[session_id]
        return False
    
    # Проверяем, что выбран правильный пазл
    try:
        selected_index = int(selected_position)
        if 0 <= selected_index < len(session['puzzle_emojis']):
            if session['puzzle_emojis'][selected_index] == session['target_emoji']:
                del captcha_sessions[session_id]
                return True
    except:
        pass
    
    return False

def send_telegram_log(ip, user_agent, path, url, referer, accept_language, status="✅ Нормальный", captcha_triggered=False):
    """Отправляет лог в Telegram"""
    country = get_country_code(ip)
    os_name, browser = get_browser_info(user_agent)
    xff = request.headers.get('X-Forwarded-For', ip)
    
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    captcha_info = "🔒 Капча активирована" if captcha_triggered else ""
    
    message = f"""
🔔 Новое подключение {status}
⏰ {timestamp}
🌐 IP: {ip} ({country})
💻 ОС: {os_name}
🌍 Браузер: {browser}
📄 Страница: {path}
🔗 URL: {url}
↩️ Referer: {referer}
🗣 Язык: {accept_language.split(',')[0] if accept_language else 'Unknown'}
📶 XFF: {xff}
🛡️ Статус: {status}
{captcha_info}
    """.strip()
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    
    try:
        requests.post(url, data=data, timeout=5)
    except:
        pass

def browser_required(f):
    """Декоратор для проверки браузера"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_agent = request.headers.get('User-Agent', '')
        client_ip = get_client_ip()
        
        # Проверяем подозрительный User-Agent
        if is_suspicious_user_agent(user_agent):
            referer = request.headers.get('Referer', '')
            accept_language = request.headers.get('Accept-Language', '')
            
            # Генерируем капчу-пазл
            session_id, target_emoji, target_name, puzzle_emojis = generate_puzzle_captcha(client_ip)
            
            send_telegram_log(client_ip, user_agent, request.path, request.url, 
                            referer, accept_language, "🚨 Требуется капча", True)
            
            return render_template_string(PUZZLE_CAPTCHA_TEMPLATE, 
                                       session_id=session_id, 
                                       target_emoji=target_emoji,
                                       target_name=target_name,
                                       puzzle_emojis=puzzle_emojis), 403
            
        if not check_request_limit(client_ip):
            return jsonify({"error": "Rate limit exceeded"}), 429
        
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
@browser_required
def index():
    """Главная страница"""
    client_ip = get_client_ip()
    user_agent = request.headers.get('User-Agent', '')
    referer = request.headers.get('Referer', '')
    accept_language = request.headers.get('Accept-Language', '')
    
    send_telegram_log(client_ip, user_agent, '/', request.url, referer, accept_language)
    
    return render_template_string(HTML_CONTENT)

@app.route('/verify-puzzle-captcha', methods=['POST'])
def verify_puzzle_captcha_route():
    """Проверяет капчу-пазл"""
    data = request.get_json()
    if not data or 'session_id' not in data or 'position' not in data:
        return jsonify({'success': False, 'error': 'Invalid data'})
    
    session_id = data['session_id']
    selected_position = data['position']
    
    if verify_puzzle_captcha(session_id, selected_position):
        return jsonify({'success': True, 'redirect': '/'})
    else:
        return jsonify({'success': False, 'error': 'Неверный выбор. Попробуйте снова.'})

@app.route('/favicon.ico')
def favicon():
    """Обслуживает favicon"""
    return send_from_directory(os.path.join(app.root_path, 'static'), 
                             'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/health')
def health():
    """Эндпоинт для проверки здоровья"""
    return jsonify({"status": "healthy", "timestamp": datetime.datetime.now().isoformat()})

# HTML шаблон для капчи-пазла
PUZZLE_CAPTCHA_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Проверка безопасности - EveryDay</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Montserrat', sans-serif;
        }
        
        body {
            background: linear-gradient(135deg, #667eea, #764ba2);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        
        .captcha-container {
            background: rgba(255, 255, 255, 0.95);
            padding: 40px;
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
            text-align: center;
            max-width: 500px;
            width: 100%;
            animation: slideIn 0.5s ease-out;
        }
        
        .captcha-header {
            margin-bottom: 30px;
        }
        
        .captcha-icon {
            font-size: 3rem;
            margin-bottom: 15px;
            animation: bounce 2s infinite;
        }
        
        .captcha-title {
            font-size: 1.8rem;
            margin-bottom: 10px;
            color: #333;
            font-weight: 600;
        }
        
        .captcha-text {
            font-size: 1.1rem;
            color: #666;
            line-height: 1.5;
        }
        
        .target-section {
            background: linear-gradient(135deg, #ff6b6b, #ff8e8e);
            padding: 20px;
            border-radius: 15px;
            margin: 25px 0;
            color: white;
        }
        
        .target-emoji {
            font-size: 3rem;
            margin-bottom: 10px;
        }
        
        .target-name {
            font-size: 1.3rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .puzzle-section {
            margin: 30px 0;
        }
        
        .puzzle-title {
            font-size: 1.2rem;
            margin-bottom: 20px;
            color: #333;
            font-weight: 500;
        }
        
        .puzzle-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 15px;
            margin-bottom: 25px;
        }
        
        .puzzle-piece {
            font-size: 2.5rem;
            background: #f8f9fa;
            border: 3px solid #e9ecef;
            border-radius: 15px;
            padding: 20px;
            cursor: pointer;
            transition: all 0.3s ease;
            user-select: none;
        }
        
        .puzzle-piece:hover {
            transform: scale(1.05);
            border-color: #667eea;
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.3);
        }
        
        .puzzle-piece.selected {
            border-color: #4CAF50;
            background: #e8f5e8;
            transform: scale(1.1);
        }
        
        .verify-button {
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            border: none;
            padding: 15px 30px;
            font-size: 1.1rem;
            font-weight: 600;
            border-radius: 25px;
            cursor: pointer;
            transition: all 0.3s ease;
            width: 100%;
            max-width: 200px;
        }
        
        .verify-button:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }
        
        .verify-button:disabled {
            background: #ccc;
            cursor: not-allowed;
        }
        
        .message {
            margin-top: 20px;
            padding: 10px;
            border-radius: 10px;
            font-weight: 500;
            display: none;
        }
        
        .success-message {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        
        .error-message {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        
        @keyframes slideIn {
            from { transform: translateY(-50px); opacity: 0; }
            to { transform: translateY(0); opacity: 1; }
        }
        
        @keyframes bounce {
            0%, 20%, 50%, 80%, 100% { transform: translateY(0); }
            40% { transform: translateY(-10px); }
            60% { transform: translateY(-5px); }
        }
        
        @media (max-width: 480px) {
            .captcha-container {
                padding: 20px;
            }
            
            .captcha-title {
                font-size: 1.5rem;
            }
            
            .target-emoji {
                font-size: 2.5rem;
            }
            
            .puzzle-piece {
                font-size: 2rem;
                padding: 15px;
            }
            
            .puzzle-grid {
                grid-template-columns: repeat(2, 1fr);
            }
        }
    </style>
</head>
<body>
    <div class="captcha-container">
        <div class="captcha-header">
            <div class="captcha-icon">🛡️</div>
            <h1 class="captcha-title">Проверка безопасности</h1>
            <p class="captcha-text">Подтвердите, что вы не робот. Выберите правильное животное:</p>
        </div>
        
        <div class="target-section">
            <div class="target-emoji">{{ target_emoji }}</div>
            <div class="target-name">{{ target_name }}</div>
        </div>
        
        <div class="puzzle-section">
            <div class="puzzle-title">Выберите соответствующее животное:</div>
            <div class="puzzle-grid">
                {% for i, emoji in enumerate(puzzle_emojis) %}
                <div class="puzzle-piece" data-position="{{ i }}" data-emoji="{{ emoji }}">
                    {{ emoji }}
                </div>
                {% endfor %}
            </div>
            
            <button class="verify-button" id="verifyButton" disabled>Проверить</button>
        </div>
        
        <div class="message success-message" id="successMessage">
            ✅ Проверка пройдена! Перенаправление...
        </div>
        <div class="message error-message" id="errorMessage">
            ❌ Неверный выбор. Попробуйте снова.
        </div>
        
        <input type="hidden" id="sessionId" value="{{ session_id }}">
    </div>

    <script>
        const sessionId = document.getElementById('sessionId').value;
        const verifyButton = document.getElementById('verifyButton');
        const successMessage = document.getElementById('successMessage');
        const errorMessage = document.getElementById('errorMessage');
        const puzzlePieces = document.querySelectorAll('.puzzle-piece');
        
        let selectedPosition = null;
        
        // Обработчики для пазлов
        puzzlePieces.forEach(piece => {
            piece.addEventListener('click', function() {
                // Снимаем выделение со всех пазлов
                puzzlePieces.forEach(p => p.classList.remove('selected'));
                
                // Выделяем выбранный пазл
                this.classList.add('selected');
                selectedPosition = this.getAttribute('data-position');
                
                // Активируем кнопку проверки
                verifyButton.disabled = false;
            });
        });
        
        // Обработчик для кнопки проверки
        verifyButton.addEventListener('click', function() {
            if (selectedPosition === null) return;
            
            verifyButton.disabled = true;
            verifyButton.textContent = 'Проверка...';
            
            fetch('/verify-puzzle-captcha', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    session_id: sessionId,
                    position: selectedPosition
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    successMessage.style.display = 'block';
                    errorMessage.style.display = 'none';
                    setTimeout(() => {
                        window.location.href = '/';
                    }, 1000);
                } else {
                    errorMessage.style.display = 'block';
                    successMessage.style.display = 'none';
                    verifyButton.disabled = false;
                    verifyButton.textContent = 'Проверить';
                    
                    // Сбрасываем выбор
                    puzzlePieces.forEach(p => p.classList.remove('selected'));
                    selectedPosition = null;
                    
                    setTimeout(() => {
                        errorMessage.style.display = 'none';
                    }, 3000);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                errorMessage.textContent = '❌ Ошибка соединения';
                errorMessage.style.display = 'block';
                verifyButton.disabled = false;
                verifyButton.textContent = 'Проверить';
            });
        });
        
        // Автоматическая очистка через 5 минут
        setTimeout(() => {
            if (!successMessage.style.display || successMessage.style.display === 'none') {
                alert('Время проверки истекло. Страница будет перезагружена.');
                location.reload();
            }
        }, 300000);
    </script>
</body>
</html>
"""

# Основной HTML контент с красивым дизайном
HTML_CONTENT = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EveryDay the best</title>
    <link rel="icon" href="/favicon.ico" type="image/x-icon">
    <link rel="preconnect" href="https://cdnjs.cloudflare.com" crossorigin>
    <link rel="preconnect" href="https://fonts.googleapis.com" crossorigin>
    <link rel="preload" as="style" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <link rel="preload" as="style" href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700&display=swap">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700&display=swap">
    
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Montserrat', sans-serif;
        }
        
        body {
            background: linear-gradient(135deg, #1a2980, #26d0ce);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
            color: white;
            overflow-x: hidden;
        }
        
        .container {
            width: 100%;
            max-width: 900px;
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(15px);
            border-radius: 20px;
            overflow: hidden;
            box-shadow: 0 15px 35px rgba(0, 0, 0, 0.2);
            border: 1px solid rgba(255, 255, 255, 0.2);
            animation: fadeIn 1s ease-out;
        }
        
        .bubble {
            position: absolute;
            border-radius: 50%;
            background: rgba(255, 255, 255, 0.05);
            z-index: -1;
            animation: float 8s infinite ease-in-out;
        }
        
        .bubble:nth-child(1) { width: 120px; height: 120px; top: 10%; left: 10%; }
        .bubble:nth-child(2) { width: 80px; height: 80px; bottom: 20%; right: 15%; animation-delay: -2s; }
        .bubble:nth-child(3) { width: 60px; height: 60px; top: 40%; right: 20%; animation-delay: -4s; }
        
        @keyframes float {
            0%, 100% { transform: translateY(0) translateX(0); }
            50% { transform: translateY(-20px) translateX(10px); }
        }
        
        .header {
            text-align: center;
            padding: 40px 30px;
            background: rgba(0, 0, 0, 0.2);
            position: relative;
        }
        
        .logo {
            font-size: 4rem;
            margin-bottom: 15px;
            animation: pulse 2s infinite;
        }
        
        h1 {
            font-size: 2.8rem;
            background: linear-gradient(to right, #4df1ff, #a6f6ff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
        }
        
        .tabs {
            display: flex;
            background: rgba(0, 0, 0, 0.25);
        }
        
        .tab {
            flex: 1;
            text-align: center;
            padding: 20px;
            cursor: pointer;
            transition: all 0.3s ease;
            border-bottom: 3px solid transparent;
        }
        
        .tab.active {
            background: rgba(0, 195, 255, 0.3);
            border-bottom-color: #00c3ff;
        }
        
        .tab:hover {
            background: rgba(0, 195, 255, 0.2);
        }
        
        .content {
            padding: 30px;
            min-height: 400px;
        }
        
        .tab-content {
            display: none;
            animation: slideIn 0.3s ease;
        }
        
        .tab-content.active {
            display: block;
        }
        
        .link-list {
            list-style: none;
        }
        
        .link-item {
            background: rgba(255, 255, 255, 0.1);
            margin: 15px 0;
            padding: 20px;
            border-radius: 15px;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            cursor: pointer;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .link-item:hover {
            background: rgba(255, 255, 255, 0.15);
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
        }
        
        .link-item i {
            font-size: 1.5rem;
            margin-right: 15px;
            width: 40px;
            color: #4df1ff;
        }
        
        .link-item .title {
            font-size: 1.2rem;
            font-weight: 600;
        }
        
        .soon-banner {
            display: flex;
            justify-content: center;
            align-items: center;
            height: 200px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 15px;
            border: 2px dashed rgba(255, 255, 255, 0.3);
        }
        
        .soon-text {
            font-size: 3rem;
            font-weight: 700;
            background: linear-gradient(45deg, #ff00cc, #00ccff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            animation: pulse 2s infinite;
        }
        
        .footer {
            text-align: center;
            padding: 20px;
            background: rgba(0, 0, 0, 0.2);
            font-size: 0.9rem;
            color: rgba(255, 255, 255, 0.8);
        }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        @keyframes pulse {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.05); }
        }
        
        @keyframes slideIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        @media (max-width: 768px) {
            .header { padding: 30px 20px; }
            h1 { font-size: 2.2rem; }
            .logo { font-size: 3rem; }
            .content { padding: 20px; }
            .tab { padding: 15px 10px; }
            .soon-text { font-size: 2rem; }
        }
    </style>
</head>
<body>
    <div class="bubble"></div>
    <div class="bubble"></div>
    <div class="bubble"></div>
    
    <div class="container">
        <div class="header">
            <div class="logo">✨</div>
            <h1>EveryDay the best</h1>
            <p>EveryDay bio | Заместитель создателя канала PrankVZ</p>
        </div>
        
        <div class="tabs">
            <div class="tab active" data-tab="general">
                <i class="fas fa-home"></i> General
            </div>
            <div class="tab" data-tab="nft">
                <i class="fas fa-coins"></i> NFT
            </div>
            <div class="tab" data-tab="softs">
                <i class="fas fa-download"></i> Softs
            </div>
        </div>
        
        <div class="content">
            <div class="tab-content active" id="general">
                <ul class="link-list">
                    <li class="link-item" data-url="https://t.me/prankvz">
                        <i class="fab fa-telegram"></i>
                        <div class="title">Канал Telegram 📢</div>
                    </li>
                    <li class="link-item" data-url="https://t.me/mobile_everyday">
                        <i class="fab fa-telegram"></i>
                        <div class="title">Telegram Everyday 💬</div>
                    </li>
                    <li class="link-item" data-url="https://t.me/+m59rdlf7pUY2Mjk9">
                        <i class="fas fa-comments"></i>
                        <div class="title">Чат сообщества 👥</div>
                    </li>
                </ul>
            </div>
            
            <div class="tab-content" id="nft">
                <div class="soon-banner">
                    <div class="soon-text">Soon...</div>
                </div>
            </div>
            
            <div class="tab-content" id="softs">
                <ul class="link-list">
                    <li class="link-item" data-url="https://drive.google.com/uc?export=download&id=1a4uqsLWD_5vCMNMDmr8Mr0mzh0OmtF6r">
                        <i class="fas fa-download"></i>
                        <div class="title">Blue Hikvision 📥</div>
                    </li>
                    <li class="link-item" data-url="https://drive.google.com/uc?export=download&id=1tVPe7sceTvmZJKL5Y0L1IrsgIwWIkUtk">
                        <i class="fas fa-server"></i>
                        <div class="title">Ingram 📥</div>
                    </li>
                    <li class="link-item" data-url="https://drive.google.com/uc?export=download&id=1Kl9CvZn2qqTtJUi1toUZKnBKyrOG17Cx">
                        <i class="fas fa-key"></i>
                        <div class="title">Generate Pass and User 🔑</div>
                    </li>
                    <li class="link-item" data-url="https://drive.google.com/uc?export=download&id=1PrWY16XUyADSi6K5aT9YmN7xPsHI9Uhk">
                        <i class="fas fa-sun"></i>
                        <div class="title">Noon 🌞</div>
                    </li>
                </ul>
            </div>
        </div>
        
        <div class="footer">
            <p>® 2025 EveryDay the best | Все права защищены</p>
            <p>by @mobile_everyday</p>
        </div>
    </div>
    
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            // Переключение вкладок
            const tabs = document.querySelectorAll('.tab');
            tabs.forEach(tab => {
                tab.addEventListener('click', function() {
                    tabs.forEach(t => t.classList.remove('active'));
                    this.classList.add('active');
                    
                    document.querySelectorAll('.tab-content').forEach(content => {
                        content.classList.remove('active');
                    });
                    
                    const tabId = this.getAttribute('data-tab');
                    document.getElementById(tabId).classList.add('active');
                });
            });
            
            // Обработка кликов по ссылкам
            document.querySelectorAll('.link-item').forEach(item => {
                item.addEventListener('click', function() {
                    const url = this.getAttribute('data-url');
                    if (url) {
                        window.open(url, '_blank');
                    }
                });
            });
        });
    </script>
</body>
</html>
"""

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
