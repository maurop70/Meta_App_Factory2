import google.auth
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

class MarketTrendExtractor:
    """
    Skill for the Analyst Persona.
    Extracts text and numerical trends from Google Sheets and Slides.
    """
    def __init__(self, credentials_path=None):
        # In a real environment, we'd load credentials here
        # For now, we assume the environment is authenticated (e.g. ADC)
        pass

    def get_sheet_trends(self, spreadsheet_id, range_name):
        """Extracts numerical trends from a specific sheet range."""
        try:
            service = build('sheets', 'v4')
            sheet = service.spreadsheets()
            result = sheet.values().get(spreadsheetId=spreadsheet_id,
                                        range=range_name).execute()
            values = result.get('values', [])

            if not values:
                return "No data found."
            
            # Simple trend analysis logic (placeholder for complexity)
            return values
        except Exception as e:
            return f"An error occurred: {e}"

    def get_slides_text(self, presentation_id):
        """Extracts all text from a Google Slides deck for brand style analysis."""
        try:
            service = build('slides', 'v1')
            presentation = service.presentations().get(presentationId=presentation_id).execute()
            slides = presentation.get('slides')

            text_content = []
            for slide in slides:
                for element in slide.get('pageElements'):
                    if 'shape' in element and 'text' in element['shape']:
                        text_content.append(element['shape']['text']['textElements'][0]['textRun']['content'])
            
            return "\n".join(text_content)
        except Exception as e:
            return f"An error occurred: {e}"

if __name__ == "__main__":
    # Internal test placeholder
    print("MarketTrendExtractor Skill Initialized.")
