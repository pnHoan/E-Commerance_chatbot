import httpx
import hmac
import hashlib
import asyncio

from .requestHandler import handle_case1, handle_case3, handle_case2,handle_case4, handle_default, send_webhook_message
from .semanticHandler import semanticCollection 

from config import Config

from db.mongo import db

async def request_classifier(message):
    col = semanticCollection("req") 
    result = await col.semanticSearch(message,["case_no","similarities"])
    if result[0][1] >= 0.82:
        case_mapping = {
            "case1_recommendation": "case_1",
            "case2_placeOrder": "case_2",
            "case3_contactHuman": "case_3",
            "case4_getLocation": "case_4"
        }
        case_no = result[0][0]
        if case_no in case_mapping:
            return case_mapping[case_no]
        
    return "default"
    


def verify_signature(signature, payload):
    expected_signature = 'sha1=' + hmac.new(Config.APP_SECRET.encode(), payload, hashlib.sha1).hexdigest()
    print(expected_signature)
    return hmac.compare_digest(signature, expected_signature)


def verify_webhook(req):
    if req.args.get("hub.verify_token") == Config.VERIFY_TOKEN:
        return req.args.get("hub.challenge")
    else:
        return "incorrect"

def is_user_message(message):
    """Check if the message is a message from the user"""
    return (message.get('message') and
            message['message'].get('text') and
            not message['message'].get("is_echo"))



async def send_message(recipient_id, page_id , text ,access_token):
    """Send a response to Facebook"""
    payload = {
        "messaging_type": "RESPONSE",
        "message":{
            "text":text
        },
        "recipient": {
            'id': recipient_id
        }
    }   
                
    auth = {
        'access_token': access_token,
    }
    
    async with httpx.AsyncClient() as client:
        response= await client.post(f"https://graph.facebook.com/v16.0/{page_id}/messages", params=auth, json=payload)
        return response.json()

   
async def subscribe_app( PAGE_ID , PAGE_ACCESS_TOKEN):
    url = f'https://graph.facebook.com/v16.0/{PAGE_ID}/subscribed_apps'
    headers = {
        'Content-Type': 'application/json'
    }
    data = {
        'app_id': Config.APP_ID,
        'subscribed_fields': 'messages',
        'access_token': PAGE_ACCESS_TOKEN 
    }
   
    async with httpx.AsyncClient() as client:
        response= await client.post(url, headers=headers, data=data)
        return response.json()

async def get_facebook_user( access_token):
    url = f'https://graph.facebook.com/v16.0/me?access_token={access_token}&fields=id,name'
    headers = {
        'Content-Type': 'application/json'
    }
    async with httpx.AsyncClient() as client:
        response= await client.get(url, headers=headers)
        return response.json()



async def handle_facebook_message(user_id, page_id, message):
    """Formulate a response to the user and
    pass it on to a function that sends it."""
    page = await db.find_one_document("pages" ,{'page_id': page_id})
    if not page:
       return
    webhook = page['webhook']
    access_token = page['access_token']
    field = page['field'] if 'field' in page else 'clothings'
    location = page['location'] if 'location' in page else ''
    shop_link = page['shop_link'] if 'shop_link' in page else ''
    request_type = await request_classifier(message)

    print(f"type {request_type}")
    match request_type:
        case "case_1":
            response = handle_case1(message)
            return await send_message(user_id , page_id, response, access_token)
        case "case_2":
            response = handle_case2(shop_link)
            if webhook:
                return await asyncio.gather(send_webhook_message(type="order", message=message, user_id=user_id,url=webhook), send_message(user_id , page_id, response, access_token))
            else:
                return await send_message(user_id , page_id, response, access_token)
        case "case_3":
            response = handle_case3(message)
            if webhook:
                return await asyncio.gather(send_webhook_message(type="assistant", message=message, user_id=user_id, url=webhook), send_message(user_id , page_id, response, access_token))
            else:
                return await send_message(user_id , page_id, response, access_token)
        case "case_4":
            response = handle_case4(location)
            return await send_message(user_id , page_id, response, access_token)
        case "default":
            response = handle_default(message, field=field)
            return await send_message(user_id , page_id, response, access_token)
    

