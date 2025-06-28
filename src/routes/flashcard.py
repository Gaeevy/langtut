"""
Flashcard routes for the Language Learning Flashcard App.

Handles the core flashcard learning functionality.
"""

import json
import logging

from flask import Blueprint, redirect, render_template, request, session, url_for

from src.config import MAX_CARDS_PER_SESSION
from src.gsheet import read_all_card_sets, read_card_set, update_spreadsheet
from src.models import Card
from src.session_manager import SessionKeys as sk
from src.session_manager import SessionManager as sm
from src.user_manager import get_user_spreadsheet_id, is_authenticated
from src.utils import format_timestamp, get_timestamp

# Create logger
logger = logging.getLogger(__name__)

# Create blueprint
flashcard_bp = Blueprint('flashcard', __name__)


class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle datetime and Level objects."""

    def default(self, obj):
        if hasattr(obj, 'isoformat'):
            return obj.isoformat()
        return super().default(obj)


@flashcard_bp.route('/')
def index():
    """Homepage - shows login or flashcard selection."""
    logger.info('=== INDEX ROUTE ===')
    logger.info(f'Request method: {request.method}')
    logger.info(f'Remote addr: {request.remote_addr}')
    logger.info(f'User agent: {request.headers.get("User-Agent", "Unknown")}')

    # Check if session is working
    if not sm.has(sk.TEST_SESSION):
        sm.set(sk.TEST_SESSION, 'Session is working')

    # Check authentication status using SessionManager
    user_is_authenticated = is_authenticated()
    user_spreadsheet_id = get_user_spreadsheet_id(session)

    logger.info(f'Authentication status: {user_is_authenticated}')
    logger.info(f'User spreadsheet ID: {user_spreadsheet_id}')

    # If not authenticated, show login screen
    if not user_is_authenticated:
        logger.info('User not authenticated, showing login screen')
        return render_template('login.html')

    # If no spreadsheet set, show setup screen
    if not user_spreadsheet_id:
        logger.info('No spreadsheet configured, showing setup screen')
        return render_template('setup.html', is_authenticated=user_is_authenticated)

    # Normal app flow with user's spreadsheet
    try:
        card_sets = read_all_card_sets(user_spreadsheet_id)
        logger.info(f'Found {len(card_sets)} card sets in spreadsheet {user_spreadsheet_id}')
        for card_set in card_sets:
            logger.info(f'  - {card_set.name}: {card_set.card_count} cards')
    except Exception as e:
        logger.error(f'Error reading card sets from spreadsheet {user_spreadsheet_id}: {e}')
        card_sets = []

    return render_template(
        'index.html',
        is_authenticated=user_is_authenticated,
        tabs=card_sets,
        user_spreadsheet_id=user_spreadsheet_id,
    )


@flashcard_bp.route('/start/<tab_name>', methods=['POST'])
def start_learning(tab_name: str):
    """Start a learning session with cards from the specified tab."""
    logger.info('=== START LEARNING ROUTE ===')
    logger.info(f'Tab name: {tab_name}')
    logger.info(f'Request method: {request.method}')
    logger.info(f'Remote addr: {request.remote_addr}')

    # Get user's active spreadsheet
    user_spreadsheet_id = get_user_spreadsheet_id(session)
    logger.info(f'User spreadsheet ID: {user_spreadsheet_id}')

    try:
        # Read cards from the specified tab
        card_set = read_card_set(worksheet_name=tab_name, spreadsheet_id=user_spreadsheet_id)
        cards = card_set.get_cards_to_review(limit=MAX_CARDS_PER_SESSION, ignore_unshown=False)

        logger.info(f'Loaded {len(cards)} cards from tab "{tab_name}" for review')
        logger.info(f'Max cards per session: {MAX_CARDS_PER_SESSION}')

        # Log card details
        for i, card in enumerate(cards[:3]):  # Log first 3 cards
            logger.info(
                f'  Card {i + 1}: {card.word} -> {card.translation} (Level {card.level.value})'
            )
        if len(cards) > 3:
            logger.info(f'  ... and {len(cards) - 3} more cards')

        # Store cards in session (converted to dict for JSON serialization)
        # We need to format datetime objects to strings for JSON serialization
        cards_data = []
        for card in cards:
            card_dict = card.model_dump()
            card_dict['last_shown'] = format_timestamp(card.last_shown)
            cards_data.append(card_dict)

        session['cards'] = cards_data
        session['current_index'] = 0
        session['answers'] = []
        session['incorrect_cards'] = []  # Track indices of incorrectly answered cards
        session['reviewing_incorrect'] = (
            False  # Flag to indicate if we're reviewing incorrect cards
        )
        session['active_tab'] = tab_name
        session['original_card_count'] = len(cards)  # Store total card count for reference

        # Cache the sheet GID to avoid repeated API calls
        session['sheet_gid'] = card_set.gid
        logger.info(f'Cached sheet GID in session: {card_set.gid}')

        logger.info(f'Session initialized: {len(cards)} cards, starting at index 0')
        logger.info(f'Active tab set to: {tab_name}')

    except Exception as e:
        logger.error(f'Error starting learning session for tab "{tab_name}": {e}')
        return redirect(url_for('flashcard.index'))

    # Redirect to the first card
    return redirect(url_for('flashcard.show_card'))


@flashcard_bp.route('/card')
def show_card():
    """Display the current flashcard."""
    logger.info('=== SHOW CARD ROUTE ===')

    if 'cards' not in session or 'current_index' not in session:
        logger.warning('Cards or current_index not in session, redirecting to index')
        return redirect(url_for('flashcard.index'))

    cards = session['cards']
    index = session['current_index']
    reviewing = session.get('reviewing_incorrect', False)

    logger.info(f'Current index: {index}, Total cards: {len(cards)}, Reviewing: {reviewing}')

    # Check if we've gone through all the initial cards
    if index >= len(cards) and not reviewing:
        # If we have incorrect cards, start reviewing them
        if session.get('incorrect_cards', []):
            session['reviewing_incorrect'] = True
            session['current_index'] = 0
            logger.info(
                f'Starting review mode with {len(session["incorrect_cards"])} incorrect cards'
            )
            return redirect(url_for('flashcard.show_card'))
        else:
            # All cards correct, go to results
            logger.info('All cards completed, redirecting to results')
            return redirect(url_for('flashcard.show_results'))

    # If we're reviewing and reached the end of incorrect cards, go to results
    if reviewing and index >= len(session['incorrect_cards']):
        logger.info('Review completed, redirecting to results')
        return redirect(url_for('flashcard.show_results'))

    # Get the current card (either from original list or from incorrect cards)
    if reviewing:
        # Get the incorrect card index from the stored list
        incorrect_idx = session['incorrect_cards'][index]
        current_card = cards[incorrect_idx]
        # Add a flag to indicate this is a review card
        current_card['is_review'] = True
        logger.info(
            f'Showing review card {index + 1}/{len(session["incorrect_cards"])}: {current_card["word"]} (original index {incorrect_idx})'
        )
    else:
        current_card = cards[index]
        current_card['is_review'] = False
        logger.info(
            f'Showing card {index + 1}/{len(cards)}: {current_card["word"]} -> {current_card["translation"]}'
        )

    user_spreadsheet_id = get_user_spreadsheet_id(session)
    active_tab = session.get('active_tab', 'Sheet1')
    # Use cached sheet GID instead of making API call
    sheet_gid = session.get('sheet_gid')

    logger.info(
        f'Template context: spreadsheet_id={user_spreadsheet_id}, tab={active_tab}, sheet_gid={sheet_gid} (cached)'
    )

    return render_template(
        'card.html',
        card=current_card,
        index=index,
        total=len(session['incorrect_cards']) if reviewing else len(cards),
        reviewing=reviewing,
        user_spreadsheet_id=user_spreadsheet_id,
        active_tab=active_tab,
        sheet_gid=sheet_gid,
    )


@flashcard_bp.route('/answer', methods=['POST'])
def process_answer():
    """Process the user's answer to a flashcard."""
    logger.info('=== PROCESS ANSWER ROUTE ===')

    if 'cards' not in session or 'current_index' not in session:
        logger.warning('Cards or current_index not in session, redirecting to index')
        return redirect(url_for('flashcard.index'))

    # Get user's answer
    user_answer = request.form.get('user_answer', '').strip().lower()
    logger.info(f'User submitted answer: "{user_answer}"')

    # Check if we're in review mode
    reviewing = session.get('reviewing_incorrect', False)

    # Get current card
    cards = session['cards']
    index = session['current_index']

    if reviewing:
        # Get the original index of the card being reviewed
        original_index = session['incorrect_cards'][index]
        current_card = cards[original_index]
        logger.info(
            f'Processing review answer for card {index + 1}/{len(session["incorrect_cards"])} (original index {original_index})'
        )
    else:
        current_card = cards[index]
        logger.info(f'Processing initial answer for card {index + 1}/{len(cards)}')

    # Check answer (simple exact match for now)
    correct_answers = [current_card['word'].strip().lower()]  # User types Portuguese word

    # Also check the equivalent field if it exists and is different
    if (
        current_card.get('equivalent')
        and current_card['equivalent'].strip().lower() != correct_answers[0]
    ):
        correct_answers.append(current_card['equivalent'].strip().lower())

    is_correct = user_answer in correct_answers

    # Comprehensive answer validation logging
    logger.info('🔍 Answer validation details:')
    logger.info(f'  Card ID: {current_card["id"]}')
    logger.info(f"  User sees: '{current_card['translation']}' (Russian)")
    logger.info(f"  User typed: '{user_answer}'")
    logger.info(f"  Expected Portuguese word: '{current_card['word']}'")
    logger.info(f'  All correct answers: {correct_answers}')
    logger.info(f'  Is correct: {is_correct}')
    logger.info(f'  Review mode: {reviewing}')

    # Store the answer result
    answer_data = {
        'card_id': current_card['id'],
        'user_answer': user_answer,
        'is_correct': is_correct,
        'card_index': original_index if reviewing else index,
    }

    # Initialize answers list if it doesn't exist
    if 'answers' not in session:
        session['answers'] = []

    session['answers'].append(answer_data)
    logger.info(f'Answer stored. Total answers so far: {len(session["answers"])}')

    # Track incorrect cards for review (only during initial round)
    if not reviewing and not is_correct:
        if 'incorrect_cards' not in session:
            session['incorrect_cards'] = []
        session['incorrect_cards'].append(index)
        logger.info(
            f'Added card to incorrect list. Total incorrect cards: {len(session["incorrect_cards"])}'
        )

    # Update card statistics in background (don't wait for response)
    try:
        user_spreadsheet_id = get_user_spreadsheet_id(session)
        active_tab = session.get('active_tab', 'Sheet1')

        logger.info(
            f'Updating card statistics: spreadsheet={user_spreadsheet_id}, tab={active_tab}'
        )

        # Create Card object from current card data
        card = Card(**current_card)

        # Store original level for comparison
        original_level = card.level.value

        # Update statistics
        card.cnt_shown += 1
        card.last_shown = get_timestamp()

        # Simple level progression: +1 for correct, -1 for incorrect
        if is_correct:
            card.cnt_corr_answers += 1
            # Always advance level for correct answers
            card.level = card.level.next_level()
            logger.info(
                f'✅ Correct answer! Card level advanced from {original_level} to {card.level.value}'
            )
        else:
            # Always decrease level for incorrect answers
            card.level = card.level.previous_level()
            logger.info(
                f'❌ Incorrect answer! Card level decreased from {original_level} to {card.level.value}'
            )

        # Update the session data with the new level
        cards = session['cards']
        if reviewing:
            cards[original_index]['level'] = card.level.value
        else:
            cards[index]['level'] = card.level.value
        session['cards'] = cards
        logger.info('Session card level updated in memory')

        # Store level change information for the feedback page
        session['last_level_change'] = {
            'from': original_level,
            'to': card.level.value,
            'is_correct': is_correct,
        }

        # Update spreadsheet
        logger.info('Updating spreadsheet with new statistics...')
        update_spreadsheet(active_tab, [card], spreadsheet_id=user_spreadsheet_id)
        logger.info('Spreadsheet update completed successfully')

    except Exception as e:
        logger.error(f'Error updating card statistics: {e}', exc_info=True)
        # Continue without showing error to user

    # Redirect to feedback page
    feedback_url = url_for('flashcard.show_feedback', correct='yes' if is_correct else 'no')
    logger.info(f'Redirecting to feedback page: {feedback_url}')
    return redirect(feedback_url)


