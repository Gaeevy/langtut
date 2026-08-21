"""Shared processing and comparison for submitted learning answers."""


def process_answer(answer: str) -> list[str]:
    """Return lowercase alphanumeric tokens from an answer.

    Any non-alphanumeric character is treated as a token separator. This removes
    punctuation and symbols without accidentally joining the words on either side
    of them (for example, ``"one/two"`` becomes ``["one", "two"]``).
    """
    tokens: list[str] = []
    current_token: list[str] = []

    for character in answer:
        if character.isalnum():
            current_token.append(character)
        elif current_token:
            tokens.append("".join(current_token).lower())
            current_token = []

    if current_token:
        tokens.append("".join(current_token).lower())

    return tokens


def answers_match(user_answer: str, expected_answer: str) -> bool:
    """Compare processed user and expected-answer token arrays exactly."""
    input_processed = process_answer(user_answer)
    answer_processed = process_answer(expected_answer)
    return input_processed == answer_processed
