import ngrok
import redis
from flask import Flask, request, stream_with_context, Response
import logging
import requests
from flask_cors import CORS, cross_origin
import time
import json
import assemblyai as aai
from threading import Thread

r = redis.Redis(host='localhost', port=6379, db=0)

ngrok_tunnel = "https://ae968869e4ad.ngrok.app"  #note to update this every time you restart server
r.set('ngrok_url', ngrok_tunnel)

assembly_key = "09578ab459aa4f998c90f1adb44ea9ea"
aai.settings.api_key = assembly_key
def get_transcript(id):
    headers = {'authorization': assembly_key}
    response = requests.get(
        'https://api.assemblyai.com/v2/transcript/' + id,
        json={},
        headers=headers
    )
    return response.json()

first_transcript_flag = True

# create Flask app
app = Flask(__name__)

lemur_feedback_format = "<HEADLINE> \n\n <ul><NOTE><NOTE><NOTE></ul>"

crm_options = ["Salesforce", "Hubspot", "Close", "Other"]

sales_challanges_options = ["Top of funnel", "Close rates", "Sales cycle too long", "Poor record keeping", "Other"]

lead_source_options = ["Referral", "Google", "Social Media", "Conference", "Other"]

def lemur_call(transcript, prev_responses):
    lemur = aai.Lemur()
    input_text = transcript
    prompt = f"""
    You are a helpful assistant who has a goal of taking diligent notes for sales representatives and contact center employees. You have a very specific form to fill out. 
    
    Here is what you have so far. Remember, you should ONLY BUILD UPON WHAT YOU HAVE SO FAR, WITHOUT MAKING UNEEDED CHANGES or DELETING FIELDS.

    However, you should make sure to update previous responses based on new information in the transcript if something seems to contradict what was found earlier on.

    {prev_responses}

    Please continue to fill out this form, and make updates to previous responses where you see fit. For each heading (##), please provide a short, concise response, using the directions in the bullet points below each heading as your criteria.

    Remember to continue revising your previous nswer based on new information in the transcript

    ## Are they qualified?
    -Is this person /company qualified to get value out of a new CRM product? 
    -You should only output a 'yes' or 'no' answer to this question
    -If we don't have a CLEAR answer to whether or not they are qualified, you should leave this field blank

    ## What is their current CRM? 
    -What CRM do they currently use? What will our solution replace?
    -Please choose from the following options: {crm_options}. if none of the options apply, please put OTHER in this field and provide the name of the CRM if they tell us.
    -If it sounds like they're currently using a CRM, but they don't tell us who, you should put OTHER in this field
    -If no CRM is mentioned, please leave this field blank

    ## General Enthusiasm Level For Our Product/Company
    -Please respond with a number between 1 and 5, where 1 is not positive at all, and 5 is extremely positive
    -If we don't yet have enough information to answer this question, please leave this field blank. You should have at least a few paragraphs worth of transcription to answer this

    ## How many users/employees do they have?
    -Enter a NUMERICAL value. If they don't tell us, you can put leave this field blank
    -They are also likely to provide a general range. If they do this, please reflect a range like > 1000 (if the amount is greater than 1k), 100-150 (if between 100 and 150), < 10 (if less than 10), etc.
    -If they don't mention this, please leave this field blank
    -You should make sure to enter an overall number. if the prospect provides a list of employees from several departments, please add them together for a single overall user count.
        -i.e. if they say they have 10 AEs and 2 SDRs, you should enter 12 as the total number of users

    ## Did they watch the demo video?
    -Please only return a 'yes' or 'no' answer to this question
    -If the topic of the demo video is not discussed, please leave this field blank

    ## How did they hear about us?
    -Please return one of the following options: {lead_source_options}
    -If they don't mention any of these, please leave this field blank
    -If 'other' is selected, please cite the source they mention

    ## Sales Workflow Notes
    -Please provide an overview of how this prospect's company handles their sales process. 
    -What are the steps they take to close a deal? We seek to understand their entire workflow: from lead to close and post sale
    -What is their sales model? (choose one: transactional, self service, enterprise, hybrid, or other)
    -You won't be able to capture answers to this field all at once, so make sure you continue to update this based on the transcript and new information
    -If they don't mention any of these, please leave this field blank

    ## Top Sales Challenges
    -Please return a sublist from this overall list of potential challenges: {sales_challanges_options}
    -If they don't mention anything about a sales challenge, please leave this field blank 
    -If 'other' is selected, please cite the challenge they mention

    ## Next Steps
    -What are the next steps for this prospect?
    -A next step is a tangible action that the sales rep should take after the call. 
    -Examples of next steps include: sending a follow up email, scheduling a demo, sending a contract, etc.
    -If no next step is clear please leave this field blank. We NEED to identify situations where next steps are not clear

    ## Other Notes
    -Please provide any other notes that you think would be helpful for the sales rep to know
    -If nothing else is directly relevant to a sales rep in this scenario or their team who will refer back to these notes later, please leave this field blank.

    You SHOULD NOT make up any information that is not contained within the transcript. If you are unsure of an answer, you can leave it blank.
    Assume that you DO NOT know the answer until you get clear information from the transcript. You should leave spaces blank or put UNKNOWN until you get clear information from the transcript.
    
    YOU SHOULD NOT UNDER ANY CIRCUMSTANCES INCLUDE A PREAMBLE. Statements such as 'here are my notes' or 'here is what I have so far' should not be included in your response as they are strictly prohibited. 
    """
    try:
        response = lemur.task(
            prompt=prompt,
            input_text=input_text,
            final_model="basic",
            max_output_size=3000
        )
        print(response)
        return response.response
    except Exception as e:
        print("Error: ", e)
        return "Error"


