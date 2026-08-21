"""
Google Sheets integration for the Language Learning Flashcard App.

This module handles reading and writing data to Google Sheets,
including card sets and user statistics.
"""

import logging
import re
from collections.abc import Callable

import gspread
from google.oauth2.credentials import Credentials
from gspread.exceptions import APIError
from gspread.spreadsheet import Spreadsheet
from gspread.worksheet import Worksheet

from app.config import config
from app.models import NEVER_SHOWN, Card, CardSet, Levels
from app.services.auth_manager import auth_manager
from app.utils import format_timestamp, parse_timestamp

# Create logger
logger = logging.getLogger(__name__)


_SPREADSHEET_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{20,}$")


class _GoogleCredentialsUnavailableError(RuntimeError):
    """Raised when a Sheets operation cannot obtain usable Google credentials."""


def _is_authentication_error(error: APIError) -> bool:
    """Return whether Google rejected the access token for this request."""
    response_status = getattr(error.response, "status_code", None)
    return response_status == 401 or error.code == 401


def _run_with_auth_retry[ResultT](
    operation: Callable[[Credentials], ResultT],
    description: str,
) -> ResultT:
    """Run a Sheets operation, rebuilding it once after a Google authentication failure."""
    for attempt in range(2):
        credentials = (
            auth_manager.get_credentials(force_refresh=True)
            if attempt
            else auth_manager.get_credentials()
        )
        if not credentials:
            raise _GoogleCredentialsUnavailableError(
                f"No Google credentials available for {description}"
            )

        try:
            return operation(credentials)
        except APIError as error:
            if attempt == 0 and _is_authentication_error(error):
                logger.warning(
                    f"Google authentication failed during {description}; "
                    "refreshing and retrying once"
                )
                continue
            raise

    raise RuntimeError(f"Google Sheets retry exhausted for {description}")


def _open_spreadsheet(credentials: Credentials, spreadsheet_id: str) -> Spreadsheet:
    """Open a spreadsheet using the credentials supplied for this attempt."""
    return gspread.authorize(credentials).open_by_key(spreadsheet_id)


def _open_worksheet(
    credentials: Credentials,
    worksheet_name: str,
    spreadsheet_id: str,
) -> Worksheet:
    """Open a worksheet while rebuilding all credential-bound objects per attempt."""
    spreadsheet = _open_spreadsheet(credentials, spreadsheet_id)
    return spreadsheet.worksheet(worksheet_name)


def _batch_update_worksheet(
    worksheet_name: str,
    spreadsheet_id: str,
    cell_updates: list[dict[str, object]],
) -> object:
    """Apply prepared cell updates through the shared authentication retry boundary."""

    def update(credentials: Credentials) -> object:
        worksheet = _open_worksheet(credentials, worksheet_name, spreadsheet_id)
        return worksheet.batch_update(cell_updates)

    return _run_with_auth_retry(update, f"updating worksheet {worksheet_name}")


def extract_spreadsheet_id(url_or_id: str) -> str:
    """Extract spreadsheet ID from Google Sheets URL or return a bare ID if valid."""
    trimmed = (url_or_id or "").strip()
    if not trimmed:
        return ""

    if "/" not in trimmed:
        return trimmed

    patterns = [
        r"/spreadsheets/d/([a-zA-Z0-9-_]+)",
        r"[?&]id=([a-zA-Z0-9-_]+)",
        r"/d/([a-zA-Z0-9-_]+)/edit",
    ]
    for pattern in patterns:
        match = re.search(pattern, trimmed)
        if match:
            return match.group(1)

    # Do not treat an arbitrary URL string as an ID (avoids broken /d/<full-url> links).
    if _SPREADSHEET_ID_RE.fullmatch(trimmed):
        return trimmed
    logger.debug("Could not extract spreadsheet id from input")
    return ""


def spreadsheet_editor_url(spreadsheet_id: str) -> str:
    """Return the Google Sheets editor URL for a spreadsheet ID."""
    return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"


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

    try:
        spreadsheet = _run_with_auth_retry(
            lambda credentials: _open_spreadsheet(credentials, spreadsheet_id),
            f"validating spreadsheet {spreadsheet_id}",
        )
    except _GoogleCredentialsUnavailableError as error:
        raise ValueError("Not authenticated with Google") from error

    logger.info(f"✅ Spreadsheet access validated: {spreadsheet.title}")
    return spreadsheet.title


