"""
Google Sheets integration for the Language Learning Flashcard App.

This module handles reading and writing data to Google Sheets,
including card sets and user statistics.
"""

import logging
import re

import gspread
from gspread.spreadsheet import Spreadsheet
from gspread.worksheet import Worksheet

from app.config import config
from app.models import NEVER_SHOWN, Card, CardSet, Levels
from app.services.auth_manager import auth_manager
from app.utils import format_timestamp, parse_timestamp

# Create logger
logger = logging.getLogger(__name__)


def extract_spreadsheet_id(url_or_id: str) -> str:
    """Extract spreadsheet ID from Google Sheets URL or return ID if already provided"""
    # If it's already just an ID (no slashes), return as-is
    if "/" not in url_or_id:
        return url_or_id.strip()

    # Extract ID from various Google Sheets URL formats
    patterns = [
        r"/spreadsheets/d/([a-zA-Z0-9-_]+)",  # Standard URL
        r"[?&]id=([a-zA-Z0-9-_]+)",  # Query parameter
        r"/d/([a-zA-Z0-9-_]+)/edit",  # Edit URL
    ]

    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)

    # If no pattern matches, assume it's already an ID
    return url_or_id.strip()


def validate_spreadsheet_access(spreadsheet_id: str) -> str:
    """Validate spreadsheet access and return spreadsheet name.

    Args:
        spreadsheet_id: Google Sheets spreadsheet ID

    Returns:
        Spreadsheet name/title

    Raises:
        gspread.SpreadsheetNotFound: If spreadsheet doesn't exist or no access
        gspread.APIError: If Google Sheets API error occurs
        Exception: For other errors (auth issues, network, etc.)

    Note:
        Structure validation (headers, data) is done later when reading cards.
        This just checks if we can access the spreadsheet and gets its name.
    """
    logger.info(f"Validating spreadsheet access: {spreadsheet_id}")

    creds = auth_manager.get_credentials()
    if not creds:
        raise ValueError("Not authenticated with Google")

    gc = gspread.authorize(creds)
    spreadsheet = gc.open_by_key(spreadsheet_id)

    logger.info(f"✅ Spreadsheet access validated: {spreadsheet.title}")
    return spreadsheet.title


def get_spreadsheet(spreadsheet_id: str = None) -> Spreadsheet | None:
    """Get spreadsheet by ID, falls back to default if not provided"""
    creds = auth_manager.get_credentials()
    if not creds:
        return None

    # Use provided ID or fall back to default
    sheet_id = spreadsheet_id or config.spreadsheet_id

    try:
        gc = gspread.authorize(creds)
        spreadsheet = gc.open_by_key(sheet_id)
        return spreadsheet
    except Exception as e:
        print(f"Error accessing spreadsheet {sheet_id} with auth using creds {creds}: {e}")
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
        print(f"Error accessing worksheet {worksheet_name}: {e}")
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
        padded_row = row + [""] * (10 - len(row)) if len(row) < 10 else row

        try:
            card = Card(
                id=int(padded_row[0]),
                word=padded_row[1],  # Keep original encoding
                translation=padded_row[2] if len(padded_row) > 2 else "",
                equivalent=padded_row[3] if len(padded_row) > 3 else "",
                example=padded_row[4] if len(padded_row) > 4 else "",
                example_translation=padded_row[5] if len(padded_row) > 5 else "",
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
            print(f"Error processing row {row}: {e}")
            continue

    return cards


def update_spreadsheet(worksheet_name, cards, spreadsheet_id: str = None):
    """Update data in Google Sheets in bulk for a specific sheet"""
    logger.info(
        f"Updating spreadsheet: {worksheet_name} ({len(cards)} cards, ID: {spreadsheet_id})"
    )

    # Log card details being updated
    for i, card in enumerate(cards):
        logger.info(
            f"  Card {i + 1}: ID={card.id}, shown={card.cnt_shown}, correct={card.cnt_corr_answers}, level={card.level.value}"
        )

    try:
        # First, we need to get all cards from the sheet
        card_set = read_card_set(worksheet_name, spreadsheet_id)
        if not card_set:
            raise Exception(f"Could not read worksheet {worksheet_name}")

        all_cards = card_set.cards
        logger.info(f"Read {len(all_cards)} cards from worksheet")

        # Create a map of card IDs to their updated versions
        card_updates = {card.id: card for card in cards}
        logger.info(f"Created update map for card IDs: {list(card_updates.keys())}")

        # Update the all_cards list with the modified cards
        updated_count = 0
        for i, card in enumerate(all_cards):
            if card.id in card_updates:
                # Only update the dynamic fields (statistics)
                updated_card = card_updates[card.id]
                all_cards[i].cnt_shown = updated_card.cnt_shown
                all_cards[i].cnt_corr_answers = updated_card.cnt_corr_answers
                all_cards[i].level = updated_card.level
                all_cards[i].last_shown = updated_card.last_shown
                updated_count += 1
                logger.info(
                    f"Updated card {card.id}: shown={updated_card.cnt_shown}, correct={updated_card.cnt_corr_answers}, level={updated_card.level.value}"
                )

        logger.info(f"Updated {updated_count} cards in memory")

        # Now proceed with updating only the dynamic columns of the sheet
        worksheet = get_worksheet(worksheet_name, spreadsheet_id)
        if not worksheet:
            raise Exception(f"Could not access worksheet {worksheet_name}")

        logger.info("Accessing worksheet for batch update...")

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
                        "range": f"{chr(65 + col_idx)}{i + 2}",  # e.g., G2, H2, I2, J2
                        "values": [[value]],
                    }
                )

        logger.info(f"Prepared {len(cell_updates)} cell updates for batch operation")

        # Execute the batch update if there are changes
        if cell_updates:
            logger.info("Executing batch update to Google Sheets...")
            result = worksheet.batch_update(cell_updates)
            logger.info(
                f"✅ Batch update completed successfully. Updated {len(cell_updates)} cells"
            )
            return result

        logger.info("No updates to make")
        return "No updates to make"

    except Exception as e:
        logger.error(f"❌ Error updating spreadsheet: {e}", exc_info=True)
        raise
