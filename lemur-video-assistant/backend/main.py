import os
import requests
import subprocess
import time
import redis
import websocket
import base64
import threading
import json
from flask import Flask, request
from threading import Thread

# AssemblyAI API token
assembly_key = "2ba8fb6072af407f83d6f5bbec69863d"

# Redis setup
r = redis.Redis(host='localhost', port=6379, db=0)

# Flask app
app = Flask(__name__)

# Global dictionary to store final transcripts by session ID
final_transcripts = []

# Function to handle WebSocket messages (transcription responses)
def on_message(ws, message):
    print("MESSAGE MF")
    transcript = json.loads(message)
    text = transcript.get('text', '')
    session_id = transcript.get('session_id', '')

    # Handling different types of messages
    if transcript.get("message_type") == "PartialTranscript":
        print(f"Partial transcript: {text}")
    elif transcript.get("message_type") == 'FinalTranscript':
        print(f"Final transcript: {text}")
        # if session_id:
            # if session_id not in final_transcripts:
            #     final_transcripts[session_id] = []
        final_transcript = {
                'session_id': session_id,
                'text': text
        }
        final_transcripts.append(final_transcript)

def on_error(ws, error):
    print(f"WebSocket Error: {error}")

def on_close(ws, close_status_code, close_reason):
    print(f"WebSocket closed with code {close_status_code}: {close_reason}")

# Function to periodically write final transcripts to Redis
def write_transcripts_to_redis(session_id):
    print("WRITING TRANSCRIPTS TO REDIS FN")
    while True:
        print("WRITING TRANSCRIPTS TO REDIS LOOP")
        print(final_transcripts)
        time.sleep(1)  # Wait for 30 seconds
        combined_transcript = ' '
        for final_transcript in final_transcripts:
            combined_transcript += final_transcript['text'] + ' '
        print(combined_transcript)
        r.set(f"transcripts_{session_id}", combined_transcript)

# RTMP to PCM conversion and WebSocket streaming
def process_rtmp_stream(rtmp_url, session_id):
    r.set("transcripts", " ")
    print("RTMP URL")
    print(rtmp_url)
    print("SESSION ID")
    print(session_id)
    print("waiting for stream to sync")
    # Start consuming the RTMP livestream and segmenting it into chunks
    time.sleep(1)
    start_time = int(time.time())  # Get the current time in seconds since the Epoch
    r.hset('sessions', session_id, start_time) #store the session in redis. this will associate the front end session with the stream id (start time)
    # WebSocket setup
    ws_url = f"wss://api.assemblyai.com/v2/realtime/ws?sample_rate=16000"
    ws = websocket.WebSocketApp(
        ws_url,
        header={"Authorization": assembly_key},
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    
    # Start WebSocket connection in a separate thread
    threading.Thread(target=lambda: ws.run_forever()).start()

    # Wait for WebSocket to open
    time.sleep(2)

    # FFmpeg command to capture RTMP stream and convert to PCM 16-bit
    command = ['ffmpeg', '-i', rtmp_url, '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', '-f', 's16le', '-']

    # Start the FFmpeg process
    ffmpeg_process = subprocess.Popen(command, stdout=subprocess.PIPE)

    # Start the periodic function in a thread
    threading.Thread(target=write_transcripts_to_redis, args=(session_id,)).start()

    while True:
        try:
            # Read audio data from FFmpeg
            data = ffmpeg_process.stdout.read(3200)
            if not data:
                break

            # Encode data in base64 and send over WebSocket
            encoded_data = base64.b64encode(data).decode("utf-8")
            ws.send(json.dumps({"audio_data": encoded_data}))

        except Exception as e:
            print(f"Error processing audio data: {e}")
            break

    # Close the WebSocket connection
    ws.close()


# Flask endpoint to start processing RTMP stream
@app.route('/', methods=['POST'])
def app_handler():
    data = request.get_json()
    print(data)
    rtmp_url = data.get('url', '')
    session_id = data.get('session_id', '')

    # Start processing RTMP stream in a separate thread
    # Thread(target=process_rtmp_stream, args=(rtmp_url, session_id)).start()
    Thread(target=process_rtmp_stream, args=(rtmp_url, session_id)).start()
    return {"status": "processing started"}

# Flask endpoint to retrieve stream ID
@app.route('/stream_id', methods=['GET'])
def get_stream_id():
    print('Getting stream ID')
    session_id = request.args.get('session_id')
    stream_id = r.hget('sessions', session_id)
    if stream_id is None:
        return {'error': 'No stream associated with this session'}, 404
    return {'stream_id': stream_id.decode()}, 200

# Main function
if __name__ == "__main__":
    app.run(port=5001)
