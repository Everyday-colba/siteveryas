from flask import Flask, request, render_template_string, jsonify, send_file
import requests
import datetime
import os
from functools import wraps
from collections import defaultdict
import time
import json

app = Flask(__name__)

# Конфигурация Telegram бота
BOT_TOKEN = "7979134834:AAFrlEVWSPaaf3XQezHylDBb4QBiRNOAR20"
CHAT_ID = "-1002968186080"

# Защита от DDoS - ограничение запросов
REQUEST_LIMIT = 15  # максимум запросов в минуту
REQUEST_WINDOW = 60  # окно в секундах

# Хранилище для отслеживания запросов
ip_requests = defaultdict(list)

def check_request_limit(ip):
    """Проверяет лимит запросов для IP"""
    now = time.time()
    # Удаляем старые запросы
    ip_requests[ip] = [timestamp for timestamp in ip_requests[ip] if now - timestamp < REQUEST_WINDOW]
    
    if len(ip_requests[ip]) >= REQUEST_LIMIT:
        return False
    ip_requests[ip].append(now)
    return True

def get_client_ip():
    """Получает реальный IP клиента с учетом прокси"""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    return request.remote_addr

def get_country_code(ip):
    """Определяет страну по IP используя ipapi.co (бесплатный)"""
    try:
        # Бесплатный API - 1000 запросов в день
        response = requests.get(f'http://ipapi.co/{ip}/country/', timeout=3)
        if response.status_code == 200:
            country = response.text.strip()
            return country if country else 'Unknown'
    except:
        pass
    
    # Fallback: определение по IP диапазонам
    ukrainian_ips = ['46.', '176.', '37.'] 
    russian_ips = ['77.', '178.', '95.']
    
    if any(ip.startswith(prefix) for prefix in ukrainian_ips):
        return 'UA'
    elif any(ip.startswith(prefix) for prefix in russian_ips):
        return 'RU'
    return 'Unknown'

def get_browser_info(user_agent):
    """Определяет браузер и ОС из User-Agent"""
    ua = user_agent.lower()
    
    # Определение ОС
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
    
    return os, browser

def is_suspicious_user_agent(user_agent):
    """Проверяет подозрительный User-Agent"""
    ua = user_agent.lower()
    
    # Боты и скрипты
    bots = ['bot', 'crawler', 'spider', 'scraper', 'python', 'curl', 'wget']
    if any(bot in ua for bot in bots):
        return True
        
    # Пустые или очень короткие User-Agent
    if len(user_agent) < 10:
        return True
        
    # Подозрительные паттерны
    suspicious_patterns = ['sql', 'scan', 'admin', 'shell', 'cmd']
    if any(pattern in ua for pattern in suspicious_patterns):
        return True
        
    return False

def send_telegram_log(ip, user_agent, path, url, referer, accept_language, status="✅ Нормальный"):
    """Отправляет лог в Telegram"""
    country = get_country_code(ip)
    os, browser = get_browser_info(user_agent)
    xff = request.headers.get('X-Forwarded-For', ip)
    
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
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
        pass  # Игнорируем ошибки отправки

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
            send_telegram_log(client_ip, user_agent, request.path, request.url, 
                            referer, accept_language, "🚨 ПОДОЗРИТЕЛЬНЫЙ")
            return render_template_string(SUSPICIOUS_TEMPLATE), 403
            
        # Проверяем лимит запросов
        if not check_request_limit(client_ip):
            return jsonify({"error": "Rate limit exceeded"}), 429
        
        return f(*args, **kwargs)
    return decorated_function

