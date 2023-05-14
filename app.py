from functools import wraps
from flask import Flask, g, request, jsonify
import jwt
import requests
from config import Config
from db.mongo import pagesCollection, clientsCollection
from dotenv import load_dotenv

from handlers.facebookHandler import handle_facebook_message, is_user_message, send_message, verify_signature, verify_webhook
from handlers.sslHandler import has_valid_ssl
app = Flask(__name__)

load_dotenv()


def token_user_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')

        if not token:
            return jsonify({'message': 'Token is missing!'}), 401

        try:
            data = jwt.decode(token, app.config['SECRET_KEY'])
            g.user_id = data['user_id'] 
        except:
            return jsonify({'message': 'Token is invalid!'}), 401

        return f(*args, **kwargs)

    return decorated



def token_webhook_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')

        if not token:
            return jsonify({'message': 'Token is missing!'}), 401

        try:
            data = jwt.decode(token, app.config['SECRET_KEY'])
            g.page_id = data['page_id'] 
        except:
            return jsonify({'message': 'Token is invalid!'}), 401

        return f(*args, **kwargs)

    return decorated

@app.route('/send_message', methods=['POST'])
@token_webhook_required
def webhook_send_message():
    page_id = g.page_id
    text= request.json['text']
    user_id =request.json['user_id']
    try:
        send_message(user_id=user_id, page_id=page_id, text=text)
        return jsonify({"ok: true"}), 200
    except: 
        return jsonify({'message': 'Internal server error'}), 503

@app.route("/add_page_info", methods=['POST'])
@token_user_required
def set_page_info():
    if request.method == 'POST':
        PAGE_ACCESS_TOKEN = request.json.get("page_access_token")
        PAGE_ID = request.json.get("page_id")
        user_id = request.json.get("user_id")
        
        url = f'https://graph.facebook.com/v16.0/{PAGE_ID}/subscribed_apps'
        headers = {
            'Content-Type': 'application/json'
        }
        data = {
            'app_id': Config.APP_ID,
            'subscribed_fields': 'messages',
            'access_token': PAGE_ACCESS_TOKEN 
        }

        response = requests.post(url, headers=headers, data=data)

        if response.status_code == 200:
            result = pagesCollection.find_one({'page_id': PAGE_ID})
        

            print(result)
            if result is None:
                pagesCollection.insert_one({
                    'page_id': PAGE_ID,
                    'user_id': user_id,
                    'access_token': PAGE_ACCESS_TOKEN,
                    'webhook': ''
                })
            else:
                pagesCollection.update_one({'page_id': PAGE_ID}, {'$set': {'access_token': PAGE_ACCESS_TOKEN}})
            return jsonify({"message": "Page info added successfully."}), 200
        else:
            jsonify({"error": "Add page failed."}), 400
    else:
        return jsonify({"error": "Unsupported request method."}), 400

@app.route("/webhook", methods=['GET', 'POST'])
def listen():
    """This is the main function flask uses to 
    listen at the `/webhook` endpoint"""
    if request.method == 'GET':
        return verify_webhook(request)

    if request.method == 'POST':
        signature = request.headers.get('X-Hub-Signature')
        payload = request.get_data()
        if not verify_signature(signature, payload):
            return jsonify({"error": "Unsupported request method."}), 400
        payload = request.json
        
        for entry in payload['entry']:
            page_id = entry['id']
            for event in entry['messaging']:
                if is_user_message(event):
                    text = event['message']['text']
                    sender_id = event['sender']['id']
                    page = pagesCollection.find_one({'page_id': page_id})
                    if page:
                        handle_facebook_message(sender_id,page_id, text )

        return "ok"

@app.route('/set_webhook_url', methods=['POST'])
@token_user_required
def set_webhook_url():
    page_webhook_url = request.json.get("page_webhook_url")
    page_id = request.json.get("page_id")
    if not has_valid_ssl(page_webhook_url):
       return jsonify({"error": "Insecure request. Please use HTTPS."}), 400
    
    query = {'page_id': page_id}
    document = pagesCollection.find_one(query)
    if document:
        pagesCollection.update_one(query, {'$set': {"webhook": page_webhook_url}})
    else: 
        return jsonify({"error": "Page Id not exist in database."}), 400
    

    token = jwt.encode(
                {'page_id': page_id, 'page_webhook_url': page_webhook_url},
                Config.JWT_SECRET_KEY,
                algorithm='HS256'
            )
    return jsonify({'token': token}), 200
    
@app.route('/getWebhooks', methods=['GET'])
@token_user_required
def getWebhooks():
    user_id = g.user_id
    query = {'user_id': user_id}
    client=  clientsCollection.find_one({'client_id': user_id})
    if not client:
        return jsonify({"error": "user_id not exist in database."}), 400
    document = pagesCollection.find(query)
    
    return jsonify(document), 200
        
@app.route('/auth/facebook', methods =['POST'])
def loginUser():
    access_token = request.json.get("access_token")
    url = f'https://graph.facebook.com/v16.0/me?access_token=${access_token}&fields=id,name'
    headers = {
        'Content-Type': 'application/json'
    }
    try:
        response = requests.get(url, headers=headers).json()
        user_id = response['id']
        name = response['name']
        clientsCollection.find_one_and_update({"client_id": user_id }, {'$set': {"name": name, "client_id":user_id}})
        token = jwt.encode(
                {'user_id': user_id, 'name': name},
                Config.JWT_SECRET_KEY,
                algorithm='HS256'
            )
        return jsonify({'token': token}), 200
    except Exception as e:
        print(e)
        return jsonify({'message': 'Authentication failed'}), 401


def main():
    app.run()


if __name__ == "__main__":
    main()