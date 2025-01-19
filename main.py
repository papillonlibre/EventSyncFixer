from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import os.path
import pickle
import datetime

# If modifying these SCOPES, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

def list_calendars(service):
    """
    Lists the calendars associated with the user's account
    return: none
        prints out the list when accessed
    """
    page_token = None
    while True:
        calendars_result = service.calendarList().list(pageToken=page_token).execute()
        calendars = calendars_result.get('items', [])
        
        if not calendars:
            print("No calendars found.")
            return
        
        for calendar in calendars:
            print(f"ID: {calendar['id']}, Summary: {calendar['summary']}")

        page_token = calendars_result.get('nextPageToken')
        if not page_token:
            break

def upcoming_events(service, calendarID, n):
    """
    Get a list of the upcoming events for a given calendar

    param calendarID: ID of the Google Calendar
    return: none
        prints out the events retrieved based on the startTime specified
    """
    now = datetime.datetime.now().astimezone().isoformat() # .now.astimezone() grabs the system's time zone rather than defaulting to UTC
    print(f'Getting the upcoming {n} events')
    events_result = service.events().list(calendarId=calendarID, timeMin=now,
                                          maxResults=n, singleEvents=True,
                                          orderBy='startTime').execute().get('items', [])

    if not events_result:
        print('No upcoming events found.')
    for event in events_result:
        start = event['start'].get('dateTime', event['start'].get('date'))
        print(start, event['summary'])

def get_event_id_by_summary(service, calendar_id, event_summary):
    """
    Get the eventId of an event by its summary.

    param calendar_id: ID of the Google Calendar (e.g., 'primary' for the main calendar).
    param event_summary: The summary/title of the event.
    return: The eventId of the matching event or None if not found.
    """
    page_token = None
    # Fetch events from the calendar
    while True:
        events_result = service.events().list(calendarId=calendar_id, pageToken=page_token).execute()
        events = events_result.get('items', [])
        # Search for the event with the given summary
        for event in events:
            if event.get('summary') == event_summary:
                return event.get('id')  # Return the eventId
        page_token = events_result.get('nextPageToken')
        if not page_token:
            break

    return None  # Event not found

def delete_test(service, calendarID, event_title):
    eventID = get_event_id_by_summary(service, calendarID, event_title)
    if eventID:
        event = service.events().get(calendarId=calendarID, eventId=eventID).execute()
    else:
        print(f"No event was found with the summary {event_title}. Please try again.")

def main():
    """Shows basic usage of the Google Calendar API.
    Lists the next 10 events on the user's calendar.
    """
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    # Call the Google Calendar API and execute functions
    service = build('calendar', 'v3', credentials=creds)
    get_event_id_by_summary(service, "primary", "silly test")
    delete_test(service, "primary", "silly test")
    delete_test(service, "primary", "beep boop bop") # event should not be found

if __name__ == '__main__':
    main()