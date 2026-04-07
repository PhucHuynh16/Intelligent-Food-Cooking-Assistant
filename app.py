from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import os
import json
from google import genai
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

app = Flask(__name__)
CORS(app)

# Khởi tạo Client (Sử dụng biến môi trường là tốt nhất)
api_key = os.getenv("AIzaSyDLpb88v5EqcUxAbm4N6HB_h_MvQJ4pkmc") 
client = genai.Client(api_key="AIzaSyDLpb88v5EqcUxAbm4N6HB_h_MvQJ4pkmc")

HISTORY_FILE = "search_history.json"
CHAT_HISTORY_FILE = "chat_history.json"

@app.route('/')
def home_page():
    return render_template('index.html')

# --- Route 1: Nhận công thức món ăn ---
@app.route('/cook', methods=['POST'])
def cook():
    data = request.get_json()
    dish_name = data.get('dish', '').strip()

    if not dish_name:
        return jsonify({'error': 'Vui lòng cung cấp tên món ăn'}), 400

    try:
        prompt = f"Hướng dẫn nấu món '{dish_name}' chi tiết, bao gồm nguyên liệu với số lượng, gia vị, và từng bước thực hiện. Viết rõ ràng bằng Markdown."

        # Sử dụng đúng SDK: client.models.generate_content
        response = client.models.generate_content(
            model="gemini-2.5-flash", 
            contents=prompt
        )

        recipe_text = response.text.strip()

        # Lưu lịch sử
        save_search_history(dish_name, recipe_text)
        save_chat_history(dish_name, "user", f"Tôi muốn công thức món {dish_name}")
        save_chat_history(dish_name, "model", recipe_text) # 'model' thay cho 'assistant' trong Google SDK

        return jsonify({'dish': dish_name, 'recipe': recipe_text})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- Route 2: Trò chuyện Follow-up (Hỏi thêm về món ăn) ---
@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    dish_name = data.get('dish', '').strip()
    message = data.get('message', '').strip()

    if not dish_name or not message:
        return jsonify({'error': 'Vui lòng cung cấp tên món và tin nhắn'}), 400

    try:
        # 1. Lấy lịch sử chat cũ từ file
        stored_history = load_chat_history(dish_name)
        
        # 2. Chuyển đổi định dạng lịch sử cho phù hợp với Google SDK (role: user/model)
        formatted_history = []
        for entry in stored_history:
            # Google SDK dùng role 'user' và 'model'
            role = 'model' if entry['role'] == 'assistant' or entry['role'] == 'model' else 'user'
            formatted_history.append({"role": role, "parts": [{"text": entry['content']}]})

        # 3. Sử dụng chat session của Gemini để giữ ngữ cảnh
        chat_session = client.chats.create(
            model="gemini-2.5-flash",
            config={
                "system_instruction": "Bạn là một chuyên gia ẩm thực. Hãy trả lời ngắn gọn, tập trung vào kỹ thuật nấu ăn."
            },
            history=formatted_history
        )

        response = chat_session.send_message(message)
        answer = response.text.strip()

        # 4. Lưu lại lịch sử mới
        save_chat_history(dish_name, "user", message)
        save_chat_history(dish_name, "model", answer)

        return jsonify({'reply': answer})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- Các hàm hỗ trợ xử lý JSON (Giữ nguyên logic của bạn nhưng tối ưu hơn) ---

def save_search_history(dish, recipe):
    history = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            try: history = json.load(f)
            except: history = []
    
    # Kiểm tra xem món này đã có trong lịch sử chưa
    # Nếu có rồi thì xóa cái cũ đi để thêm cái mới lên đầu
    history = [item for item in history if item['dish'].lower() != dish.lower()]
    
    entry = {
        "dish": dish, 
        "recipe": recipe, 
        "timestamp": datetime.now().strftime("%H:%M - %d/%m/%Y")
    }
    
    history.append(entry)
    
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=4)

def save_chat_history(dish, role, content):
    chat_data = {}
    if os.path.exists(CHAT_HISTORY_FILE):
        with open(CHAT_HISTORY_FILE, 'r', encoding='utf-8') as f:
            try: chat_data = json.load(f)
            except: chat_data = {}
    
    if dish not in chat_data:
        chat_data[dish] = []
    
    # Lưu role 'user' hoặc 'model' để khớp với Gemini SDK
    chat_data[dish].append({
        "role": role, 
        "content": content, 
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    with open(CHAT_HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(chat_data, f, ensure_ascii=False, indent=4)
def load_chat_history(dish):
    if not os.path.exists(CHAT_HISTORY_FILE):
        return []
    with open(CHAT_HISTORY_FILE, 'r', encoding='utf-8') as f:
        try:
            chat_data = json.load(f)
            return chat_data.get(dish, [])
        except:
            return []
@app.route('/history', methods=['GET'])
def get_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            try:
                history = json.load(f)
                # Chỉ trả về tên món ăn và timestamp, đảo ngược để món mới nhất lên đầu
                display_history = [{"dish": item['dish'], "timestamp": item['timestamp']} for item in history]
                return jsonify(display_history[::-1])
            except:
                return jsonify([])
    return jsonify([])
@app.route('/get_chat_detail/<dish_name>', methods=['GET'])
def get_chat_detail(dish_name):
    # Sử dụng hàm load_chat_history bạn đã viết sẵn
    history = load_chat_history(dish_name)
    if history:
        return jsonify({'dish': dish_name, 'history': history})
    return jsonify({'error': 'Không tìm thấy lịch sử'}), 404

@app.route('/clear_history', methods=['POST'])
def clear_history_server():
    try:
        # Xóa nội dung file lịch sử tìm kiếm
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f)
        
        # Xóa nội dung file chi tiết chat
        with open(CHAT_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f)
            
        return jsonify({'status': 'success', 'message': 'Đã xóa sạch dữ liệu trên server'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
if __name__ == '__main__':
    app.run(debug=True)