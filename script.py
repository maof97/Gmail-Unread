import os
import logging
import os.path
import json

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import matrix_client.api as matrix_client_api
import matrix_client.errors

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="[%(asctime)s] %(levelname)s %(message)s", handlers=[logging.FileHandler("script.log"), logging.StreamHandler()]
)

# Define constants
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly", "https://www.googleapis.com/auth/gmail.modify"]
TOKEN_FILE = "token.json"
SERVICE_ACCOUNT_FILE = "token_cred.json"
MATRIX_FILE = "matrix-credentials.json"

# Get Matrix credentialss from json file:
try:
    MATRIX_ACCESS_TOKEN = json.load(open(MATRIX_FILE))["MATRIX_TOKEN"]
    MATRIX_ROOM_ID = json.load(open(MATRIX_FILE))["MATRIX_ROOM_ID"]
    # MATRIX_USER_ID = json.load(open(MATRIX_FILE))["MATRIX_USER_ID"]
    MATRIX_SERVER = json.load(open(MATRIX_FILE))["MATRIX_SERVER"]
except Exception as e:
    logging.error(f"Unable to retrieve Matrix credentials: {str(e)}")
    exit()


def login_browser(creds):
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file(TOKEN_FILE, SCOPES)
        creds = flow.run_local_server(port=0)
    # Save the credentials for the next run
    with open(SERVICE_ACCOUNT_FILE, "w") as token:
        token.write(creds.to_json())


def main():
    """Shows basic usage of the Gmail API.
    Lists the user's Gmail labels.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists(SERVICE_ACCOUNT_FILE):
        creds = Credentials.from_authorized_user_file(SERVICE_ACCOUNT_FILE, SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        login_browser(creds)

    try:
        # Call the Gmail API
        gmail_service = build("gmail", "v1", credentials=creds)
        # Create Matrix API client
        matrix_client = matrix_client_api.MatrixHttpApi(MATRIX_SERVER, token=MATRIX_ACCESS_TOKEN)

        # Check if credentials and API clients are initialized successfully
        if not gmail_service or not matrix_client:
            logging.error("Initialization failed. Exiting.")
            exit()

        # Search for unread messages with specific label
        query = "is:unread label:PW Reset Mails"
        try:
            response = gmail_service.users().messages().list(userId="me", q=query).execute()
            messages = response.get("messages", [])
        except Exception as e:
            logging.error(f"Unable to search for messages: {str(e)}")
            exit()

        # If there are unread messages, send an alert to Matrix
        if messages:
            logging.info(f"{len(messages)} unread messages found.")
            alert_message = ""
            for msg in messages:
                try:
                    message = gmail_service.users().messages().get(userId="me", id=msg["id"]).execute()

                    # Get sender and subject of message
                    for header in message["payload"]["headers"]:
                        if header["name"] == "From":
                            sender = header["value"]
                        if header["name"] == "Subject":
                            subject = header["value"]

                    alert_message += f"Sender: {sender}\nSubject: {subject}\n\n"
                except Exception as e:
                    logging.error(f"Unable to retrieve message: {str(e)}")

            # Send the alert to Matrix
            try:
                matrix_client.send_message_event(
                    room_id=MATRIX_ROOM_ID,
                    event_type="m.room.message",
                    content={"msgtype": "m.text", "body": f"Unread messages in Gmail:\n{alert_message}"},
                )
                logging.info("Alert sent to Matrix successfully.")
            except Exception as e:
                logging.error(f"Unable to send alert to Matrix: {str(e)}")

            # Mark messages as read
            try:
                for msg in messages:
                    gmail_service.users().messages().modify(userId="me", id=msg["id"], body={"removeLabelIds": ["UNREAD"]}).execute()
                logging.info("Messages marked as read.")
            except Exception as e:
                logging.error(f"Unable to mark messages as read: {str(e)}")

        else:
            logging.info("No unread messages found.")

    except HttpError as error:
        # TODO(developer) - Handle errors from gmail API.
        logging.error(f"An error occurred: {error}")


if __name__ == "__main__":
    creds = Credentials.from_authorized_user_file(SERVICE_ACCOUNT_FILE, SCOPES)
    login_browser(creds)
    main()
