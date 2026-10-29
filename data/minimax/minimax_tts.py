import os
import sys
import time
import json
import logging
import datetime
import argparse
import requests
import subprocess

def setup_logging():
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"tts_generation_{timestamp}.log"

    logger = logging.getLogger("MiniMaxTTS")
    logger.setLevel(logging.DEBUG)

    file_handler = logging.FileHandler(log_filename)
    file_handler.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

def load_config(config_path, logger):
    logger.info(f"Loading configuration from {config_path}")
    if not os.path.exists(config_path):
        logger.error(f"Configuration file not found: {config_path}")
        sys.exit(1)

    with open(config_path, 'r', encoding='utf-8') as f:
        try:
            config = json.load(f)
            return config
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON config: {e}")
            sys.exit(1)

def read_input_text(text_path, logger):
    logger.info(f"Reading input text from {text_path}")
    if not os.path.exists(text_path):
        logger.error(f"Input text file not found: {text_path}")
        sys.exit(1)

    with open(text_path, 'r', encoding='utf-8') as f:
        text = f.read().strip()

    if not text:
        logger.error("Input text file is empty.")
        sys.exit(1)

    return text

def submit_task(text, config, logger):
    url = "https://api.minimax.io/v1/t2a_async_v2"

    headers = {
        'Authorization': f"Bearer {config['api_key']}",
        'Content-Type': 'application/json',
        'GroupId': config['group_id']
    }

    payload = {
        "model": config.get('model_id', 'speech-2.8-hd'),
        "text": text,
        "lang": config.get('lang', 'ja_JP'),
        "voice_setting": config.get('voice_setting', {}),
        "audio_setting": config.get('audio_setting', {})
    }

    logger.info("Submitting text-to-speech task to MiniMax API...")
    logger.debug(f"Payload: {json.dumps(payload, indent=2)}")

    response = requests.post(url, headers=headers, json=payload)
    logger.debug(f"Submit response status: {response.status_code}")
    logger.debug(f"Submit response text: {response.text}")

    if response.status_code != 200:
        logger.error("Failed to submit task via HTTP.")
        sys.exit(1)

    response_data = response.json()
    base_resp = response_data.get('base_resp', {})

    if base_resp.get('status_code') != 0:
        logger.error(f"API rejected task: {base_resp.get('status_msg')}")
        sys.exit(1)

    task_id = response_data.get("task_id")
    if not task_id:
        logger.error("No task_id found in the successful response.")
        sys.exit(1)

    logger.info(f"Task successfully created. Task ID: {task_id}")
    return task_id

def poll_task_status(task_id, config, logger, poll_interval=5):
    url = f"https://api.minimax.io/v1/query/t2a_async_query_v2?task_id={task_id}"

    headers = {
        'Authorization': f"Bearer {config['api_key']}",
        'Content-Type': 'application/json',
        'GroupId': config['group_id']
    }

    logger.info("Polling task status...")

    while True:
        response = requests.get(url, headers=headers)

        if response.status_code != 200:
            logger.error(f"Failed to query task status. HTTP {response.status_code}")
            time.sleep(poll_interval)
            continue

        data = response.json()
        logger.debug(f"Poll response: {json.dumps(data)}")

        status = data.get("status")

        if status == "Success":
            file_id = data.get("file_id")
            logger.info(f"Task complete. Target File ID: {file_id}")
            return file_id
        elif status == "Failed":
            logger.error("Task processing failed on the server side.")
            sys.exit(1)
        else:
            logger.info(f"Task status is currently '{status}'. Waiting {poll_interval} seconds...")
            time.sleep(poll_interval)

def download_audio(file_id, output_path, config, logger):
    url = f"https://api.minimax.io/v1/files/retrieve_content?file_id={file_id}"

    headers = {
        'Authorization': f"Bearer {config['api_key']}",
        'Content-Type': 'application/json',
        'GroupId': config['group_id']
    }

    logger.info(f"Downloading raw audio bitstream to {output_path}...")

    response = requests.get(url, headers=headers, stream=True)

    if response.status_code == 200:
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        logger.info("Raw audio download complete.")
    else:
        logger.error(f"Failed to download audio. HTTP {response.status_code}")
        logger.debug(f"Response text: {response.text}")
        sys.exit(1)

def sanitize_audio(input_path, output_path, logger):
    logger.info(f"Sanitizing audio using ffmpeg to rebuild missing headers...")

    command = [
        "ffmpeg",
        "-y",
        "-v", "error",
        "-i", input_path,
        "-c:a", "flac",
        output_path
    ]

    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.stderr:
            logger.warning(f"ffmpeg reported issues during input parsing (expected for this API's raw streams):\n{result.stderr}")

        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            logger.info("Audio sanitization complete. Clean file generated.")
            os.remove(input_path)
            logger.debug(f"Cleaned up temporary raw file: {input_path}")
        else:
            logger.error("ffmpeg failed to generate the sanitized output file.")
            sys.exit(1)

    except FileNotFoundError:
        logger.error("ffmpeg executable not found. Ensure FFmpeg is installed and added to your system PATH.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error running ffmpeg: {e}")
        sys.exit(1)

def run_ffprobe(file_path, logger):
    logger.info(f"Running ffprobe analysis on {file_path}...")

    command = [
        "ffprobe",
        "-v", "error",
        "-show_format",
        "-show_streams",
        file_path
    ]

    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.stdout:
            logger.info(f"ffprobe format details:\n{result.stdout}")
        if result.stderr:
            logger.error(f"ffprobe error output:\n{result.stderr}")

        if not result.stdout and not result.stderr:
            logger.info("ffprobe returned no output, the file might be entirely empty or corrupted.")

    except FileNotFoundError:
        logger.error("ffprobe executable not found. Ensure FFmpeg is installed and added to your system PATH.")
    except Exception as e:
        logger.error(f"Unexpected error running ffprobe: {e}")

def main():
    parser = argparse.ArgumentParser(description="MiniMax Async TTS Generator")
    parser.add_argument("--config", default="config.json", help="Path to the JSON configuration file")
    parser.add_argument("--input", required=True, help="Path to the input text file")
    parser.add_argument("--output", default="output.flac", help="Path for the generated output audio file")
    args = parser.parse_args()

    logger = setup_logging()

    config = load_config(args.config, logger)
    text = read_input_text(args.input, logger)

    task_id = submit_task(text, config, logger)
    file_id = poll_task_status(task_id, config, logger)

    ext = os.path.splitext(args.output)[1]
    raw_output_path = f"{args.output}.dirty{ext}"

    download_audio(file_id, raw_output_path, config, logger)

    sanitize_audio(raw_output_path, args.output, logger)
    run_ffprobe(args.output, logger)

if __name__ == "__main__":
    main()