def get_spreadsheet(spreadsheet_id: str = None) -> Spreadsheet | None:
    """Get spreadsheet by ID, falls back to default if not provided"""
    sheet_id = spreadsheet_id or config.spreadsheet_id

    try:
        return _run_with_auth_retry(
            lambda credentials: _open_spreadsheet(credentials, sheet_id),
            f"opening spreadsheet {sheet_id}",
        )
    except _GoogleCredentialsUnavailableError as error:
        logger.warning(str(error))
    except gspread.SpreadsheetNotFound:
        logger.warning(f"Spreadsheet not found or inaccessible: {sheet_id}")
    except APIError as error:
        logger.error(
            f"Google Sheets API error accessing spreadsheet {sheet_id}: {error}", exc_info=True
        )
    except Exception as error:
        logger.error(f"Error accessing spreadsheet {sheet_id}: {error}", exc_info=True)
    return None


def get_worksheet(worksheet_name, spreadsheet_id: str = None) -> Worksheet | None:
    """Get a specific worksheet by name"""
    sheet_id = spreadsheet_id or config.spreadsheet_id
    try:
        return _run_with_auth_retry(
            lambda credentials: _open_worksheet(credentials, worksheet_name, sheet_id),
            f"opening worksheet {worksheet_name}",
        )
    except _GoogleCredentialsUnavailableError as error:
        logger.warning(str(error))
    except (gspread.SpreadsheetNotFound, gspread.WorksheetNotFound):
        logger.warning(f"Worksheet not found or inaccessible: {worksheet_name}")
    except APIError as error:
        logger.error(
            f"Google Sheets API error accessing worksheet {worksheet_name}: {error}",
            exc_info=True,
        )
    except Exception as error:
        logger.error(f"Error accessing worksheet {worksheet_name}: {error}", exc_info=True)
    return None


def read_all_card_sets(spreadsheet_id: str = None) -> list[CardSet]:
    """Get all card sets from the spreadsheet"""
    sheet_id = spreadsheet_id or config.spreadsheet_id

    def read(credentials: Credentials) -> list[CardSet]:
        spreadsheet = _open_spreadsheet(credentials, sheet_id)
        return [
            CardSet(
                name=worksheet.title,
                gid=worksheet.id,
                cards=read_cards_from_worksheet(worksheet),
            )
            for worksheet in spreadsheet.worksheets()
        ]

    try:
        return _run_with_auth_retry(read, f"reading card sets from spreadsheet {sheet_id}")
    except _GoogleCredentialsUnavailableError as error:
        logger.warning(str(error))
    except (gspread.SpreadsheetNotFound, APIError) as error:
        logger.error(
            f"Could not read card sets from spreadsheet {sheet_id}: {error}", exc_info=True
        )
    return []


def read_card_set(worksheet_name, spreadsheet_id: str = None) -> CardSet | None:
    sheet_id = spreadsheet_id or config.spreadsheet_id

    def read(credentials: Credentials) -> CardSet:
        worksheet = _open_worksheet(credentials, worksheet_name, sheet_id)
        return CardSet(
            name=worksheet.title,
            gid=worksheet.id,
            cards=read_cards_from_worksheet(worksheet),
        )

    try:
        return _run_with_auth_retry(read, f"reading worksheet {worksheet_name}")
    except _GoogleCredentialsUnavailableError as error:
        logger.warning(str(error))
    except (gspread.SpreadsheetNotFound, gspread.WorksheetNotFound):
        logger.warning(f"Worksheet not found or inaccessible: {worksheet_name}")
    except APIError as error:
        logger.error(
            f"Google Sheets API error reading worksheet {worksheet_name}: {error}", exc_info=True
        )
    return None


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
            logger.warning(f"Error processing worksheet row {row}: {e}")
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
            sheet_id = spreadsheet_id or config.spreadsheet_id
            result = _batch_update_worksheet(worksheet_name, sheet_id, cell_updates)
            logger.info(
                f"✅ Batch update completed successfully. Updated {len(cell_updates)} cells"
            )
            return result

        logger.info("No updates to make")
        return "No updates to make"

    except Exception as e:
        logger.error(f"❌ Error updating spreadsheet: {e}", exc_info=True)
        raise
