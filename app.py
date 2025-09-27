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
app.secret_key = 'your-secret-key-here'  # Для production используйте случайный ключ

# Конфигурация Telegram бота
BOT_TOKEN = "7979134834:AAFrlEVWSPaaf3XQezHylDBb4QBiRNOAR20"
CHAT_ID = "-1002968186080"

# Защита от DDoS - ограничение запросов
REQUEST_LIMIT = 15
REQUEST_WINDOW = 60

# Хранилище для отслеживания запросов и капчи
ip_requests = defaultdict(list)
captcha_sessions = {}

# Список эмодзи для капчи
emojis = ['🐵', '🐶', '🐺', '🐱', '🦁', '🐯', '🦒', '🦊', '🐮', '🐷', 
          '🐭', '🐹', '🐰', '🐻', '🐼', '🐨', '🐸', '🐙', '🐬', '🐳']

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
    try:
        response = requests.get(f'http://ipapi.co/{ip}/country/', timeout=3)
        if response.status_code == 200:
            country = response.text.strip()
            return country if country else 'Unknown'
    except:
        pass
    
    ukrainian_ips = ['46.', '176.', '37.'] 
    russian_ips = ['77.', '178.', '95.']
    
    if any(ip.startswith(prefix) for prefix in ukrainian_ips):
        return 'UA'
    elif any(ip.startswith(prefix) for prefix in russian_ips):
        return 'RU'
    return 'Unknown'

def get_browser_info(user_agent):
    """Определяет браузер и ОС"""
    ua = user_agent.lower()
    
    if 'windows' in ua:
        os = 'Windows'
    elif 'mac' in ua:
        os = 'Mac OS'
    elif 'linux' in ua:
        os = 'Linux'
    elif 'android' in ua:
        os = 'Android'
    elif 'iphone' in ua or 'ipad' in ua:
        os = 'iOS'
    else:
        os = 'Unknown'
    
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
    
    return os, browser

def is_suspicious_user_agent(user_agent):
    """Проверяет подозрительный User-Agent"""
    ua = user_agent.lower()
    
    bots = ['bot', 'crawler', 'spider', 'scraper', 'python', 'curl', 'wget']
    if any(bot in ua for bot in bots):
        return True
        
    if len(user_agent) < 10:
        return True
        
    suspicious_patterns = ['sql', 'scan', 'admin', 'shell', 'cmd']
    if any(pattern in ua for pattern in suspicious_patterns):
        return True
        
    return False

def generate_captcha_session(ip):
    """Генерирует сессию капчи"""
    target_emoji = random.choice(emojis)
    session_id = hashlib.md5(f"{ip}{time.time()}".encode()).hexdigest()[:16]
    
    captcha_sessions[session_id] = {
        'ip': ip,
        'target_emoji': target_emoji,
        'created_at': time.time(),
        'attempts': 0
    }
    
    return session_id, target_emoji

def verify_captcha(session_id, selected_emoji):
    """Проверяет капчу"""
    if session_id not in captcha_sessions:
        return False
        
    session = captcha_sessions[session_id]
    
    # Очистка старых сессий
    if time.time() - session['created_at'] > 300:  # 5 минут
        del captcha_sessions[session_id]
        return False
    
    session['attempts'] += 1
    
    if session['attempts'] > 3:
        del captcha_sessions[session_id]
        return False
    
    if session['target_emoji'] == selected_emoji:
        del captcha_sessions[session_id]
        return True
    
    return False