@flashcard_bp.route('/feedback/<correct>')
def show_feedback(correct: str):
    """Show feedback after answering a card."""
    if 'cards' not in session or 'current_index' not in session:
        return redirect(url_for('flashcard.index'))

    cards = session['cards']
    index = session['current_index']
    reviewing = session.get('reviewing_incorrect', False)

    # Get the current card
    if reviewing:
        incorrect_idx = session['incorrect_cards'][index]
        current_card = cards[incorrect_idx]
    else:
        current_card = cards[index]

    # Get the last answer
    last_answer = session.get('answers', [])[-1] if session.get('answers') else None

    # Get level change information
    level_change = session.pop('last_level_change', None)

    return render_template(
        'feedback.html',
        card=current_card,
        correct=(correct == 'yes'),
        user_answer=last_answer['user_answer'] if last_answer else '',
        reviewing=reviewing,
        card_index=index,
        level_change=level_change,
        user_spreadsheet_id=get_user_spreadsheet_id(session),
        active_tab=session.get('active_tab', 'Sheet1'),
        # Use cached sheet GID instead of making API call
        sheet_gid=session.get('sheet_gid'),
    )


@flashcard_bp.route('/rate-difficulty/<int:card_index>/<difficulty>')
def rate_difficulty(card_index: int, difficulty: str):
    """Rate the difficulty of a card (for future spaced repetition)."""
    # For now, just acknowledge the rating and continue
    # In the future, this could affect the spaced repetition algorithm
    logger.info(f'Card {card_index} rated as {difficulty}')
    return redirect(url_for('flashcard.next_card'))


