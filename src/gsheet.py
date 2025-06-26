import re

import gspread
from gspread.spreadsheet import Spreadsheet
from gspread.worksheet import Worksheet

from src.auth import get_credentials
from src.config import SPREADSHEET_ID
from src.models import NEVER_SHOWN, Card, CardSet, Levels
from src.utils import format_timestamp, parse_timestamp


def extract_spreadsheet_id(url_or_id: str) -> str:
    """Extract spreadsheet ID from Google Sheets URL or return ID if already provided"""
    # If it's already just an ID (no slashes), return as-is
    if '/' not in url_or_id:
        return url_or_id.strip()

    # Extract ID from various Google Sheets URL formats
    patterns = [
        r'/spreadsheets/d/([a-zA-Z0-9-_]+)',  # Standard URL
        r'[?&]id=([a-zA-Z0-9-_]+)',  # Query parameter
        r'/d/([a-zA-Z0-9-_]+)/edit',  # Edit URL
    ]

    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)

    # If no pattern matches, assume it's already an ID
    return url_or_id.strip()


def validate_spreadsheet_access(spreadsheet_id: str) -> tuple[bool, str, list[str]]:
    """
    Validate that the user has access to the spreadsheet and it has the correct format
    Returns: (is_valid, error_message, worksheet_names)
    """
    creds = get_credentials()
    if not creds:
        return False, 'Not authenticated with Google', []

    try:
        gc = gspread.authorize(creds)
        spreadsheet = gc.open_by_key(spreadsheet_id)

        # Get worksheet names
        worksheets = spreadsheet.worksheets()
        worksheet_names = [ws.title for ws in worksheets]

        # Basic validation - check if at least one worksheet exists
        if not worksheets:
            return False, 'Spreadsheet has no worksheets', []

        # Try to read the first worksheet to validate format
        first_worksheet = worksheets[0]
        values = first_worksheet.get_all_values()

        if not values or len(values) < 2:  # Need at least header + 1 data row
            return (
                False,
                'Spreadsheet appears to be empty or has insufficient data',
                worksheet_names,
            )

        # Check if header row has expected columns (basic validation)
        header = values[0] if values else []
        expected_columns = ['id', 'word', 'translation']  # Minimum required columns

        # Convert to lowercase for comparison
        header_lower = [col.lower() for col in header]
        missing_columns = [col for col in expected_columns if col not in header_lower]

        if missing_columns:
            return (
                False,
                f'Missing required columns: {", ".join(missing_columns)}. Expected columns: id, word, translation, equivalent, example',
                worksheet_names,
            )

        return True, 'Spreadsheet is valid', worksheet_names

    except gspread.SpreadsheetNotFound:
        return (
            False,
            "Spreadsheet not found. Please check the URL/ID and make sure it's shared with your Google account.",
            [],
        )
    except gspread.APIError as e:
        return False, f'Google Sheets API error: {e!s}', []
    except Exception as e:
        return False, f'Error accessing spreadsheet: {e!s}', []


def get_spreadsheet(spreadsheet_id: str = None) -> Spreadsheet | None:
    """Get spreadsheet by ID, falls back to default if not provided"""
    creds = get_credentials()
    if not creds:
        return None

    # Use provided ID or fall back to default
    sheet_id = spreadsheet_id or SPREADSHEET_ID

    try:
        gc = gspread.authorize(creds)
        spreadsheet = gc.open_by_key(sheet_id)
        return spreadsheet
    except Exception as e:
        print(f'Error accessing spreadsheet {sheet_id} with auth using creds {creds}: {e}')
        return None


def get_worksheet(worksheet_name, spreadsheet_id: str = None) -> Worksheet | None:
    """Get a specific worksheet by name"""
    spreadsheet = get_spreadsheet(spreadsheet_id)
    if not spreadsheet:
        return None

    try:
        worksheet = spreadsheet.worksheet(worksheet_name)
        return worksheet
    except Exception as e:
        print(f'Error accessing worksheet {worksheet_name}: {e}')
        return None


def read_all_card_sets(spreadsheet_id: str = None) -> list[CardSet]:
    """Get all card sets from the spreadsheet"""
    spreadsheet = get_spreadsheet(spreadsheet_id)
    if not spreadsheet:
        return []

    # Get all worksheets
    worksheets = spreadsheet.worksheets()
    worksheets_parsed = []

    for worksheet in worksheets:
        cards = read_cards_from_worksheet(worksheet)
        worksheet_parsed = CardSet(
            name=worksheet.title,
            gid=worksheet.id,  # Capture the permanent sheet ID
            cards=cards,
        )
        worksheets_parsed.append(worksheet_parsed)

    return worksheets_parsed


