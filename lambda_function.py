import logging
import os
from datetime import datetime, timedelta

import requests
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

CHANNEL_ID = os.environ.get("CHANNEL_ID")
USER_TOKEN = os.environ.get("USER_TOKEN")
NOTION_PAGE_ID = os.environ.get("NOTION_PAGE_ID")
slack_client = WebClient(token=USER_TOKEN)

DAILY_STATUS_FILTER_TEXT = "Good morning! Don’t forget to post your update in thread."
DAILY_STATUS_FILTER_POD_NAME = "learningpod"
AUTOMATED_MESSAGE = "Note: This is an automated message 😋"

logger = logging.getLogger(__name__)


class NotionClassName():
    NOTION_URL = "https://energetic-tuberose-21a.notion.site/api/v3/loadCachedPageChunk"

    def __init__(self, name) -> None:
        self.name = name

    def request_data_from_notion(self):
        response = requests.post(self.NOTION_URL,
                                 json={
                                     "page": {
                                         "id": NOTION_PAGE_ID
                                     },
                                     "limit": 30,
                                     "cursor": {
                                         "stack": []
                                     },
                                     "chunkNumber": 0,
                                     "verticalColumns": False
                                 })
        response_data= response.json()
        data=response_data.get("recordMap", {}).get("block", {})
        return data


def parse_text(title):
    text_list = []
    for text_data in title:
        # Text only
        if len(text_data) == 1:
            text_list.append(text_data[0])
        # Text with link
        elif text_data[1][0] and text_data[1][0][0] == 'a':
            # text_list.append(f"[{text_data[0]}]({text_data[1][0][1]})")
            text_list.append(text_data[0])
    complete_text = ''.join(text_list)
    return complete_text

def format_text(text, value_type):
    if value_type == 'text':
        return text
    elif value_type == 'bulleted_list':
        return f"•   {text}"
    elif value_type == 'page':
        return None


def parse_response(data):
    page = []
    for _, data_value in data.items():
        value = data_value.get('value')
        value_type = value.get('type')
        title = value.get('properties', {}).get('title', [['']])
        text = parse_text(title)

        if not text:
            break

        text = format_text(text, value_type)
        if text:
            page.append(text)
    page.append(AUTOMATED_MESSAGE)
    page_string = '\n'.join(page)
    return page_string

def print_data(page):
    """
    For debugging
    """
    for line in page:
        print(line)


def post_to_slack(text, thread_id):
    try:
        result = slack_client.chat_postMessage(
            channel=CHANNEL_ID,
            text=text,
            thread_ts=thread_id
        )
        logger.info(result)

    except SlackApiError as e:
        logger.error(f"Error posting message: {e}")

def get_status_thread_id():
    try:
        older_time = (datetime.now()-timedelta(hours=12)).timestamp()
        result = slack_client.conversations_history(channel=CHANNEL_ID, oldest=older_time)
        conversation_history = result["messages"]
        for conversation_data in conversation_history:
            text = conversation_data.get('text')
            if DAILY_STATUS_FILTER_TEXT in text and DAILY_STATUS_FILTER_POD_NAME in text:
                return conversation_data.get('ts')

    except SlackApiError as e:
        logger.error(f"Error getting message: {e}")


def lambda_handler(event, context):
    # Due to some unknown reason Notion gives correct data only in the second api call.
    data = request_data_from_notion()
    data = request_data_from_notion()

    page = parse_response(data)
    thread_id = get_status_thread_id()
    if thread_id and page != AUTOMATED_MESSAGE:
        post_to_slack(page, thread_id)
        logger.info(f"Successfully posted")
    elif page == AUTOMATED_MESSAGE:
        logger.info(f"Not posting status")
    else:
        logger.error(f"Couldn't get thread id: {thread_id}")
    return {
        'message' : "Success",
        'status_code': 200
    }



if __name__ == '__main__':
    lambda_handler(None, None)