@flashcard_bp.route('/next')
def next_card():
    """Move to the next card in the session."""
    if 'current_index' not in session:
        return redirect(url_for('flashcard.index'))

    session['current_index'] += 1
    return redirect(url_for('flashcard.show_card'))


@flashcard_bp.route('/results')
def show_results():
    """Display the results of the learning session."""
    if 'answers' not in session:
        return redirect(url_for('flashcard.index'))

    answers = session.get('answers', [])
    original_count = session.get('original_card_count', len(answers))

    # Calculate statistics
    total_answered = len(answers)
    correct_answers = sum(1 for answer in answers if answer['is_correct'])

    # Calculate review statistics
    incorrect_cards = session.get('incorrect_cards', [])
    review_count = len([a for a in answers if a.get('card_index', 0) in incorrect_cards])
    first_attempt_count = total_answered - review_count

    # Calculate accuracy percentage
    accuracy = (correct_answers / total_answered * 100) if total_answered > 0 else 0

    return render_template(
        'results.html',
        total=total_answered,
        correct=correct_answers,
        percentage=int(accuracy),
        review_count=review_count,
        first_attempt_count=first_attempt_count,
        answers=answers,
        original_count=original_count,
        is_authenticated=is_authenticated(),
        updated=False,  # Will be True when spreadsheet updates are working
    )


@flashcard_bp.route('/end-session')
def end_session_early():
    """End the current learning session early."""
    # Calculate partial results
    answers = session.get('answers', [])
    original_count = session.get('original_card_count', len(answers))

    total_answered = len(answers)
    correct_answers = sum(1 for answer in answers if answer['is_correct'])

    # Calculate review statistics
    incorrect_cards = session.get('incorrect_cards', [])
    review_count = len([a for a in answers if a.get('card_index', 0) in incorrect_cards])
    first_attempt_count = total_answered - review_count

    accuracy = (correct_answers / total_answered * 100) if total_answered > 0 else 0

    # Clear session data
    for key in [
        'cards',
        'current_index',
        'answers',
        'incorrect_cards',
        'reviewing_incorrect',
        'active_tab',
        'original_card_count',
        'sheet_gid',
    ]:
        session.pop(key, None)

    return render_template(
        'results.html',
        total=total_answered,
        correct=correct_answers,
        percentage=int(accuracy),
        review_count=review_count,
        first_attempt_count=first_attempt_count,
        answers=answers,
        original_count=original_count,
        ended_early=True,
        cards_remaining=original_count - total_answered,
        is_authenticated=is_authenticated(),
        updated=False,  # Will be True when spreadsheet updates are working
    )
