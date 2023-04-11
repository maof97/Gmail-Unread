import os
import logging
import os.path
import json

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.exceptions import RefreshError

import matrix_client.api as matrix_client_api

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="[%(asctime)s] %(levelname)s %(message)s", handlers=[logging.FileHandler("script.log"), logging.StreamHandler()]
)

# Define constants
SCOPES = ["https://www.googleapis.com/auth/gmail.metadata", "https://www.googleapis.com/auth/gmail.labels"]
TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "token.json")
SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "token_cred.json")
MATRIX_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "matrix-credentials.json")
HANDLED_FILES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "handled_messages.txt")

# Get Matrix credentialss from json file:
try:
    MATRIX_ACCESS_TOKEN = json.load(open(MATRIX_FILE))["MATRIX_TOKEN"]
    MATRIX_ROOM_ID = json.load(open(MATRIX_FILE))["MATRIX_ROOM_ID"]
    # MATRIX_USER_ID = json.load(open(MATRIX_FILE))["MATRIX_USER_ID"]
    MATRIX_SERVER = json.load(open(MATRIX_FILE))["MATRIX_SERVER"]
except Exception as e:
    logging.warning(f"Unable to retrieve Matrix credentials: {str(e)}")
    exit()


def login_browser(creds):
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except RefreshError as e:
            logging.critical(f"Unable to refresh credentials: {str(e)} MANUAL INTERVENTION REQUIRED!")
            logging.info("Removing invalid credetials.")
            os.remove(SERVICE_ACCOUNT_FILE)

            # Inform user to re-run script via Matrix
            # First check if message was not already sent by looking for "Sending alert to Matrix"  in log file
            with open("script.log", "r") as f:
                if "Sending alert to Matrix" in f.read():
                    logging.info("Alert already sent to Matrix. Exiting.")
                    exit()

            logging.info("Sending alert to Matrix.")
            matrix_client = matrix_client_api.MatrixHttpApi(MATRIX_SERVER, token=MATRIX_ACCESS_TOKEN)
            matrix_client.send_message_event(
                room_id=MATRIX_ROOM_ID,
                event_type="m.room.message",
                content={"msgtype": "m.text", "body": "⚠️ Gmail credentials expired. Please re-run script manually."},
            )
            logging.info("Alert sent to Matrix.")

            logging.info("Exiting.")
            exit()
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

        # Search for unread messages with specific label, but without 'q' using format=METADATA and labelIds
        query = "is:unread label:PW Reset Mails"
        try:
            # response = gmail_service.users().messages().list(userId="me", labelIds=["UNREAD", "PW Reset Mails"]).execute()
            response = gmail_service.users().messages().list(userId="me", labelIds=["Label_2839713299079306617"]).execute()
            messages = response.get("messages", [])
        except Exception as e:
            logging.error(f"Unable to search for messages: {str(e)}")
            exit()

        # If there are unread messages, send an alert to Matrix
        if messages:
            # Check if there are any messages that have already been handled
            handled_messages = []
            if os.path.exists(HANDLED_FILES):
                with open(HANDLED_FILES, "r") as f:
                    handled_messages = f.read().splitlines()

            # Remove handled messages from list
            messages = [msg for msg in messages if msg["id"] not in handled_messages]
            if not messages:
                logging.info("No new messages found.")
                exit()

            # Get message details for each message
            logging.info(f"{len(messages)} unread messages found.")
            alert_message = ""
            for msg in messages:
                try:
                    message = gmail_service.users().messages().get(userId="me", id=msg["id"], format="metadata").execute()

                    # Get sender and subject of message
                    for header in message["payload"]["headers"]:
                        if header["name"] == "From":
                            sender = header["value"]
                        if header["name"] == "Subject":
                            subject = header["value"]

                    alert_message += f"Sender: {sender}\nSubject: {subject}\n\n"
                    logging.info(f"New message from '{sender}' with subject '{subject}' message id: '{msg['id']}'")
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

            # Write handled messages to file
            with open(HANDLED_FILES, "a") as f:
                for msg in messages:
                    f.write(f"{msg['id']}\n")
                    logging.info(f"Message '{msg['id']}' written to file.")

        else:
            logging.info("No messages found.")

    except HttpError as error:
        # TODO(developer) - Handle errors from gmail API.
        logging.error(f"An error occurred: {error}")


if __name__ == "__main__":
    main()
