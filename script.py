import os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from matrix_client.api import MatrixHttpApi

# Authenticate with the Gmail API
creds = None
if os.path.exists('token.json'):
    creds = Credentials.from_authorized_user_file('token.json', ['https://www.googleapis.com/auth/gmail.readonly', 'https://www.googleapis.com/auth/gmail.modify'])
service = build('gmail', 'v1', credentials=creds)

# Search for unread messages with the "PW Reset Mails" label
result = service.users().messages().list(userId='me', q='label:PW Reset Mails is:unread').execute()
messages = result.get('messages', [])

# Store the sender and subject of each unread message in a string
message_info = ""
for message in messages:
    msg = service.users().messages().get(userId='me', id=message['id']).execute()
    headers = msg['payload']['headers']
    sender = [header['value'] for header in headers if header['name'] == 'From'][0]
    subject = [header['value'] for header in headers if header['name'] == 'Subject'][0]
    message_info += f"Sender: {sender}\nSubject: {subject}\n\n"

# Send the message info to a Matrix channel using a bot user account
matrix_api = MatrixHttpApi("https://your_matrix_server.com", access_token="your_bot_access_token")
room_id = "!your_room_id:your_matrix_server.com"
matrix_api.send_message(room_id, message_info)