"""
Flashcard routes for the Language Learning Flashcard App.

Handles the core flashcard learning functionality.
"""

import json
from datetime import datetime

from flask import Blueprint, redirect, render_template, request, session, url_for

from src.config import MAX_CARDS_PER_SESSION
from src.gsheet import read_all_card_sets, read_card_set, update_spreadsheet
from src.models import Card
from src.user_manager import get_user_spreadsheet_id
from src.utils import format_timestamp, get_timestamp

# Create blueprint
flashcard_bp = Blueprint('flashcard', __name__)


# Custom JSON encoder to handle datetime objects
class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return format_timestamp(obj)
        return super().default(obj)


@flashcard_bp.route('/')
def index():
    """Homepage - shows login or flashcard selection."""
    # Print debug information
    print('Index route accessed')
    print(f'Session data: {session}')

    # Check if session is working
    if 'test' not in session:
        session['test'] = 'Session is working'

    # Check authentication status
    is_authenticated = 'credentials' in session
    print(f'Authentication status: {is_authenticated}')

    # If not authenticated, show login screen
    if not is_authenticated:
        return render_template('login.html')

    # Get the user's active spreadsheet ID
    user_spreadsheet_id = get_user_spreadsheet_id(session)

    # If no spreadsheet set, show setup screen
    if not user_spreadsheet_id:
        return render_template('setup.html', is_authenticated=is_authenticated)

    # Normal app flow with user's spreadsheet
    card_sets = read_all_card_sets(user_spreadsheet_id)

    return render_template(
        'index.html',
        is_authenticated=is_authenticated,
        tabs=card_sets,
        user_spreadsheet_id=user_spreadsheet_id,
    )


@flashcard_bp.route('/start/<tab_name>', methods=['POST'])
def start_learning(tab_name: str):
    """Start a learning session with cards from the specified tab."""
    # Get user's active spreadsheet
    user_spreadsheet_id = get_user_spreadsheet_id(session)

    # Read cards from the specified tab
    card_set = read_card_set(worksheet_name=tab_name, spreadsheet_id=user_spreadsheet_id)
    cards = card_set.get_cards_to_review(limit=MAX_CARDS_PER_SESSION, ignore_unshown=False)

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
    session['reviewing_incorrect'] = False  # Flag to indicate if we're reviewing incorrect cards
    session['active_tab'] = tab_name
    session['original_card_count'] = len(cards)  # Store total card count for reference

    # Redirect to the first card
    return redirect(url_for('flashcard.show_card'))


@flashcard_bp.route('/card')
def show_card():
    """Display the current flashcard."""
    if 'cards' not in session or 'current_index' not in session:
        return redirect(url_for('flashcard.index'))

    cards = session['cards']
    index = session['current_index']
    reviewing = session.get('reviewing_incorrect', False)

    # Check if we've gone through all the initial cards
    if index >= len(cards) and not reviewing:
        # If we have incorrect cards, start reviewing them
        if session.get('incorrect_cards', []):
            session['reviewing_incorrect'] = True
            session['current_index'] = 0
            return redirect(url_for('flashcard.show_card'))
        else:
            # All cards correct, go to results
            return redirect(url_for('flashcard.show_results'))

    # If we're reviewing and reached the end of incorrect cards, go to results
    if reviewing and index >= len(session['incorrect_cards']):
        return redirect(url_for('flashcard.show_results'))

    # Get the current card (either from original list or from incorrect cards)
    if reviewing:
        # Get the incorrect card index from the stored list
        incorrect_idx = session['incorrect_cards'][index]
        current_card = cards[incorrect_idx]
        # Add a flag to indicate this is a review card
        current_card['is_review'] = True
    else:
        current_card = cards[index]
        current_card['is_review'] = False

    return render_template(
        'card.html',
        card=current_card,
        index=index,
        total=len(session['incorrect_cards']) if reviewing else len(cards),
        reviewing=reviewing,
    )


@flashcard_bp.route('/answer', methods=['POST'])
def process_answer():
    """Process the user's answer to a flashcard."""
    if 'cards' not in session or 'current_index' not in session:
        return redirect(url_for('flashcard.index'))

    # Get user's answer
    user_answer = request.form.get('answer', '').strip().lower()

    # Check if we're in review mode
    reviewing = session.get('reviewing_incorrect', False)

    # Get current card
    cards = session['cards']
    index = session['current_index']

    if reviewing:
        # Get the original index of the card being reviewed
        original_index = session['incorrect_cards'][index]
        current_card = cards[original_index]
    else:
        current_card = cards[index]

    # Check answer (simple exact match for now)
    correct_answers = [current_card['translation'].strip().lower()]

    # Also check the equivalent field if it exists and is different
    if (
        current_card.get('equivalent')
        and current_card['equivalent'].strip().lower() != correct_answers[0]
    ):
        correct_answers.append(current_card['equivalent'].strip().lower())

    is_correct = user_answer in correct_answers

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

    # Track incorrect cards for review (only during initial round)
    if not reviewing and not is_correct:
        if 'incorrect_cards' not in session:
            session['incorrect_cards'] = []
        session['incorrect_cards'].append(index)

    # Update card statistics in background (don't wait for response)
    try:
        user_spreadsheet_id = get_user_spreadsheet_id(session)
        active_tab = session.get('active_tab', 'Sheet1')

        # Create Card object from current card data
        card = Card(**current_card)

        # Update statistics
        card.cnt_shown += 1
        card.last_shown = get_timestamp()
        if is_correct:
            card.cnt_corr_answers += 1

        # Update spreadsheet
        update_spreadsheet(card, worksheet_name=active_tab, spreadsheet_id=user_spreadsheet_id)

    except Exception as e:
        print(f'Error updating card statistics: {e}')
        # Continue without showing error to user

    # Redirect to feedback page
    return redirect(url_for('flashcard.show_feedback', correct='yes' if is_correct else 'no'))


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

    return render_template(
        'feedback.html',
        card=current_card,
        correct=(correct == 'yes'),
        user_answer=last_answer['user_answer'] if last_answer else '',
        reviewing=reviewing,
    )


@flashcard_bp.route('/rate-difficulty/<int:card_index>/<difficulty>')
def rate_difficulty(card_index: int, difficulty: str):
    """Rate the difficulty of a card (for future spaced repetition)."""
    # For now, just acknowledge the rating and continue
    # In the future, this could affect the spaced repetition algorithm
    print(f'Card {card_index} rated as {difficulty}')
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

    # Calculate accuracy percentage
    accuracy = (correct_answers / total_answered * 100) if total_answered > 0 else 0

    return render_template(
        'results.html',
        total_answered=total_answered,
        correct_answers=correct_answers,
        accuracy=accuracy,
        answers=answers,
        original_count=original_count,
    )


@flashcard_bp.route('/end-session')
def end_session_early():
    """End the current learning session early."""
    # Calculate partial results
    answers = session.get('answers', [])
    original_count = session.get('original_card_count', len(answers))

    total_answered = len(answers)
    correct_answers = sum(1 for answer in answers if answer['is_correct'])
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
    ]:
        session.pop(key, None)

    return render_template(
        'results.html',
        total_answered=total_answered,
        correct_answers=correct_answers,
        accuracy=accuracy,
        answers=answers,
        original_count=original_count,
        ended_early=True,
    )
