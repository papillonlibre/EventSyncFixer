from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import os.path
import pickle
from datetime import datetime, timezone
from googleapiclient.http import BatchHttpRequest

# token.pickle has to be deleted to reauth every time SCOPES is altered
SCOPES = ['https://www.googleapis.com/auth/calendar.events.owned']
COLORS = {
    "family and friends": "2", # green
    "classes": "5", # yellow
    "extracurricular": "4", # red
    "fitness": "7", # teal
    "work": "10", # green
    "networking, outreach": "8", # gray
    "personal development": "3", # lavendar
    "chores": "1" # baby blue
}

def reset_and_write_file(filename, data):
    with open(filename, 'w') as file:
        file.write(data)

def list_calendars(service):
    """
    Lists the calendars associated with the user's account

    param service: Authenticated Google Calendar API service instance.

    return: none
    Side effects:
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

def delete_calendar_duplicates(service, calendar_id):
    """
    Checks a specified calendar for duplicate events and then deletes the duplicates
    of the event off the calendar.

    param service: Authenticated Google Calendar API service instance.
    param calendar_id: ID of the Google Calendar being checked

    Returns: None
    Side effects:
        Deletes any events in the calendar that are found to be duplicates
    """

    page_token = None
    events = []
    # Fetch events from the calendar
    while True:
        events_result = service.events().list(calendarId=calendar_id, pageToken=page_token).execute()
        events.extend(events_result.get('items', [])) # extend unpacks event_results and adds each individual event to events
        # Search for the event with the given summary
        page_token = events_result.get('nextPageToken')
        if not page_token:
            break
    seen = set()
    duplicates = []

    for event in events:
        unique_event_key = ( # unique key for each event to avoid issue with recurring events
            event.get('summary'),  # Title of the event
            event.get('start', {}).get('dateTime', event.get('start', {}).get('date')),  # Start time/date
            event.get('end', {}).get('dateTime', event.get('end', {}).get('date'))  # End time/date
        )

        if unique_event_key in seen:
            duplicates.append(event)
        else:
            seen.add(unique_event_key)

    for duplicate in duplicates:
        try:
            service.events().delete(calendarId=calendar_id, eventId=duplicate['id']).execute()
            print(f"Deleted duplicate event: {duplicate.get('summary')}")
        except Exception as e:
            print(f"Failed to delete event: {duplicate.get('summary')}, Error: {e}")

    print(f"Total duplicates found and deleted: {len(duplicates)}")

def get_event_id_by_summary(service, calendar_id, event_summary):
    """
    Get the eventId of an event by its summary.

    param service: Authenticated Google Calendar API service instance.
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

def delete_event(service, calendarID, event_title):
    eventID = get_event_id_by_summary(service, calendarID, event_title)
    if eventID:
        event = service.events().get(calendarId=calendarID, eventId=event_title).execute()
        print(f"The event {event['summary']} will be deleted")
        service.events().delete(calendarId=calendarID, eventId=eventID).execute()
        print(f"The event {event['summary']} has been deleted")
    else:
        print(f"No event was found with the summary {event_title}. Please try again.")

def color_explorer(service):
    colors = service.colors().get().execute()
    event_colors = colors.get('event', {})

    # Print available event colors.
    for id, color in event_colors.items(): # iteritems was removed in Python 3
        print('colorId: %s' % id)
        print('Background: %s' % color['background'])
        print('Foreground: %s' % color['foreground'])

def log_to_file(message):
    """Helper function to log messages to a file called debug.txt."""
    with open("debug.txt", "a", encoding="utf-8") as log_file:
        log_file.write(message + "\n")

def batch_callback(request_id, response, exception):
    """
    Callback function to handle the results of batch requests.
    """
    if exception is not None:
        log_to_file(f"Error in request {request_id}: {exception}")
    else:
        log_to_file(f"Successfully updated event: {response.get('summary')} with color ID {response.get('colorId')}")

