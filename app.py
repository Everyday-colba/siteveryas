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
REQUEST_LIMIT = 20
REQUEST_WINDOW = 60

# Хранилища
ip_requests = defaultdict(list)
captcha_sessions = {}

# Улучшенные эмодзи для капчи с категориями
puzzle_categories = {
    'животные': {
        '🐱': 'кошка',
        '🐶': 'собака', 
        '🐰': 'кролик',
        '🐻': 'медведь',
        '🐵': 'обезьяна',
        '🐯': 'тигр',
        '🦁': 'лев',
        '🐮': 'корова',
        '🐷': 'свинья',
        '🐸': 'лягушка',
        '🐼': 'панда',
        '🦊': 'лиса'
    },
    'еда': {
        '🍎': 'яблоко',
        '🍕': 'пицца',
        '🍔': 'бургер',
        '🍦': 'мороженое',
        '🍩': 'пончик',
        '🍰': 'торт',
        '🍫': 'шоколад',
        '🍓': 'клубника',
        '🍇': 'виноград',
        '🥑': 'авокадо'
    },
    'транспорт': {
        '🚗': 'машина',
        '✈️': 'самолет',
        '🚂': 'поезд',
        '🚲': 'велосипед',
        '🚀': 'ракета',
        '🛴': 'самокат',
        '🚁': 'вертолет',
        '🚤': 'катер',
        '🛸': 'летающая тарелка'
    }
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
    """Определяет страну по IP"""
    if ip.startswith(('192.168.', '10.', '172.', '127.0.0.1')):
        return 'LOCAL'
    
    try:
        response = requests.get(f'http://ip-api.com/json/{ip}?fields=countryCode', timeout=2)
        if response.status_code == 200:
            data = response.json()
            return data.get('countryCode', 'Unknown')
    except:
        pass
    
    # Fallback по IP диапазонам
    if ip.startswith(('46.', '176.', '37.', '91.', '195.', '31.43.')):
        return 'UA'
    elif ip.startswith(('77.', '178.', '95.', '5.', '2a02:')):
        return 'RU'
    elif ip.startswith(('8.8.', '1.1.')):
        return 'DNS'
    
    return 'Unknown'

def get_browser_info(user_agent):
    """Определяет браузер и ОС"""
    if not user_agent:
        return 'Unknown', 'Unknown'
        
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
    
    bots = ['bot', 'crawler', 'spider', 'scraper', 'python', 'curl', 'wget', 'scan', 'headless']
    if any(bot in ua for bot in bots):
        return True
        
    suspicious_patterns = ['sql', 'admin', 'shell', 'cmd', 'exploit', 'select', 'union']
    if any(pattern in ua for pattern in suspicious_patterns):
        return True
        
    return False

def generate_puzzle_captcha(ip):
    """Генерирует улучшенную капчу-пазл"""
    try:
        # Выбираем случайную категорию
        category_name = random.choice(list(puzzle_categories.keys()))
        category = puzzle_categories[category_name]
        
        # Выбираем целевое изображение
        target_emoji = random.choice(list(category.keys()))
        session_id = hashlib.md5(f"{ip}{time.time()}".encode()).hexdigest()[:16]
        
        # Создаем список изображений для выбора
        puzzle_items = [target_emoji]
        while len(puzzle_items) < 9:  # 3x3 сетка
            random_item = random.choice(list(category.keys()))
            if random_item not in puzzle_items:
                puzzle_items.append(random_item)
        
        random.shuffle(puzzle_items)
        
        captcha_sessions[session_id] = {
            'ip': ip,
            'target_emoji': target_emoji,
            'target_name': category[target_emoji],
            'category': category_name,
            'puzzle_items': puzzle_items,
            'created_at': time.time(),
            'attempts': 0
        }
        
        return session_id, target_emoji, category[target_emoji], category_name, puzzle_items
    except Exception as e:
        # Fallback на простую капчу
        target_emoji = '🐱'
        session_id = hashlib.md5(f"{ip}{time.time()}".encode()).hexdigest()[:16]
        puzzle_items = ['🐱', '🐶', '🐰', '🐻', '🐵', '🐯', '🦁', '🐮', '🐷']
        
        captcha_sessions[session_id] = {
            'ip': ip,
            'target_emoji': target_emoji,
            'target_name': 'кошка',
            'category': 'животные',
            'puzzle_items': puzzle_items,
            'created_at': time.time(),
            'attempts': 0
        }
        
        return session_id, target_emoji, 'кошка', 'животные', puzzle_items

def verify_puzzle_captcha(session_id, selected_position):
    """Проверяет капчу-пазл"""
    try:
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
        
        # Проверяем, что выбран правильный элемент
        selected_index = int(selected_position)
        if 0 <= selected_index < len(session['puzzle_items']):
            if session['puzzle_items'][selected_index] == session['target_emoji']:
                del captcha_sessions[session_id]
                return True
                
        return False
    except:
        return False

def send_telegram_log(ip, user_agent, path, url, referer, accept_language, status="✅ Нормальный", captcha_triggered=False):
    """Отправляет лог в Telegram"""
    try:
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
        
        requests.post(url, data=data, timeout=3)
    except:
        pass

def browser_required(f):
    """Декоратор для проверки браузера"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            user_agent = request.headers.get('User-Agent', '')
            client_ip = get_client_ip()
            
            # Проверяем подозрительный User-Agent
            if is_suspicious_user_agent(user_agent):
                referer = request.headers.get('Referer', '')
                accept_language = request.headers.get('Accept-Language', '')
                
                # Генерируем капчу-пазл
                session_id, target_emoji, target_name, category_name, puzzle_items = generate_puzzle_captcha(client_ip)
                
                send_telegram_log(client_ip, user_agent, request.path, request.url, 
                                referer, accept_language, "🚨 Требуется капча", True)
                
                return render_template_string(PUZZLE_CAPTCHA_TEMPLATE, 
                                           session_id=session_id, 
                                           target_emoji=target_emoji,
                                           target_name=target_name,
                                           category_name=category_name,
                                           puzzle_items=puzzle_items), 403
                
            if not check_request_limit(client_ip):
                return jsonify({"error": "Rate limit exceeded"}), 429
            
            return f(*args, **kwargs)
        except Exception as e:
            return f(*args, **kwargs)
    return decorated_function

@app.route('/')
@browser_required
def index():
    """Главная страница"""
    try:
        client_ip = get_client_ip()
        user_agent = request.headers.get('User-Agent', '')
        referer = request.headers.get('Referer', '')
        accept_language = request.headers.get('Accept-Language', '')
        
        send_telegram_log(client_ip, user_agent, '/', request.url, referer, accept_language)
    except:
        pass
    
    return render_template_string(HTML_CONTENT)

@app.route('/verify-puzzle-captcha', methods=['POST'])
def verify_puzzle_captcha_route():
    """Проверяет капчу-пазл"""
    try:
        data = request.get_json()
        if not data or 'session_id' not in data or 'position' not in data:
            return jsonify({'success': False, 'error': 'Invalid data'})
        
        session_id = data['session_id']
        selected_position = data['position']
        
        if verify_puzzle_captcha(session_id, selected_position):
            return jsonify({'success': True, 'redirect': '/'})
        else:
            return jsonify({'success': False, 'error': 'Неверный выбор. Попробуйте снова.'})
    except:
        return jsonify({'success': False, 'error': 'Ошибка сервера'})

@app.route('/favicon.ico')
def favicon():
    """Обслуживает favicon"""
    try:
        return send_from_directory(os.path.join(app.root_path, 'static'), 
                                 'favicon.ico', mimetype='image/vnd.microsoft.icon')
    except:
        return '', 204

@app.route('/health')
def health():
    """Эндпоинт для проверки здоровья"""
    return jsonify({"status": "healthy", "timestamp": datetime.datetime.now().isoformat()})

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

# Улучшенный HTML шаблон для капчи
PUZZLE_CAPTCHA_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Проверка безопасности - EveryDay</title>
    <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Montserrat', sans-serif;
        }
        
        body {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        
        .captcha-container {
            background: rgba(255, 255, 255, 0.95);
            padding: 40px;
            border-radius: 25px;
            box-shadow: 0 25px 50px rgba(0, 0, 0, 0.15);
            text-align: center;
            max-width: 500px;
            width: 100%;
            animation: slideInUp 0.6s ease-out;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        
        .captcha-header {
            margin-bottom: 30px;
        }
        
        .captcha-icon {
            font-size: 4rem;
            margin-bottom: 20px;
            animation: bounce 2s infinite;
            background: linear-gradient(135deg, #667eea, #764ba2);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .captcha-title {
            font-size: 2rem;
            margin-bottom: 10px;
            color: #2d3748;
            font-weight: 700;
            background: linear-gradient(135deg, #2d3748, #4a5568);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .captcha-text {
            font-size: 1.1rem;
            color: #718096;
            line-height: 1.6;
        }
        
        .category-badge {
            display: inline-block;
            background: linear-gradient(135deg, #48bb78, #38a169);
            color: white;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 0.9rem;
            font-weight: 600;
            margin: 10px 0;
        }
        
        .target-section {
            background: linear-gradient(135deg, #ff6b6b, #ff8e8e);
            padding: 25px;
            border-radius: 20px;
            margin: 25px 0;
            color: white;
            box-shadow: 0 10px 25px rgba(255, 107, 107, 0.3);
            position: relative;
            overflow: hidden;
        }
        
        .target-section::before {
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%);
        }
        
        .target-emoji {
            font-size: 4rem;
            margin-bottom: 15px;
            filter: drop-shadow(0 5px 15px rgba(0,0,0,0.2));
            animation: pulse 2s infinite;
        }
        
        .target-name {
            font-size: 1.5rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 2px;
            text-shadow: 0 2px 4px rgba(0,0,0,0.3);
        }
        
        .puzzle-section {
            margin: 30px 0;
        }
        
        .puzzle-title {
            font-size: 1.3rem;
            margin-bottom: 25px;
            color: #2d3748;
            font-weight: 600;
        }
        
        .puzzle-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 12px;
            margin-bottom: 30px;
        }
        
        .puzzle-piece {
            font-size: 2.2rem;
            background: linear-gradient(135deg, #f7fafc, #edf2f7);
            border: 3px solid #e2e8f0;
            border-radius: 15px;
            padding: 20px;
            cursor: pointer;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            user-select: none;
            position: relative;
            overflow: hidden;
        }
        
        .puzzle-piece::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.4), transparent);
            transition: left 0.5s;
        }
        
        .puzzle-piece:hover {
            transform: translateY(-5px) scale(1.05);
            border-color: #667eea;
            box-shadow: 0 10px 25px rgba(102, 126, 234, 0.3);
        }
        
        .puzzle-piece:hover::before {
            left: 100%;
        }
        
        .puzzle-piece.selected {
            border-color: #48bb78;
            background: linear-gradient(135deg, #c6f6d5, #9ae6b4);
            transform: scale(1.1);
            box-shadow: 0 8px 20px rgba(72, 187, 120, 0.4);
        }
        
        .verify-button {
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            border: none;
            padding: 18px 40px;
            font-size: 1.2rem;
            font-weight: 600;
            border-radius: 30px;
            cursor: pointer;
            transition: all 0.3s ease;
            width: 100%;
            max-width: 220px;
            box-shadow: 0 8px 20px rgba(102, 126, 234, 0.3);
            position: relative;
            overflow: hidden;
        }
        
        .verify-button::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
            transition: left 0.5s;
        }
        
        .verify-button:hover:not(:disabled) {
            transform: translateY(-3px);
            box-shadow: 0 12px 25px rgba(102, 126, 234, 0.4);
        }
        
        .verify-button:hover::before {
            left: 100%;
        }
        
        .verify-button:disabled {
            background: #cbd5e0;
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
        }
        
        .message {
            margin-top: 20px;
            padding: 15px;
            border-radius: 15px;
            font-weight: 600;
            display: none;
            animation: fadeIn 0.3s ease;
        }
        
        .success-message {
            background: linear-gradient(135deg, #48bb78, #38a169);
            color: white;
            box-shadow: 0 5px 15px rgba(72, 187, 120, 0.3);
        }
        
        .error-message {
            background: linear-gradient(135deg, #f56565, #e53e3e);
            color: white;
            box-shadow: 0 5px 15px rgba(245, 101, 101, 0.3);
        }
        
        @keyframes slideInUp {
            from { 
                transform: translateY(50px); 
                opacity: 0; 
            }
            to { 
                transform: translateY(0); 
                opacity: 1; 
            }
        }
        
        @keyframes bounce {
            0%, 20%, 50%, 80%, 100% { transform: translateY(0); }
            40% { transform: translateY(-10px); }
            60% { transform: translateY(-5px); }
        }
        
        @keyframes pulse {
            0% { transform: scale(1); }
            50% { transform: scale(1.1); }
            100% { transform: scale(1); }
        }
        
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        
        .loading-dots {
            display: inline-block;
        }
        
        .loading-dots::after {
            content: '';
            animation: dots 1.5s steps(5, end) infinite;
        }
        
        @keyframes dots {
            0%, 20% { content: '.'; }
            40% { content: '..'; }
            60% { content: '...'; }
            80%, 100% { content: ''; }
        }
        
        @media (max-width: 480px) {
            .captcha-container {
                padding: 25px 20px;
            }
            
            .captcha-title {
                font-size: 1.6rem;
            }
            
            .target-emoji {
                font-size: 3rem;
            }
            
            .puzzle-piece {
                font-size: 1.8rem;
                padding: 15px;
            }
        }
    </style>
</head>
<body>
    <div class="captcha-container">
        <div class="captcha-header">
            <div class="captcha-icon">🛡️</div>
            <h1 class="captcha-title">Проверка безопасности</h1>
            <p class="captcha-text">Подтвердите, что вы не робот</p>
            <div class="category-badge">Категория: {{ category_name }}</div>
        </div>
        
        <div class="target-section">
            <div class="target-emoji">{{ target_emoji }}</div>
            <div class="target-name">{{ target_name }}</div>
        </div>
        
        <div class="puzzle-section">
            <div class="puzzle-title">Выберите соответствующий элемент:</div>
            <div class="puzzle-grid">
                {% for item in puzzle_items %}
                <div class="puzzle-piece" data-position="{{ loop.index0 }}" data-emoji="{{ item }}">
                    {{ item }}
                </div>
                {% endfor %}
            </div>
            
            <button class="verify-button" id="verifyButton" disabled>
                <span id="buttonText">Проверить</span>
            </button>
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
        const buttonText = document.getElementById('buttonText');
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
            buttonText.innerHTML = 'Проверка<span class="loading-dots"></span>';
            
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
                    verifyButton.style.background = 'linear-gradient(135deg, #48bb78, #38a169)';
                    buttonText.textContent = 'Успешно!';
                    
                    setTimeout(() => {
                        window.location.href = '/';
                    }, 1500);
                } else {
                    errorMessage.textContent = data.error || '❌ Неверный выбор. Попробуйте снова.';
                    errorMessage.style.display = 'block';
                    successMessage.style.display = 'none';
                    verifyButton.disabled = false;
                    buttonText.textContent = 'Проверить';
                    
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
                buttonText.textContent = 'Проверить';
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

# Основной HTML контент с улучшенным дизайном
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
    <link rel="preload" as="style" href="https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;500;600;700;800&display=swap">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;500;600;700;800&display=swap">
    
    <style>
        :root {
            --primary-gradient: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            --secondary-gradient: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            --accent-gradient: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            --success-gradient: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);
            --dark-gradient: linear-gradient(135deg, #2c3e50 0%, #3498db 100%);
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Montserrat', sans-serif;
        }
        
        body {
            background: var(--dark-gradient);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
            color: white;
            overflow-x: hidden;
            position: relative;
        }
        
        .particles {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: -1;
        }
        
        .particle {
            position: absolute;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 50%;
            animation: float 15s infinite linear;
        }
        
        .container {
            width: 100%;
            max-width: 1000px;
            background: rgba(255, 255, 255, 0.08);
            backdrop-filter: blur(20px);
            border-radius: 30px;
            overflow: hidden;
            box-shadow: 
                0 25px 50px rgba(0, 0, 0, 0.25),
                inset 0 1px 0 rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.1);
            animation: containerEntrance 1s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative;
        }
        
        .container::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 1px;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.4), transparent);
        }
        
        .header {
            text-align: center;
            padding: 50px 40px 40px;
            background: rgba(0, 0, 0, 0.2);
            position: relative;
            overflow: hidden;
        }
        
        .header::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: var(--primary-gradient);
            opacity: 0.1;
            z-index: -1;
        }
        
        .logo {
            font-size: 5rem;
            margin-bottom: 20px;
            animation: logoGlow 3s ease-in-out infinite alternate;
            display: inline-block;
            background: linear-gradient(135deg, #ffd89b, #19547b);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            filter: drop-shadow(0 0 20px rgba(255, 216, 155, 0.3));
        }
        
        h1 {
            font-size: 3.2rem;
            background: linear-gradient(135deg, #ffecd2, #fcb69f);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 15px;
            font-weight: 800;
            letter-spacing: 1px;
            text-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
        }
        
        .subtitle {
            font-size: 1.2rem;
            opacity: 0.9;
            font-weight: 300;
            letter-spacing: 0.5px;
        }
        
        .tabs {
            display: flex;
            background: rgba(0, 0, 0, 0.3);
            backdrop-filter: blur(10px);
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .tab {
            flex: 1;
            text-align: center;
            padding: 25px 20px;
            cursor: pointer;
            transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
            border-bottom: 3px solid transparent;
            position: relative;
            overflow: hidden;
            font-weight: 600;
            letter-spacing: 0.5px;
        }
        
        .tab::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.1), transparent);
            transition: left 0.6s;
        }
        
        .tab:hover::before {
            left: 100%;
        }
        
        .tab.active {
            background: rgba(102, 126, 234, 0.2);
            border-bottom-color: #667eea;
        }
        
        .tab:hover {
            background: rgba(102, 126, 234, 0.15);
            transform: translateY(-2px);
        }
        
        .tab i {
            margin-right: 10px;
            font-size: 1.1em;
        }
        
        .content {
            padding: 40px;
            min-height: 500px;
        }
        
        .tab-content {
            display: none;
            animation: contentSlide 0.5s cubic-bezier(0.4, 0, 0.2, 1);
        }
        
        .tab-content.active {
            display: block;
        }
        
        .link-list {
            list-style: none;
            display: grid;
            gap: 20px;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
        }
        
        .link-item {
            background: rgba(255, 255, 255, 0.05);
            padding: 25px;
            border-radius: 20px;
            transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
            display: flex;
            align-items: center;
            cursor: pointer;
            border: 1px solid rgba(255, 255, 255, 0.1);
            position: relative;
            overflow: hidden;
        }
        
        .link-item::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 1px;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent);
        }
        
        .link-item:hover {
            background: rgba(255, 255, 255, 0.1);
            transform: translateY(-8px) scale(1.02);
            box-shadow: 
                0 15px 30px rgba(0, 0, 0, 0.3),
                0 0 0 1px rgba(255, 255, 255, 0.1);
        }
        
        .link-item i {
            font-size: 2rem;
            margin-right: 20px;
            width: 60px;
            height: 60px;
            display: flex;
            align-items: center;
            justify-content: center;
            background: var(--accent-gradient);
            border-radius: 15px;
            transition: all 0.3s ease;
        }
        
        .link-item:hover i {
            transform: scale(1.1) rotate(5deg);
            box-shadow: 0 5px 15px rgba(79, 172, 254, 0.4);
        }
        
        .link-item .title {
            font-size: 1.3rem;
            font-weight: 600;
            background: linear-gradient(135deg, #fff, #a8edea);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .soon-banner {
            display: flex;
            justify-content: center;
            align-items: center;
            height: 300px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 25px;
            border: 2px dashed rgba(255, 255, 255, 0.2);
            position: relative;
            overflow: hidden;
        }
        
        .soon-banner::before {
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: linear-gradient(
                45deg, 
                transparent 0%, 
                transparent 46%, 
                rgba(255, 255, 255, 0.05) 49%, 
                rgba(255, 255, 255, 0.05) 51%, 
                transparent 53%, 
                transparent 100%
            );
            animation: shine 4s infinite linear;
        }
        
        .soon-text {
            font-size: 4rem;
            font-weight: 800;
            background: linear-gradient(135deg, #ff6b6b, #ffd93d, #6bcf7f, #4d96ff);
            background-size: 400% 400%;
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            animation: gradientShift 4s ease infinite, textGlow 2s ease-in-out infinite alternate;
        }
        
        .footer {
            text-align: center;
            padding: 30px;
            background: rgba(0, 0, 0, 0.3);
            font-size: 0.9rem;
            color: rgba(255, 255, 255, 0.7);
            position: relative;
        }
        
        .footer::before {
            content: '';
            position: absolute;
            top: 0;
            left: 50%;
            transform: translateX(-50%);
            width: 80%;
            height: 1px;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent);
        }
        
        @keyframes containerEntrance {
            from {
                opacity: 0;
                transform: translateY(50px) scale(0.9);
            }
            to {
                opacity: 1;
                transform: translateY(0) scale(1);
            }
        }
        
        @keyframes contentSlide {
            from {
                opacity: 0;
                transform: translateY(20px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        @keyframes float {
            0%, 100% { 
                transform: translateY(0) translateX(0) rotate(0deg); 
            }
            33% { 
                transform: translateY(-20px) translateX(10px) rotate(120deg); 
            }
            66% { 
                transform: translateY(10px) translateX(-10px) rotate(240deg); 
            }
        }
        
        @keyframes logoGlow {
            0% {
                filter: drop-shadow(0 0 10px rgba(255, 216, 155, 0.3));
            }
            100% {
                filter: drop-shadow(0 0 30px rgba(255, 216, 155, 0.6));
            }
        }
        
        @keyframes gradientShift {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }
        
        @keyframes textGlow {
            0% { text-shadow: 0 0 10px rgba(255, 255, 255, 0.3); }
            100% { text-shadow: 0 0 20px rgba(255, 255, 255, 0.6); }
        }
        
        @keyframes shine {
            0% { transform: translate(-25%, -25%) rotate(0deg); }
            100% { transform: translate(-25%, -25%) rotate(360deg); }
        }
        
        @media (max-width: 768px) {
            .header { padding: 40px 25px; }
            h1 { font-size: 2.4rem; }
            .logo { font-size: 4rem; }
            .content { padding: 30px 20px; }
            .tab { padding: 20px 15px; }
            .soon-text { font-size: 2.5rem; }
            .link-list { grid-template-columns: 1fr; }
        }
        
        @media (max-width: 480px) {
            .header { padding: 30px 20px; }
            h1 { font-size: 2rem; }
            .logo { font-size: 3rem; }
            .tab { padding: 15px 10px; font-size: 0.9rem; }
            .soon-text { font-size: 2rem; }
        }
    </style>
</head>
<body>
    <div class="particles" id="particles"></div>
    
    <div class="container">
        <div class="header">
            <div class="logo">✨</div>
            <h1>EveryDay the best</h1>
            <p class="subtitle">EveryDay bio | Заместитель создателя канала PrankVZ</p>
        </div>
        
        <div class="tabs">
            <div class="tab active" data-tab="general">
                <i class="fas fa-home"></i> General
            </div>
            <div class="tab" data-tab="nft">
                <i class="fas fa-gem"></i> NFT
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
                        <i class="fab fa-telegram-plane"></i>
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
                    <div class="soon-text">Coming Soon...</div>
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
                        <div class="title">Generate Pass & User 🔑</div>
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
            <p>by @mobile_everyday | Сделано с ❤️</p>
        </div>
    </div>
    
    <script>
        // Создание частиц
        function createParticles() {
            const particlesContainer = document.getElementById('particles');
            const particleCount = 15;
            
            for (let i = 0; i < particleCount; i++) {
                const particle = document.createElement('div');
                particle.className = 'particle';
                
                const size = Math.random() * 60 + 20;
                const posX = Math.random() * 100;
                const posY = Math.random() * 100;
                const delay = Math.random() * 20;
                const duration = 15 + Math.random() * 10;
                
                particle.style.width = `${size}px`;
                particle.style.height = `${size}px`;
                particle.style.left = `${posX}%`;
                particle.style.top = `${posY}%`;
                particle.style.animationDelay = `${delay}s`;
                particle.style.animationDuration = `${duration}s`;
                
                particlesContainer.appendChild(particle);
            }
        }
        
        document.addEventListener('DOMContentLoaded', function() {
            createParticles();
            
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
                        // Анимация клика
                        this.style.transform = 'scale(0.95)';
                        setTimeout(() => {
                            this.style.transform = '';
                            window.open(url, '_blank');
                        }, 150);
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
