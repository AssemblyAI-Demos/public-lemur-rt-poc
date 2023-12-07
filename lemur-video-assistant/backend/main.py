# import os
# import requests
# import subprocess
# import time
# import redis
# from glob import glob
# import ngrok
# from flask import Flask, request
# from threading import Thread
# from pydub import AudioSegment

# r = redis.Redis(host='localhost', port=6379, db=0)

# webhook_url = r.get('ngrok_url').decode() + '/'
# assembly_key = "YOUR KEY HERE"

# # create Flask app
# app = Flask(__name__)

# def has_audio(filename):
#     audio = AudioSegment.from_file(filename)
#     return len(audio) > 0


# # Function to upload a file to AssemblyAI for transcription
# def upload_to_assemblyai(filename):
#     headers = {'authorization': assembly_key}
#     response = requests.post(
#         'https://api.assemblyai.com/v2/upload',
#         headers=headers,
#         data=open(filename, 'rb')
#     )
#     return response.json()['upload_url']

# # Function to transcribe an uploaded file with AssemblyAI
# def transcribe_with_assemblyai(upload_url, stream_id):
#     headers = {'authorization': assembly_key}
#     response = requests.post(
#         'https://api.assemblyai.com/v2/transcript',
#         json={'audio_url': upload_url, 'speaker_labels': True, 'speech_threshold': 0.2, 'webhook_url': f'{webhook_url}/?streamid={stream_id}'}, 
#         headers=headers
#     )
#     return response.json()['id']


# def upload_and_transcribe(filename, stream_id):
#     upload_url = upload_to_assemblyai(filename)
#     transcript_id = transcribe_with_assemblyai(upload_url, stream_id)
#     return transcript_id


# def process_video(data):
#     rtmp_url = data.get('url', '')  # extract the URL from the data
#     session_id = data.get('session_id', '')
#     print('rtmp_url: ' + rtmp_url)
#     print("waiting for stream to sync")
#     # Start consuming the RTMP livestream and segmenting it into chunks
#     time.sleep(3)
#     start_time = int(time.time())  # Get the current time in seconds since the Epoch
#     r.hset('sessions', session_id, start_time) #store the session in redis. this will associate the front end session with the stream id (start time)
#     counter = 0
#     while True:
#         # Define the output filename based on the counter
#         filename = f'stream_{start_time}_{counter:04d}.mp3'

#         # Start consuming the RTMP livestream and segmenting it into 20s chunks
#         command = ['ffmpeg', '-i', rtmp_url, '-f', 'mp3', '-t', '20', filename]

#         # Run the ffmpeg command and wait for it to complete
#         ffmpeg_process = subprocess.run(command)

#         print(f'Processing {filename}...')
#         transcript_id = upload_and_transcribe(filename, start_time) #use start time as stream id
#         print(f'Transcription started with id {transcript_id}...')

#         # try:
#         #     # Remove the file after it has been uploaded
#         #     # os.remove(filename)
#         # except Exception as e:
#         #     print("error removing file:", filename, e)

#         # Increment the counter for the next loop
#         counter += 1

# @app.route('/', methods=['POST'])
# def app_handler():
#     data = request.get_json()
#     thread = Thread(target=process_video, args=(data,))
#     thread.start()
#     return {"status": "processing started"}

# @app.route('/stream_id', methods=['GET'])
# def get_stream_id():
#     session_id = request.args.get('session_id')  # get the session_id from the query parameters
#     stream_id = r.hget('sessions', session_id)  # retrieve the stream_id from Redis
#     if stream_id is None:
#         return {'error': 'No stream associated with this session'}, 404
#     return {'stream_id': stream_id.decode()}, 200

# if __name__ == "__main__":

#     # start the Flask app
#     app.run(port=5001)


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

# Function to handle WebSocket messages (transcription responses)
def on_message(ws, message):
    print("MESSAGE MF")
    transcript = json.loads(message)
    text = transcript.get('text', '')

    # Handling different types of messages
    if transcript.get("message_type") == "PartialTranscript":
        print(f"Partial transcript: {text}")
    elif transcript.get("message_type") == 'FinalTranscript':
        print(f"Final transcript: {text}")
        # Additional processing for final transcript can be done here

def on_error(ws, error):
    print(f"WebSocket Error: {error}")

def on_close(ws, close_status_code, close_reason):
    print(f"WebSocket closed with code {close_status_code}: {close_reason}")


# RTMP to PCM conversion and WebSocket streaming
def process_rtmp_stream(rtmp_url, session_id):
# def process_rtmp_stream(data):
    print("DATA MF")
    print(rtmp_url)
    print("DATA MFs 2")
    print(session_id)
    # rtmp_url = data.get('url', '')  # extract the URL from the data
    # session_id = data.get('session_id', '')
    print('rtmp_url: ' + rtmp_url)
    print("waiting for stream to sync")
    # Start consuming the RTMP livestream and segmenting it into chunks
    time.sleep(3)
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