def update_event_colors_by_keyword(service, calendar_id, keyword, color_id):
    """
    Updates the color of events in a Google Calendar if their summary contains the specified keyword.
    
    param service: Authenticated Google Calendar API service instance.
    param calendar_id (str): The ID of the calendar (e.g., 'primary').
    param keyword (str): The keyword to filter by to determine color.
    param color_id (str): The color ID to apply to matching events.

    Returns:
        None
    Side effect:
        Changes the color of events in the specified calendar.
    """
    try:
        # Retrieve all events from the calendar
        page_token = None
        events_checked = 0  # Track the number of events checked
        events_updated = 0  # Track how many events were updated
        while True:
            events_result = service.events().list(calendarId=calendar_id, pageToken=page_token, singleEvents=True).execute()
            events = events_result.get('items', [])

            if not events:
                log_to_file("No events found.")
                return

            # Create a batch request
            batch = BatchHttpRequest(batch_uri="https://www.googleapis.com/batch/calendar/v3", callback=batch_callback)

            # Iterate through events and update the color if the keyword is found in the summary
            for event in events:
                events_checked += 1
                summary = event.get('summary', '')
                current_color_id = event.get('colorId', None)

                # Log event details for debugging
                log_to_file(f"Checking event: {summary} (Current Color: {current_color_id})")

                # Only update if the keyword is found and the color is not already set to the desired color
                if keyword.lower() in summary.lower() and current_color_id != color_id:
                    event['colorId'] = color_id  # Set the desired color
                    update_request = service.events().update(
                        calendarId=calendar_id,
                        eventId=event['id'],
                        body=event
                    )
                    batch.add(update_request)
                    events_updated += 1
                    log_to_file(f"Event '{summary}' will be updated to color ID {color_id}")
                elif(current_color_id == color_id):
                    log_to_file(f"Skipping event '{summary}' (Color already set to the desired color)")
                else:
                    log_to_file("Keyword not found in event summary")

            # Execute the batch
            if events_updated > 0:
                log_to_file("Executing batch...")
                batch.execute()

            # Move to the next page of events if available
            page_token = events_result.get('nextPageToken')
            if not page_token:
                break

        log_to_file(f"Total events checked: {events_checked}")
        log_to_file(f"Total events updated: {events_updated}")

    except Exception as e:
        log_to_file(f"An error occurred: {e}")
        print(f"An error occurred: {e}")
def main():
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the 1st time.
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
    reset_and_write_file('debug.txt', 'Initial content:\n')
    service = build('calendar', 'v3', credentials=creds)
    # delete_calendar_duplicates(service, "primary")
    update_event_colors_by_keyword(service, "primary", "CHEM-", COLORS["classes"])
    update_event_colors_by_keyword(service, "primary", "CS-", COLORS["classes"])
    update_event_colors_by_keyword(service, "primary", "PHIL-", COLORS["classes"])
    update_event_colors_by_keyword(service, "primary", "homework", COLORS["classes"])
    update_event_colors_by_keyword(service, "primary", "capstone", COLORS["classes"])
    update_event_colors_by_keyword(service, "primary", "STS-", COLORS["classes"])
    update_event_colors_by_keyword(service, "primary", "Alex", COLORS["family and friends"])
    update_event_colors_by_keyword(service, "primary", "Maddi", COLORS["family and friends"])
    update_event_colors_by_keyword(service, "primary", "Jordan", COLORS["family and friends"])
    update_event_colors_by_keyword(service, "primary", "Maman", COLORS["family and friends"])
    update_event_colors_by_keyword(service, "primary", "Gabby", COLORS["family and friends"])
    update_event_colors_by_keyword(service, "primary", "Kayla", COLORS["family and friends"])
    update_event_colors_by_keyword(service, "primary", "Morgan", COLORS["family and friends"])
    update_event_colors_by_keyword(service, "primary", "friends", COLORS["family and friends"])
    update_event_colors_by_keyword(service, "primary", "Swim", COLORS["fitness"])
    update_event_colors_by_keyword(service, "primary", "Lift", COLORS["fitness"])
    update_event_colors_by_keyword(service, "primary", "Doctor", COLORS["fitness"])
    update_event_colors_by_keyword(service, "primary", "Dentist", COLORS["fitness"])
    update_event_colors_by_keyword(service, "primary", "Workout", COLORS["fitness"])
    update_event_colors_by_keyword(service, "primary", "Robin", COLORS["networking, outreach"])
    update_event_colors_by_keyword(service, "primary", "E-week", COLORS["networking, outreach"])
    update_event_colors_by_keyword(service, "primary", "Mixer", COLORS["networking, outreach"])
    update_event_colors_by_keyword(service, "primary", "Megan", COLORS["networking, outreach"])
    update_event_colors_by_keyword(service, "primary", "Ambassadors", COLORS["networking, outreach"])
    update_event_colors_by_keyword(service, "primary", "cubesat", COLORS["extracurricular"])
    update_event_colors_by_keyword(service, "primary", "roboard", COLORS["extracurricular"])
    update_event_colors_by_keyword(service, "primary", "pacbot", COLORS["extracurricular"]) 
    update_event_colors_by_keyword(service, "primary", "notetaking", COLORS["personal development"])
    update_event_colors_by_keyword(service, "primary", "notes", COLORS["personal development"])
    update_event_colors_by_keyword(service, "primary", "readings", COLORS["personal development"])
    # color_explorer(service)
if __name__ == '__main__':
    main()