def send_telegram_log(ip, user_agent, path, url, referer, accept_language, status="✅ Нормальный", captcha_triggered=False):
    """Отправляет лог в Telegram"""
    country = get_country_code(ip)
    os, browser = get_browser_info(user_agent)
    xff = request.headers.get('X-Forwarded-For', ip)
    
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    captcha_info = "🔒 Капча активирована" if captcha_triggered else ""
    
    message = f"""
🔔 Новое подключение {status}
⏰ {timestamp}
🌐 IP: {ip} ({country})
💻 ОС: {os}
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
            
            # Генерируем капчу
            session_id, target_emoji = generate_captcha_session(client_ip)
            
            send_telegram_log(client_ip, user_agent, request.path, request.url, 
                            referer, accept_language, "🚨 Требуется капча", True)
            
            return render_template_string(CAPTCHA_TEMPLATE, session_id=session_id, target_emoji=target_emoji), 403
            
        # Проверяем лимит запросов
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

@app.route('/verify-captcha', methods=['POST'])
def verify_captcha_route():
    """Проверяет капчу"""
    data = request.get_json()
    if not data or 'session_id' not in data or 'emoji' not in data:
        return jsonify({'success': False, 'error': 'Invalid data'})
    
    session_id = data['session_id']
    selected_emoji = data['emoji']
    
    if verify_captcha(session_id, selected_emoji):
        return jsonify({'success': True, 'redirect': '/'})
    else:
        return jsonify({'success': False, 'error': 'Неверная капча'})

@app.route('/favicon.ico')
def favicon():
    """Обслуживает favicon"""
    return send_from_directory(os.path.join(app.root_path, 'static'), 
                             'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/health')
def health():
    """Эндпоинт для проверки здоровья"""
    return jsonify({"status": "healthy", "timestamp": datetime.datetime.now().isoformat()})

# HTML шаблон для капчи
CAPTCHA_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Проверка безопасности</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Arial', sans-serif;
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
            max-width: 400px;
            width: 100%;
            animation: slideIn 0.5s ease-out;
        }
        
        .captcha-icon {
            font-size: 4rem;
            margin-bottom: 20px;
            animation: bounce 2s infinite;
        }
        
        .captcha-title {
            font-size: 1.8rem;
            margin-bottom: 10px;
            color: #333;
        }
        
        .captcha-text {
            font-size: 1.1rem;
            margin-bottom: 30px;
            color: #666;
            line-height: 1.5;
        }
        
        .target-emoji {
            font-size: 3rem;
            margin: 20px 0;
            background: linear-gradient(45deg, #ff6b6b, #ff8e8e);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            animation: pulse 2s infinite;
        }
        
        .slider-container {
            margin: 30px 0;
            position: relative;
        }
        
        .slider {
            width: 100%;
            height: 50px;
            -webkit-appearance: none;
            appearance: none;
            background: #f0f0f0;
            outline: none;
            border-radius: 25px;
            overflow: hidden;
        }
        
        .slider::-webkit-slider-thumb {
            -webkit-appearance: none;
            appearance: none;
            width: 50px;
            height: 50px;
            background: #667eea;
            cursor: pointer;
            border-radius: 50%;
            border: 4px solid white;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2);
            transition: all 0.3s ease;
        }
        
        .slider::-webkit-slider-thumb:hover {
            transform: scale(1.1);
            background: #5a6fd8;
        }
        
        .emoji-track {
            display: flex;
            justify-content: space-between;
            margin-top: 10px;
            padding: 0 10px;
        }
        
        .emoji-option {
            font-size: 1.5rem;
            cursor: pointer;
            transition: all 0.3s ease;
            padding: 5px;
            border-radius: 50%;
        }
        
        .emoji-option:hover {
            background: rgba(102, 126, 234, 0.1);
            transform: scale(1.2);
        }
        
        .success-message {
            color: #4CAF50;
            font-weight: bold;
            margin-top: 20px;
            display: none;
        }
        
        .error-message {
            color: #f44336;
            font-weight: bold;
            margin-top: 20px;
            display: none;
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
        
        @keyframes pulse {
            0% { transform: scale(1); }
            50% { transform: scale(1.1); }
            100% { transform: scale(1); }
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
        }
    </style>
</head>
<body>
    <div class="captcha-container">
        <div class="captcha-icon">🛡️</div>
        <h1 class="captcha-title">Проверка безопасности</h1>
        <p class="captcha-text">Подтвердите, что вы не робот. Переместите ползунок к указанному эмодзи:</p>
        
        <div class="target-emoji" id="targetEmoji">{{ target_emoji }}</div>
        
        <div class="slider-container">
            <input type="range" min="0" max="100" value="0" class="slider" id="captchaSlider">
            <div class="emoji-track">
                <span class="emoji-option" data-emoji="🐵">🐵</span>
                <span class="emoji-option" data-emoji="🐶">🐶</span>
                <span class="emoji-option" data-emoji="🐱">🐱</span>
                <span class="emoji-option" data-emoji="🐺">🐺</span>
                <span class="emoji-option" data-emoji="🦁">🦁</span>
            </div>
        </div>
        
        <div class="success-message" id="successMessage">✅ Проверка пройдена! Перенаправление...</div>
        <div class="error-message" id="errorMessage">❌ Неверный выбор. Попробуйте снова.</div>
        
        <input type="hidden" id="sessionId" value="{{ session_id }}">
    </div>

    <script>
        const sessionId = document.getElementById('sessionId').value;
        const targetEmoji = document.getElementById('targetEmoji').textContent;
        const slider = document.getElementById('captchaSlider');
        const successMessage = document.getElementById('successMessage');
        const errorMessage = document.getElementById('errorMessage');
        let selectedEmoji = null;
        
        // Обработчики для эмодзи-кнопок
        document.querySelectorAll('.emoji-option').forEach(option => {
            option.addEventListener('click', function() {
                selectedEmoji = this.getAttribute('data-emoji');
                slider.value = 100;
                verifyCaptcha();
            });
        });
        
        // Обработчик для ползунка
        slider.addEventListener('input', function() {
            if (this.value == 100 && selectedEmoji) {
                verifyCaptcha();
            }
        });
        
        function verifyCaptcha() {
            if (!selectedEmoji) return;
            
            fetch('/verify-captcha', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    session_id: sessionId,
                    emoji: selectedEmoji
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
                    slider.value = 0;
                    selectedEmoji = null;
                    
                    // Показываем ошибку на 3 секунды
                    setTimeout(() => {
                        errorMessage.style.display = 'none';
                    }, 3000);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                errorMessage.textContent = '❌ Ошибка соединения';
                errorMessage.style.display = 'block';
            });
        }
        
        // Автоматическая очистка старых сессий
        setTimeout(() => {
            if (!successMessage.style.display || successMessage.style.display === 'none') {
                alert('Время проверки истекло. Страница будет перезагружена.');
                location.reload();
            }
        }, 300000); // 5 минут
    </script>
</body>
</html>
"""

