import os
import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build
import matrix_client.api
import matrix_client.errors

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("script.log"),
        logging.StreamHandler()
    ]
)

# Define constants
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
SERVICE_ACCOUNT_FILE = '/path/to/service-account.json'
MATRIX_USER_ID = '@your_matrix_user_id:your_matrix_server'
MATRIX_ACCESS_TOKEN = 'your_matrix_access_token'
MATRIX_ROOM_ID = '!your_room_id:your_matrix_server'

# Create credentials object
creds = None
try:
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)
except FileNotFoundError:
    logging.error("Service account file not found.")
except Exception as e:
    logging.error(f"Unable to create credentials object: {str(e)}")

# Create Gmail API client
gmail_service = None
if creds:
    try:
        gmail_service = build('gmail', 'v1', credentials=creds)
    except Exception as e:
        logging.error(f"Unable to create Gmail API client: {str(e)}")

# Create Matrix API client
matrix_client = matrix_client.api.MatrixHttpApi(
    'https://your_matrix_server', token=MATRIX_ACCESS_TOKEN)

# Check if credentials and API clients are initialized successfully
if not creds or not gmail_service or not matrix_client:
    logging.error("Initialization failed. Exiting.")
    exit()

# Search for unread messages with specific label
query = "is:unread label:PW Reset Mails"
try:
    response = gmail_service.users().messages().list(userId='me', q=query).execute()
    messages = response.get('messages', [])
except Exception as e:
    logging.error(f"Unable to search for messages: {str(e)}")
    exit()

# If there are unread messages, send an alert to Matrix
if messages:
    logging.info(f"{len(messages)} unread messages found.")
    alert_message = ""
    for msg in messages:
        try:
            message = gmail_service.users().messages().get(userId='me', id=msg['id']).execute()
            sender = message['payload']['headers'][0]['value']
            subject = message['payload']['headers'][16]['value']
            alert_message += f"Sender: {sender}\nSubject: {subject}\n\n"
        except Exception as e:
            logging.error(f"Unable to retrieve message: {str(e)}")

    # Send the alert to Matrix
    try:
        matrix_client.send_message_event(
            room_id=MATRIX_ROOM_ID,
            event_type="m.room.message",
            content={
                "msgtype": "m.text",
                "body": f"Unread messages in Gmail:\n{alert_message}"
            },
            user_id=MATRIX_USER_ID
        )
        logging.info("Alert sent to Matrix successfully.")
    except matrix_client.errors.MatrixRequestError as e:
        logging.error(f"Unable to send alert to Matrix: {str(e)}")
else:
    logging.info("No unread messages found.")