def read_card_set(worksheet_name, spreadsheet_id: str = None) -> CardSet | None:
    worksheet = get_worksheet(worksheet_name, spreadsheet_id)
    if not worksheet:
        return None

    cards = read_cards_from_worksheet(worksheet)
    worksheet_parsed = CardSet(
        name=worksheet.title,
        gid=worksheet.id,  # Capture the permanent sheet ID
        cards=cards,
    )
    return worksheet_parsed


def read_cards_from_worksheet(worksheet) -> list[Card]:
    """Read data from a specific worksheet"""

    values = worksheet.get_all_values()

    if not values:
        return []

    # Skip the header row
    data_rows = values[1:]
    cards = []

    for row in data_rows:
        if not row or len(row) < 5 or not row[0]:  # Skip empty rows
            continue

        # Pad the row if it doesn't have enough columns
        padded_row = row + [''] * (10 - len(row)) if len(row) < 10 else row

        try:
            card = Card(
                id=int(padded_row[0]),
                word=padded_row[1],  # Keep original encoding
                translation=padded_row[2] if len(padded_row) > 2 else '',
                equivalent=padded_row[3] if len(padded_row) > 3 else '',
                example=padded_row[4] if len(padded_row) > 4 else '',
                example_translation=padded_row[5] if len(padded_row) > 5 else '',
                cnt_shown=int(padded_row[6]) if len(padded_row) > 6 and padded_row[6] else 0,
                cnt_corr_answers=int(padded_row[7]) if len(padded_row) > 7 and padded_row[7] else 0,
                level=Levels(int(padded_row[8]))
                if len(padded_row) > 8 and padded_row[8]
                else Levels.LEVEL_0,
                last_shown=parse_timestamp(padded_row[9])
                if len(padded_row) > 9 and padded_row[9]
                else NEVER_SHOWN,
            )
            cards.append(card)
        except Exception as e:
            print(f'Error processing row {row}: {e}')
            continue

    return cards


def update_spreadsheet(worksheet_name, cards, spreadsheet_id: str = None):
    """Update data in Google Sheets in bulk for a specific sheet"""
    # First, we need to get all cards from the sheet
    card_set = read_card_set(worksheet_name, spreadsheet_id)
    if not card_set:
        raise Exception(f'Could not read worksheet {worksheet_name}')

    all_cards = card_set.cards

    # Create a map of card IDs to their updated versions
    card_updates = {card.id: card for card in cards}

    # Update the all_cards list with the modified cards
    for i, card in enumerate(all_cards):
        if card.id in card_updates:
            # Only update the dynamic fields (statistics)
            updated_card = card_updates[card.id]
            all_cards[i].cnt_shown = updated_card.cnt_shown
            all_cards[i].cnt_corr_answers = updated_card.cnt_corr_answers
            all_cards[i].level = updated_card.level
            all_cards[i].last_shown = updated_card.last_shown

    # Now proceed with updating only the dynamic columns of the sheet
    worksheet = get_worksheet(worksheet_name, spreadsheet_id)
    if not worksheet:
        raise Exception(f'Could not access worksheet {worksheet_name}')

    # Prepare the updates for only the dynamic columns
    # Column indices: cnt_shown=6, cnt_corr_answers=7, level=8, last_shown=9
    dynamic_columns = [6, 7, 8, 9]  # 0-based indices for the dynamic columns

    # Create cell updates only for the dynamic columns
    cell_updates = []
    for i, card in enumerate(all_cards):
        # Only create updates for the dynamic columns (statistics)
        # Format the datetime for last_shown
        last_shown_formatted = format_timestamp(card.last_shown)
        values = [card.cnt_shown, card.cnt_corr_answers, card.level.value, last_shown_formatted]

        for col_idx, value in zip(dynamic_columns, values, strict=False):
            cell_updates.append(
                {
                    'range': f'{chr(65 + col_idx)}{i + 2}',  # e.g., G2, H2, I2, J2
                    'values': [[value]],
                }
            )

    # Execute the batch update if there are changes
    if cell_updates:
        result = worksheet.batch_update(cell_updates)
        return result

    return 'No updates to make'
