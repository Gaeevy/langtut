"""Service layer for listening cards endpoint."""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from typing import Any

from app.gsheet import read_card_set

logger = logging.getLogger(__name__)


@dataclass
class ListeningCardsResult:
    """Transport-agnostic result for listening cards lookup."""

    payload: dict[str, Any]
    status_code: int = 200


class ListeningCardsService:
    """Encapsulates listening cards retrieval and shaping logic."""

    def get_for_listening(self, user: Any, tab_name: str) -> ListeningCardsResult:
        """Build listening cards payload for a tab."""
        logger.info(f"Loading cards for listening mode: {tab_name}")
        try:
            active_spreadsheet = user.get_active_spreadsheet()
            if not active_spreadsheet:
                logger.warning("No spreadsheet configured for user")
                return ListeningCardsResult(
                    {"success": False, "error": "No spreadsheet configured"},
                    status_code=400,
                )

            user_spreadsheet_id = active_spreadsheet.spreadsheet_id
            logger.info(f"Using spreadsheet: {user_spreadsheet_id}")

            card_set = read_card_set(worksheet_name=tab_name, spreadsheet_id=user_spreadsheet_id)
            if not card_set:
                logger.error(
                    f'Card set "{tab_name}" not found in spreadsheet {user_spreadsheet_id}'
                )
                return ListeningCardsResult(
                    {"success": False, "error": f'Card set "{tab_name}" not found'},
                    status_code=404,
                )

            if not card_set.cards:
                logger.warning(f'Card set "{tab_name}" is empty')
                return ListeningCardsResult(
                    {"success": False, "error": f'Card set "{tab_name}" is empty'},
                    status_code=400,
                )

            cards_for_listening: list[dict[str, Any]] = []
            for card in card_set.cards:
                if card.word and card.word.strip() and card.example and card.example.strip():
                    cards_for_listening.append(
                        {"id": card.id, "word": card.word.strip(), "example": card.example.strip()}
                    )
                else:
                    logger.debug(f"Skipping card {card.id}: missing word or example")

            if not cards_for_listening:
                logger.warning(f'No valid cards for listening in "{tab_name}"')
                return ListeningCardsResult(
                    {
                        "success": False,
                        "error": f'No cards with audio content found in "{tab_name}"',
                    },
                    status_code=400,
                )

            random.shuffle(cards_for_listening)
            return ListeningCardsResult(
                {
                    "success": True,
                    "tab_name": card_set.name,
                    "sheet_gid": card_set.gid,
                    "cards": cards_for_listening,
                    "total_count": len(cards_for_listening),
                    "original_count": len(card_set.cards),
                }
            )
        except Exception as e:
            logger.error(f"Error fetching cards for listening: {e}", exc_info=True)
            return ListeningCardsResult(
                {"success": False, "error": f"Failed to fetch cards: {e!s}"},
                status_code=500,
            )
