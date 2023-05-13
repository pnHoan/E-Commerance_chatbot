import openai
import re
from config import Config
from db.mongo import db

# Set up a connection to the OpenAI API
openai.api_key = Config.OPENAI_API_KEY

# Define a function to send a message to the GPT-3 API and retrieve a response
def get_gpt3_response(prompt):
    response = openai.Completion.create(
        engine="text-davinci-003",
        prompt=prompt,
        max_tokens=1024,
        n=1,
        stop=None,
        temperature=0,
    )
    return response.choices[0].text

def check_relativity(message):
    prompt = f"{message}. Is this sentence related to clothings ?. return 'Y' or 'N' as answer."
    response = openai.Completion.create(
        engine="text-davinci-003",
        prompt=prompt,
        max_tokens=1024,
        n=1,
        stop=None,
        temperature=0,
    )
    res = response.choices[0].text
    return ' '.join(res.strip().split())

# def extract_search_parameters(response):
#     search_params = {}
#     match = re.search('Name: (.*?), Color: (.*?), Size: (.*?).', response)
#     if match:
#         search_params['name'] = match.group(1).strip()
#         search_params['color'] = match.group(2).strip()
#         search_params['size'] = match.group(3).strip()
#     return search_params


# Define a function to handle customer messages
# def handle_chatgpt_message(sender,message):
#     #TODO: Fix default promt
#     prompt = "Please return name, color, size of clothes based on the customer's message (if the value does not exist, please return None):\nCustomer: " + message + "\nClothes:"

#     # Send the message to the GPT-3 API and retrieve a response
#     response = get_gpt3_response(prompt)
 
#     return response 

#     # # Present the search results to the customer
#     # if len(results) == 0:
#     #     return "I'm sorry, I couldn't find any clothes that match your search criteria."
#     # else:
#     #     result_strings = []
#     #     for result in results:
#     #         result_strings.append(f"{result['name']} in {result['color']} color, size {result['size']}, quantity {result['quantity']}, price {result['price']}")
#     #     return "I found the following clothes that match your search criteria:\n" + "\n".join(result_strings)