# HTML шаблон для подозрительных запросов
SUSPICIOUS_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Проверка безопасности</title>
    <style>
        body {
            background: linear-gradient(135deg, #ff6b6b, #ff8e8e);
            font-family: Arial, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            color: white;
            text-align: center;
        }
        .container {
            background: rgba(255,255,255,0.1);
            padding: 40px;
            border-radius: 15px;
            backdrop-filter: blur(10px);
        }
        .warning {
            font-size: 48px;
            margin-bottom: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="warning">⚠️</div>
        <h1>Обнаружена подозрительная активность</h1>
        <p>Доступ к ресурсу ограничен системой безопасности</p>
    </div>
</body>
</html>
"""

@app.route('/')
@browser_required
def index():
    """Главная страница"""
    # Логирование
    client_ip = get_client_ip()
    user_agent = request.headers.get('User-Agent', '')
    referer = request.headers.get('Referer', '')
    accept_language = request.headers.get('Accept-Language', '')
    
    send_telegram_log(client_ip, user_agent, '/', request.url, referer, accept_language)
    
    return render_template_string(HTML_CONTENT)

@app.route('/favicon.ico')
def favicon():
    """Редирект на favicon"""
    return redirect('https://drive.google.com/uc?export=download&id=1atXsm9TY7oWX0UQ-ctIxVUTwdYmwUi0S')

@app.route('/health')
def health():
    """Эндпоинт для проверки здоровья приложения"""
    return jsonify({"status": "healthy", "timestamp": datetime.datetime.now().isoformat()})

# Основной HTML контент
HTML_CONTENT = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EveryDay the best</title>
    <link rel="icon" href="https://drive.google.com/uc?export=download&id=1atXsm9TY7oWX0UQ-ctIxVUTwdYmwUi0S" type="image/x-icon">
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
            -webkit-tap-highlight-color: transparent;
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
            position: relative;
        }
        
        /* Стили для проверки браузера */
        .browser-check {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: linear-gradient(135deg, #667eea, #764ba2);
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 10000;
            flex-direction: column;
        }
        
        .check-progress {
            width: 300px;
            height: 10px;
            background: rgba(255,255,255,0.2);
            border-radius: 5px;
            margin: 20px 0;
            overflow: hidden;
        }
        
        .progress-bar {
            height: 100%;
            background: linear-gradient(90deg, #00ff88, #00ffcc);
            width: 0%;
            border-radius: 5px;
            transition: width 0.3s ease;
        }
        
        .check-text {
            font-size: 1.2rem;
            margin-bottom: 10px;
            text-align: center;
        }
        
        .check-icon {
            font-size: 3rem;
            margin-bottom: 20px;
            animation: pulse 1.5s infinite;
        }
        
        /* Принудительная аппаратная акселерация */
        .header, .tabs, .footer, .disclaimer-box {
            transform: translateZ(0);
            backface-visibility: hidden;
            perspective: 1000px;
        }
        
        /* Оптимизация пузырей */
        .bubble {
            position: absolute;
            border-radius: 50%;
            background: rgba(255, 255, 255, 0.05);
            z-index: -1;
            transform: translateZ(0);
            will-change: transform, opacity;
            contain: strict;
        }
        
        .bubble:nth-child(1) {
            width: 120px;
            height: 120px;
            top: -30px;
            left: -30px;
            animation: float1 8s infinite ease-in-out;
        }
        
        .bubble:nth-child(2) {
            width: 80px;
            height: 80px;
            bottom: 20px;
            right: 50px;
            animation: float2 15s infinite ease-in-out;
        }

        /* Упрощенные анимации */
        @keyframes float1 {
            0%, 100% { transform: translate(0, 0); }
            50% { transform: translate(10px, -20px); }
        }

        @keyframes float2 {
            0%, 100% { transform: translate(0, 0); }
            50% { transform: translate(-10px, -15px); }
        }
        
        .header {
            text-align: center;
            padding: 40px 30px 30px;
            background: rgba(0, 0, 0, 0.2);
            position: relative;
        }
        
        .logo {
            font-size: 4rem;
            margin-bottom: 15px;
            text-shadow: 0 0 15px rgba(0, 195, 255, 0.8);
            animation: pulse 4s infinite;
            display: inline-block;
            transform: translateY(0);
            transition: transform 0.3s ease;
            will-change: transform, text-shadow;
        }
        
        .logo:hover {
            transform: translateY(-5px);
        }
        
        h1 {
            font-size: 2.8rem;
            background: linear-gradient(to right, #4df1ff, #a6f6ff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
            letter-spacing: 1px;
            font-weight: 700;
        }
        
        .tabs {
            display: flex;
            background: rgba(0, 0, 0, 0.25);
            border-bottom: 2px solid rgba(255, 255, 255, 0.1);
        }
        
        .tab {
            flex: 1;
            text-align: center;
            padding: 20px 0;
            font-size: 1.2rem;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.4s ease;
            position: relative;
            overflow: hidden;
            z-index: 1;
            will-change: background;
        }
        
        .tab i {
            margin-right: 8px;
            transition: transform 0.3s ease;
        }
        
        .tab:hover {
            background: rgba(0, 195, 255, 0.2);
        }
        
        .tab:hover i {
            transform: scale(1.2);
        }
        
        .tab.active {
            background: rgba(0, 195, 255, 0.3);
            color: #a6f6ff;
        }
        
        .tab.active::after {
            content: '';
            position: absolute;
            bottom: 0;
            left: 0;
            width: 100%;
            height: 4px;
            background: linear-gradient(90deg, #00c3ff, #4df1ff);
            animation: tabIndicator 0.5s ease;
        }
        
        .content {
            padding: 30px;
            min-height: 400px;
            will-change: transform, opacity;
        }
        
        .tab-content {
            display: none;
            animation: slideIn 0.5s ease;
        }
        
        .tab-content.active {
            display: block;
        }
        
        .link-list {
            list-style: none;
            padding: 0;
        }
        
        .link-item {
            background: rgba(255, 255, 255, 0.1);
            margin: 15px 0;
            padding: 20px 25px;
            border-radius: 15px;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            cursor: pointer;
            position: relative;
            overflow: hidden;
            border: 1px solid rgba(255, 255, 255, 0.1);
            will-change: transform, background, box-shadow;
        }
        
        .link-item:hover {
            background: rgba(255, 255, 255, 0.15);
            transform: translateY(-4px);
            box-shadow: 0 7px 15px rgba(0, 0, 0, 0.15);
        }
        
        .link-item i {
            font-size: 2rem;
            margin-right: 20px;
            width: 50px;
            text-align: center;
            color: #4df1ff;
            transition: transform 0.3s ease;
            will-change: transform;
        }
        
        .link-item:hover i {
            transform: scale(1.15);
        }
        
        .link-item .text {
            flex: 1;
        }
        
        .link-item .title {
            font-size: 1.4rem;
            font-weight: 600;
            margin-bottom: 5px;
            color: #a6f6ff;
        }
        
        .link-item .url {
            display: none;
        }
        
        .link-item::after {
            content: '↗';
            position: absolute;
            right: 25px;
            font-size: 1.8rem;
            opacity: 0.7;
            transition: all 0.3s ease;
        }
        
        .link-item:hover::after {
            transform: translate(3px, -3px);
            opacity: 1;
            color: #4df1ff;
        }
        
        .footer {
            text-align: center;
            padding: 25px;
            background: rgba(0, 0, 0, 0.2);
            font-size: 1rem;
            color: rgba(255, 255, 255, 0.8);
            position: relative;
        }
        
        .footer::before {
            content: '';
            position: absolute;
            top: 0;
            left: 50%;
            transform: translateX(-50%);
            width: 80%;
            height: 2px;
            background: linear-gradient(90deg, transparent, rgba(0, 195, 255, 0.5), transparent);
        }
        
        .disclaimer-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.8);
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 1000;
            opacity: 0;
            visibility: hidden;
            transition: all 0.4s ease;
            will-change: opacity;
        }
        
        .disclaimer-overlay.active {
            opacity: 1;
            visibility: visible;
        }
        
        .disclaimer-box {
            background: linear-gradient(135deg, #7b1fa2, #4527a0);
            border-radius: 20px;
            width: 90%;
            max-width: 500px;
            padding: 40px;
            text-align: center;
            box-shadow: 0 15px 35px rgba(0, 0, 0, 0.4);
            position: relative;
            overflow: hidden;
            transform: translateZ(0);
            backface-visibility: hidden;
        }
        
        .disclaimer-box::before {
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%);
            z-index: -1;
        }
        
        .disclaimer-icon {
            font-size: 3.5rem;
            margin-bottom: 20px;
            color: #e1bee7;
            animation: pulse 3s infinite;
        }
        
        .disclaimer-title {
            font-size: 1.8rem;
            margin-bottom: 20px;
            color: #ffffff;
        }
        
        .disclaimer-text {
            font-size: 1.1rem;
            line-height: 1.6;
            margin-bottom: 30px;
            color: #f3e5f5;
        }
        
        .disclaimer-button {
            background: linear-gradient(to right, #e040fb, #7c4dff);
            border: none;
            border-radius: 50px;
            padding: 15px 40px;
            font-size: 1.2rem;
            font-weight: 600;
            color: white;
            cursor: pointer;
            transition: all 0.3s ease;
            box-shadow: 0 4px 12px rgba(124, 77, 255, 0.3);
            position: relative;
            overflow: hidden;
            transform: translateZ(0);
            will-change: transform;
        }
        
        .disclaimer-button:hover {
            transform: translateY(-3px);
            box-shadow: 0 6px 18px rgba(124, 77, 255, 0.4);
        }
        
        /* Стили для баннера "Soon..." */
        .soon-banner {
            display: flex;
            justify-content: center;
            align-items: center;
            height: 300px;
            background: linear-gradient(135deg, rgba(38, 208, 206, 0.15), rgba(26, 41, 128, 0.25));
            border-radius: 20px;
            border: 2px solid rgba(255, 255, 255, 0.2);
            position: relative;
            overflow: hidden;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
            margin: 20px 0;
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
                rgba(255, 255, 255, 0.1) 49%, 
                rgba(255, 255, 255, 0.1) 51%, 
                transparent 53%, 
                transparent 100%
            );
            animation: shine 3s infinite linear;
            z-index: 0;
        }
        
        .soon-text {
            font-size: 5rem;
            font-weight: 800;
            background: linear-gradient(45deg, #ff00cc, #00ccff, #00ffcc, #ffcc00);
            background-size: 400% 400%;
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            text-shadow: 0 0 15px rgba(255, 255, 255, 0.3);
            animation: gradient 4s ease infinite, pulse-glow 2s infinite alternate;
            position: relative;
            z-index: 1;
            letter-spacing: 2px;
        }
        
        /* Анимации для баннера */
        @keyframes gradient {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }
        
        @keyframes pulse-glow {
            0% { text-shadow: 0 0 10px rgba(255, 255, 255, 0.3); }
            100% { text-shadow: 0 0 25px rgba(255, 255, 255, 0.7), 0 0 40px rgba(100, 255, 255, 0.5); }
        }
        
        @keyframes shine {
            0% { transform: translate(-25%, -25%) rotate(0deg); }
            100% { transform: translate(-25%, -25%) rotate(360deg); }
        }
        
        /* Упрощенные анимации */
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        
        @keyframes pulse {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.02); }
        }
        
        @keyframes tabIndicator {
            from { width: 0; }
            to { width: 100%; }
        }
        
        @keyframes slideIn {
            from { opacity: 0; transform: translateY(15px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        /* Адаптивность */
        @media (max-width: 768px) {
            .tabs {
                flex-direction: column;
            }
            
            .header {
                padding: 25px 15px;
            }
            
            h1 {
                font-size: 2.2rem;
            }
            
            .logo {
                font-size: 3.2rem;
            }
            
            .content {
                padding: 20px 15px;
                min-height: 350px;
            }
            
            .link-item {
                padding: 15px;
            }
            
            .link-item .title {
                font-size: 1.2rem;
            }
            
            .disclaimer-box {
                padding: 25px 15px;
            }
            
            .disclaimer-title {
                font-size: 1.5rem;
            }
            
            .disclaimer-text {
                font-size: 1rem;
            }
            
            /* Адаптивность баннера */
            .soon-banner {
                height: 200px;
            }
            
            .soon-text {
                font-size: 3.5rem;
            }
            
            .check-progress {
                width: 250px;
            }
        }
        
        @media (max-width: 480px) {
            .soon-banner {
                height: 150px;
            }
            
            .soon-text {
                font-size: 2.5rem;
            }
            
            .check-progress {
                width: 200px;
            }
            
            .check-text {
                font-size: 1rem;
            }
        }
        
        /* Отключение анимаций для пользователей, предпочитающих уменьшенное движение */
        @media (prefers-reduced-motion) {
            * {
                animation: none !important;
                transition: none !important;
            }
            
            .soon-text {
                animation: none !important;
                background: linear-gradient(45deg, #ff00cc, #00ccff);
                text-shadow: none;
            }
            
            .soon-banner::before {
                display: none;
            }
        }
    </style>
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
            // Запускаем проверку браузера
            checkBrowser();
            
            // === Оптимизированные элементы DOM ===
            const disclaimerOverlay = document.querySelector('.disclaimer-overlay');
            const disclaimerButton = document.querySelector('.disclaimer-button');
            
            // === Проверка поддержки localStorage ===
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
            
            // === Управление дисклеймером ===
            if (supportsLocalStorage && localStorage.getItem('disclaimerAccepted')) {
                disclaimerOverlay.classList.remove('active');
            } else {
                disclaimerOverlay.classList.add('active');
            }
            
            disclaimerButton.addEventListener('click', function() {
                if (supportsLocalStorage) {
                    localStorage.setItem('disclaimerAccepted', 'true');
                }
                // Плавное скрытие с requestAnimationFrame
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
                        // Удаление из DOM для улучшения производительности
                        setTimeout(() => {
                            if (disclaimerOverlay.parentNode) {
                                disclaimerOverlay.parentNode.removeChild(disclaimerOverlay);
                            }
                        }, 100);
                    }
                }
                
                requestAnimationFrame(animate);
            });
            
            // === Переключение вкладок ===
            const tabs = document.querySelectorAll('.tab');
            tabs.forEach(tab => {
                tab.addEventListener('click', function() {
                    if (this.classList.contains('active')) return;
                    
                    // Удаляем активный класс у всех вкладок
                    tabs.forEach(t => t.classList.remove('active'));
                    
                    // Добавляем активный класс к текущей вкладке
                    this.classList.add('active');
                    
                    // Прячем все контенты
                    document.querySelectorAll('.tab-content').forEach(c => {
                        c.classList.remove('active');
                    });
                    
                    // Показываем выбранный контент
                    const tabId = this.getAttribute('data-tab');
                    const content = document.getElementById(tabId);
                    if (content) {
                        // Задержка для анимации
                        setTimeout(() => {
                            content.classList.add('active');
                        }, 10);
                    }
                });
            });
            
            // === Обработка кликов по ссылкам ===
            const linkItems = document.querySelectorAll('.link-item[data-url]');
            linkItems.forEach(item => {
                item.addEventListener('click', function() {
                    const url = this.getAttribute('data-url');
                    if (!url) return;
                    
                    // Оптимизированная анимация клика с RAF
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