@app.route('/start', methods=['POST'])
def start_process():
    data = request.get_json()
    session_id = str(data.get('session_id'))
    if session_id:
        print("Starting process for:", session_id)
        stream_id = r.hget('sessions', session_id).decode('utf-8')
        print("STREAM ID: ", stream_id)
        Thread(target=check_for_updates_and_call_lemur, args=(stream_id,)).start()
        return {"message": "Process started for session " + stream_id}, 200
    else:
        return {"error": "Session ID not provided"}, 400

def check_for_updates_and_call_lemur(stream_id):
    
    r.hset(f"lemur_outputs:{stream_id}", "latest", " ")
    print("Starting check for updates on session:", stream_id)
    previous_transcript = ""
    while True:
        time.sleep(30)  # Check every 15 seconds
        current_transcript = r.get(f"transcripts_{stream_id}")
        print(current_transcript.decode())

        previous_responses = r.hget(f"lemur_outputs:{stream_id}", "latest")
        print(len(previous_responses))
        if len(previous_responses) > 5:
            previous_responses.decode('utf-8')
        print(previous_responses)
        print(current_transcript)
        if current_transcript and current_transcript.decode() != previous_transcript:
            print("CONDITION MET")
            previous_transcript = current_transcript.decode()
            # Call LeMUR API
            lemur_response = lemur_call(previous_transcript, previous_responses)
            print(lemur_response)
            # Store in Redis
            r.hset(f"lemur_outputs:{stream_id}", 'latest', json.dumps(lemur_response))


@app.route('/stream')
def stream():
    def event_stream():
        stream_id = request.args.get('streamid')
        previous_lemur_output = None
        while True:
            # Get the latest LeMUR output from Redis
            lemur_output = r.hget(f"lemur_outputs:{stream_id}", 'latest').decode('utf-8')
            
            if lemur_output != previous_lemur_output:
                # Update the previous output and send the new data as an SSE
                previous_lemur_output = lemur_output
                yield f"data: {json.dumps({'lemur_response': previous_lemur_output})}\n\n"  # SSE data format

            # Sleep to prevent CPU overload and allow for new updates to come in
            time.sleep(3)

    headers = {
        'Content-Type': 'text/event-stream',
        'Access-Control-Allow-Origin': 'http://localhost:3000',
        'Access-Control-Allow-Credentials': 'true'
    }
    
    response = Response(stream_with_context(event_stream()), headers=headers, mimetype="text/event-stream")
    print(response.headers)
    return response

if __name__ == "__main__":

    # start the Flask app
    app.run(port=5000)