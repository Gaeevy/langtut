import logging
from openai import OpenAI
from dotenv import load_dotenv
import pandas as pd
from pathlib import Path
from enum import Enum
import re

load_dotenv()
logger = logging.getLogger(__name__)

class TextType(Enum):
    QUESTION = "question"
    ANSWER = "answer"

client = OpenAI()

# Get the base directory of the project
BASE_DIR = Path(__file__).parent.parent
RAW_AUDIO_FILES = BASE_DIR / "static_files" / "raw_speech_output"
CSV_PATH = BASE_DIR / "static_files" / "saude.csv"

def preprocess_text(text: str) -> str:
    """Remove numbers and dots at the beginning of the text."""
    return re.sub(r'^\d+\.\s*', '', text.strip())

def setup_logging():
    # Setup custom logger
    logger.setLevel(logging.DEBUG)

    # Create console handler with a specific format
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # Disable other loggers
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)


def generate_audio(text, file_name, text_type: TextType, dry_run=False):
    logger.debug(f"Generating audio file {file_name} for text: {text}")
    if dry_run:
        logger.info(f"Dry run enabled. Skipping audio generation for {file_name}.")
        return
    
    # Ensure output directory exists
    RAW_AUDIO_FILES.mkdir(parents=True, exist_ok=True)

    voice = "coral" # Default voice — goes for questions
    if text_type == TextType.ANSWER:
        voice = "nova"
    
    output_path = RAW_AUDIO_FILES / file_name
    with client.audio.speech.with_streaming_response.create(
            model="gpt-4o-mini-tts",
            voice=voice,
            input=text,
            instructions=f"You're a europian portugues speaker. Speak like a native speaker. Use a friendly tone. You're voicing questions and answers to them. The particular phrase is {text_type.value}",
    ) as response:
        response.stream_to_file(str(output_path))


def process_csv(file_path, dry_run=False):
    df = pd.read_csv(file_path).head(30)
    for i, row in df.iterrows():
        question = preprocess_text(row['pergunta'])
        answer = preprocess_text(row['resposta'])
        question_file_name = f"{i:04d}_pergunta.mp3"
        answer_file_name = f"{i:04d}_resposta.mp3"

        # Check if files already exist before generating
        question_path = RAW_AUDIO_FILES / question_file_name
        answer_path = RAW_AUDIO_FILES / answer_file_name

        if not question_path.exists():
            generate_audio(question, question_file_name, TextType.QUESTION, dry_run=dry_run)
        else:
            logger.info(f"Skipping existing file: {question_file_name}")

        if not answer_path.exists():
            generate_audio(answer, answer_file_name, TextType.ANSWER, dry_run=dry_run)
        else:
            logger.info(f"Skipping existing file: {answer_file_name}")


if __name__ == "__main__":
    setup_logging()
    process_csv(CSV_PATH, dry_run=False)