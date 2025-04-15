import gspread
from src.auth import get_credentials
from src.models import Card, Tab, NEVER_SHOWN
from src.config import SPREADSHEET_ID
from src.utils import format_timestamp, parse_timestamp


def get_spreadsheet():
    """Connect to Google Sheets using gspread and return the spreadsheet"""
    creds = get_credentials()

    try:
        # Authenticated access
        gc = gspread.authorize(creds)
        spreadsheet = gc.open_by_key(SPREADSHEET_ID)
        return spreadsheet, True  # Second value indicates if write is possible
    except Exception as e:
        print(f"Error accessing spreadsheet with auth using creds {creds}: {e}")
        return None, False


def get_worksheet(sheet_name):
    """Get a specific worksheet by name"""
    spreadsheet, can_write = get_spreadsheet()
    if not spreadsheet:
        return None, False

    try:
        worksheet = spreadsheet.worksheet(sheet_name)
        return worksheet, can_write
    except Exception as e:
        print(f"Error accessing worksheet {sheet_name}: {e}")
        return None, False


def get_all_tabs():
    """Get all tabs (worksheets) from the spreadsheet"""
    spreadsheet, _ = get_spreadsheet()
    if not spreadsheet:
        return []

    try:
        # Get all worksheets
        worksheets = spreadsheet.worksheets()
        tabs = []

        for worksheet in worksheets:
            tab_name = worksheet.title
            # Read cards for each tab
            cards = read_worksheet_data(worksheet)

            # Create Tab object
            tab = Tab(name=tab_name, cards=cards)
            tabs.append(tab)

        return tabs
    except Exception as e:
        print(f"Error getting all tabs: {e}")
        return []


def read_worksheet_data(worksheet):
    """Read data from a specific worksheet"""
    try:
        # Get all values from the worksheet
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
                    translation=padded_row[2] if len(padded_row) > 2 else "",
                    equivalent=padded_row[3] if len(padded_row) > 3 else "",
                    example=padded_row[4] if len(padded_row) > 4 else "",
                    example_translation=padded_row[5] if len(padded_row) > 5 else "",
                    cnt_shown=int(padded_row[6]) if len(padded_row) > 6 and padded_row[6] else 0,
                    cnt_corr_answers=int(padded_row[7]) if len(padded_row) > 7 and padded_row[
                        7] else 0,
                    level=int(padded_row[8]) if len(padded_row) > 8 and padded_row[8] else 0,
                    last_shown=parse_timestamp(padded_row[9]) if len(padded_row) > 9 and padded_row[9] else NEVER_SHOWN
                )
                cards.append(card)
            except Exception as e:
                print(f"Error processing row {row}: {e}")
                continue

        return cards
    except Exception as e:
        print(f"Error reading worksheet data: {e}")
        return []


def read_spreadsheet(sheet_name=None):
    """Read data from Google Sheets, either from a specific sheet or all sheets"""
    if sheet_name:
        # Read specific sheet
        worksheet, _ = get_worksheet(sheet_name)
        if not worksheet:
            return []

        return read_worksheet_data(worksheet)
    else:
        # Read all sheets
        return get_all_tabs()


def update_spreadsheet(sheet_name, cards):
    """Update data in Google Sheets in bulk for a specific sheet"""
    # First, we need to get all cards from the sheet
    all_cards = read_spreadsheet(sheet_name=sheet_name)
    if not all_cards:
        raise Exception(f"Could not read worksheet {sheet_name}")

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
    worksheet, can_write = get_worksheet(sheet_name)
    if not worksheet:
        raise Exception(f"Could not access worksheet {sheet_name}")

    if not can_write:
        raise Exception("Authentication required to update spreadsheet")

    # Prepare the updates for only the dynamic columns
    # Column indices: cnt_shown=6, cnt_corr_answers=7, level=8, last_shown=9
    dynamic_columns = [6, 7, 8, 9]  # 0-based indices for the dynamic columns

    # Create cell updates only for the dynamic columns
    cell_updates = []
    for i, card in enumerate(all_cards):
        # Only create updates for the dynamic columns (statistics)
        # Format the datetime for last_shown
        last_shown_formatted = format_timestamp(card.last_shown)
        values = [card.cnt_shown, card.cnt_corr_answers, card.level, last_shown_formatted]

        for col_idx, value in zip(dynamic_columns, values):
            cell_updates.append({
                'range': f'{chr(65 + col_idx)}{i + 2}',  # e.g., G2, H2, I2, J2
                'values': [[value]]
            })

    # Execute the batch update if there are changes
    if cell_updates:
        result = worksheet.batch_update(cell_updates)
        return result

    return "No updates to make"