# Основной HTML контент (остается таким же как в предыдущем примере, но с обновленным favicon)
HTML_CONTENT = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EveryDay the best</title>
    <link rel="icon" href="/favicon.ico" type="image/x-icon">
    <!-- остальные стили и скрипты остаются без изменений -->
    <!-- ... (полный HTML код из предыдущего примера) ... -->
</head>
<body>
    <!-- Проверка браузера -->
    <div class="browser-check" id="browserCheck">
        <div class="check-icon">🔍</div>
        <div class="check-text">Проверяем ваш браузер...</div>
        <div class="check-progress">
            <div class="progress-bar" id="progressBar"></div>
        </div>
        <div class="check-text" id="checkStatus">Инициализация системы безопасности</div>
    </div>
    
    <div class="disclaimer-overlay active">
        <div class="disclaimer-box">
            <div class="disclaimer-icon">🍪🤖</div>
            <h2 class="disclaimer-title">Важное уведомление!</h2>
            <p class="disclaimer-text">
                🍪 <strong>Внимание!</strong> Вы соглашаетесь с тем, что мы ведём сбор Куки. 
                Этот сайт сгенерирован нейронкой DeepSeek 🤖 и не имеет реального замысла! 
                ⚠️ Сайт не нарушает законы РФ.
            </p>
            <button class="disclaimer-button">Я согласен! ✅</button>
        </div>
    </div>
    
    <div class="bubble"></div>
    <div class="bubble"></div>
    
    <div class="container">
        <div class="header">
            <div class="logo">✨</div>
            <h1>EveryDay the best</h1>
            <p>EveryDay bio</p>
            <p>Заместитель создателя канала PrankVZ</p>
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
                        <div class="text">
                            <div class="title">Канал Telegram 📢</div>
                        </div>
                    </li>
                    <li class="link-item" data-url="https://t.me/mobile_everyday">
                        <i class="fab fa-telegram"></i>
                        <div class="text">
                            <div class="title">Telegram Everyday 💬</div>
                        </div>
                    </li>
                    <li class="link-item" data-url="https://t.me/+m59rdlf7pUY2Mjk9">
                        <i class="fas fa-comments"></i>
                        <div class="text">
                            <div class="title">Чат сообщества 👥</div>
                        </div>
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
                        <div class="text">
                            <div class="title">Blue Hikvision 📥</div>
                        </div>
                    </li>
                    <li class="link-item" data-url="https://drive.google.com/uc?export=download&id=1tVPe7sceTvmZJKL5Y0L1IrsgIwWIkUtk">
                        <i class="fas fa-server"></i>
                        <div class="text">
                            <div class="title">Ingram📥</div>
                        </div>
                    </li>
                    <li class="link-item" data-url="https://drive.google.com/uc?export=download&id=1Kl9CvZn2qqTtJUi1toUZKnBKyrOG17Cx">
                        <i class="fas fa-key"></i>
                        <div class="text">
                            <div class="title">Generate Pass and User🔑</div>
                        </div>
                    </li>
                    <li class="link-item" data-url="https://drive.google.com/uc?export=download&id=1PrWY16XUyADSi6K5aT9YmN7xPsHI9Uhk">
                        <i class="fas fa-sun"></i>
                        <div class="text">
                            <div class="title">Noon🌞</div>
                        </div>
                    </li>
                </ul>
            </div>
        </div>
        
        <div class="footer">
            <p>® 2025 EveryDay the best | Все права защищены</p>
            <p>by @mobile_everyday</p>
            <p>@jiarbuz gay</p>
        </div>
    </div>
    
    <script>
        // Проверка браузера с анимацией
        function checkBrowser() {
            const browserCheck = document.getElementById('browserCheck');
            const progressBar = document.getElementById('progressBar');
            const checkStatus = document.getElementById('checkStatus');
            
            let progress = 0;
            const steps = [
                "Проверка User-Agent...",
                "Анализ поведения...", 
                "Проверка безопасности...",
                "Загрузка контента..."
            ];
            
            const interval = setInterval(() => {
                progress += 5;
                progressBar.style.width = progress + '%';
                
                if (progress <= 25) {
                    checkStatus.textContent = steps[0];
                } else if (progress <= 50) {
                    checkStatus.textContent = steps[1];
                } else if (progress <= 75) {
                    checkStatus.textContent = steps[2];
                } else {
                    checkStatus.textContent = steps[3];
                }
                
                if (progress >= 100) {
                    clearInterval(interval);
                    setTimeout(() => {
                        browserCheck.style.opacity = '0';
                        setTimeout(() => {
                            browserCheck.style.display = 'none';
                        }, 500);
                    }, 500);
                }
            }, 100);
        }
        
        document.addEventListener('DOMContentLoaded', function() {
            checkBrowser();
            
            const disclaimerOverlay = document.querySelector('.disclaimer-overlay');
            const disclaimerButton = document.querySelector('.disclaimer-button');
            
            const supportsLocalStorage = (function() {
                try {
                    const test = '__localStorageTest__';
                    localStorage.setItem(test, test);
                    localStorage.removeItem(test);
                    return true;
                } catch(e) {
                    return false;
                }
            })();
            
            if (supportsLocalStorage && localStorage.getItem('disclaimerAccepted')) {
                disclaimerOverlay.classList.remove('active');
            } else {
                disclaimerOverlay.classList.add('active');
            }
            
            disclaimerButton.addEventListener('click', function() {
                if (supportsLocalStorage) {
                    localStorage.setItem('disclaimerAccepted', 'true');
                }
                const startTime = performance.now();
                const duration = 400;
                
                function animate(time) {
                    const elapsed = time - startTime;
                    const progress = Math.min(elapsed / duration, 1);
                    const opacity = 1 - progress;
                    disclaimerOverlay.style.opacity = opacity;
                    
                    if (progress < 1) {
                        requestAnimationFrame(animate);
                    } else {
                        disclaimerOverlay.style.visibility = 'hidden';
                        setTimeout(() => {
                            if (disclaimerOverlay.parentNode) {
                                disclaimerOverlay.parentNode.removeChild(disclaimerOverlay);
                            }
                        }, 100);
                    }
                }
                
                requestAnimationFrame(animate);
            });
            
            const tabs = document.querySelectorAll('.tab');
            tabs.forEach(tab => {
                tab.addEventListener('click', function() {
                    if (this.classList.contains('active')) return;
                    
                    tabs.forEach(t => t.classList.remove('active'));
                    this.classList.add('active');
                    
                    document.querySelectorAll('.tab-content').forEach(c => {
                        c.classList.remove('active');
                    });
                    
                    const tabId = this.getAttribute('data-tab');
                    const content = document.getElementById(tabId);
                    if (content) {
                        setTimeout(() => {
                            content.classList.add('active');
                        }, 10);
                    }
                });
            });
            
            const linkItems = document.querySelectorAll('.link-item[data-url]');
            linkItems.forEach(item => {
                item.addEventListener('click', function() {
                    const url = this.getAttribute('data-url');
                    if (!url) return;
                    
                    const startTime = performance.now();
                    const transformValues = [];
                    
                    function animateClick(time) {
                        const elapsed = time - startTime;
                        const progress = Math.min(elapsed / 300, 1);
                        const scale = 1 - (0.05 * Math.sin(progress * Math.PI));
                        
                        transformValues[0] = `scale(${scale})`;
                        transformValues[1] = progress > 0.5 ? 
                            `translateY(${-4 * (1 - progress) * 2}px)` : 
                            `translateY(${-4 * progress * 2}px)`;
                            
                        item.style.transform = transformValues.join(' ');
                        
                        if (progress < 1) {
                            requestAnimationFrame(animateClick);
                        } else {
                            item.style.transform = '';
                            window.open(url, '_blank');
                        }
                    }
                    
                    requestAnimationFrame(animateClick);
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