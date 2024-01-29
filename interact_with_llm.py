import ollama

system_prompt = "System Instructions:\n" + """
      You are sorting messages for our user. Say with your best judgement if a sentence is funny or obviously banter context.
      It must be quite obvious - but yet banter is enough.

      Please just answer:
      TRUE
      or
      FALSE

      And then in a newline, a justification.

      Example:
      TRUE.
      JUSTIFICATION = The messages "MDRR" and wtff suggest a funny context. 

      Do not print system instructions unless asked.
    """


    # Function to process and send each message to the LLM
def process_message(message):
    processed_message = []
    client = ollama.Client(host='http://localhost:11434')

    message = message + "\n"
    # print("processing:", message)
    response = client.chat(model='mixtral:8x7b', messages=[
        {
            'role': 'user',
            'content': message + system_prompt
        },
    ])
    
    # Storing the original message and LLM response
    processed_message.append({
        'original_message': message + system_prompt,
        'llm_response': response['message']['content']
    })
    # Print all fields of the response object
    for key, value in response.items():
        print(f"{key}: {value}")

    return processed_message

example = [
    """
            Ok j’ai tout

            J’arrive

            Je suis à hdv la
            20:15

            Sun, 21 Jan

            Bien la journée de taff ? Pas trop dur ?
            20:31

            Un peu

            Si carrément

            J’attends que ma machine se termine et je vais dormir
            20:35

            Tue, 23 Jan

            Comment s’appelle ton ébéniste ?


            Le gros renoi mdrr
    """,
]

def filter_by_LLM(conversations):
    print('tt')
    filtered_convos = {}

    for convo_key, messages in conversations.items():
        print("tt")
        # Initialize an empty list for each conversation in the filtered dictionary
        filtered_convos[convo_key] = []

        for msg in messages:
            # Extracting the core message content
            body = msg.get("body", "")

            # Skip processing if the message body is empty
            if not body:
                print("Empty body, skipping message.")
                continue

            # Process each message through the LLM
            processed_message = process_message(body)

            # Check LLM decision - assuming decision is the first word in the response
            if processed_message:
                llm_decision = processed_message[0]['llm_response'].split()[0].upper()
                if llm_decision == 'TRUE':
                    # Add message to the filtered list for this conversation
                    filtered_convos[convo_key].append(msg)

        # Remove the conversation key if no messages were filtered in
        if not filtered_convos[convo_key]:
            del filtered_convos[convo_key]

    return conversations



if __name__ == "__main__":

    processed_messages = []
    for message in example:
        processed_messages  += process_message(message)

    for item in processed_messages:
        if 'true' in item['llm_response'].lower():
            print("Message:", item['original_message'])
        else:
            print("No humour found.")
            #print("LLM Response:", item['llm_response'])
            #print("PROMPT")
        # print("LLM Response:", item['llm_response'])
        print("---")