import os
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor
from random import uniform
from time import sleep

import openai
import requests
from PIL import Image
from lobe import ImageModel

from FaceCrop import detect_and_crop_main_face
from tinderAPI import tinderAPI

model = ImageModel.load('C:/Users/david/PycharmProjects/Lobe Models/Tinder Faces 3.0 TensorFlow 4')
SWIPE_LEFT_CONFIDENCE_THRESHOLD = 0.93
openai.api_key = "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"

# Add max_images_per_person as a global variable
max_images_per_person = 3


# (Include all functions from TinderAutomate0_3.py here)
# get_lobe_score, save_image, save_original_image, process_person
def get_lobe_score(image_url):
    req = requests.get(image_url, stream=True)
    if req.status_code == 200:
        original_img = Image.open(req.raw).convert('RGB')
        cropped_face = detect_and_crop_main_face(original_img)
        if cropped_face is not None:
            pil_cropped_face = Image.fromarray(cropped_face)
            grayscale_face = pil_cropped_face.convert('L')
            result = model.predict(grayscale_face)
            label = result.prediction

            confidence_dict = dict(result.labels)
            print(f"Confidence for '{label}': {confidence_dict[label]}")

            # Check if the confidence for 'Swipe Left' is below the threshold
            if label == 'Swipe Left' and confidence_dict[label] < SWIPE_LEFT_CONFIDENCE_THRESHOLD:
                label = 'Swipe Right'

            return label, grayscale_face, original_img
        else:
            return None, None, None
    else:
        return None, None, None

def save_image(label, img, file_name):
    folder_map = {
        'Swipe Right': './images/lobe swipe right',
        'Swipe Left': './images/lobe swipe left'
    }

    folder = folder_map[label]
    if not os.path.exists(folder):
        os.makedirs(folder)

    file_path = os.path.join(folder, file_name)
    img.save(file_path)
    print(f"Saved image to {file_path}")

def save_original_image(label, img, file_name):
    folder_map = {
        'Swipe Right': './images/lobe swipe right/original',
        'Swipe Left': './images/lobe swipe left/original'
    }

    folder = folder_map[label]
    if not os.path.exists(folder):
        os.makedirs(folder)

    file_path = os.path.join(folder, file_name)
    img.save(file_path)
    print(f"Saved original image to {file_path}")

# Define a new function to process a single person
def process_person(person):
    right_swipe = False
    for i, image_url in enumerate(person.images[:max_images_per_person]):
        try:
            lobe_score, face_img, original_img = get_lobe_score(image_url)
            if lobe_score is not None and face_img is not None:
                file_name = f"{person.id}_{i}.png"
                save_image(lobe_score, face_img, file_name)
                save_original_image(lobe_score, original_img, file_name)

                if lobe_score == "Swipe Right":
                    right_swipe = True
                    break
        except Exception as e:
            print(f"Error processing image for {person.name} ({person.id}): {e}")

    sleep_time = uniform(1, 3)  # You can adjust the range as needed

    if right_swipe:
        person.like()
        print(f"Liked {person.name} ({person.id}) - At least one 'Swipe Right'")
        time.sleep(sleep_time)
        return "like"
    else:
        person.dislike()
        print(f"Disliked {person.name} ({person.id}) - All 'Swipe Left' or errors")
        time.sleep(sleep_time)
        return "dislike"

# (Include all functions from TinderAutomateConversations0_2.py here)
# conversation_starter, chatbot, print_conversation, check_and_send_message

def conversation_starter(match_name):
    return f"Hey {match_name}! Critical question for you. Would you prefer endless tacos and cocktails in Mexico, or pasta and endless wine in Italy?"

def chatbot(input, message_count):
    messages = [
        {
            "role": "system",
            "content": "Continue a partially-started conversation as a 30-year-old male, "
                       "using a dating app to meet new women. Adapt to the existing conversation. Write short and "
                       "consise responses and speak with the confidence of james bond, but never say you are james bond."
                       "Every message should tease the match "
                       "and keep the conversation very edgy, flirtatious, and sexual. Progress the "
                       "conversation to requesting a date over drinks"
        }
    ]

    if input:
        messages.append({"role": "user", "content": input})
        chat = openai.ChatCompletion.create(
            model="gpt-4", messages=messages
        )
        reply = chat.choices[0].message.content.strip()
        return reply

def print_conversation(messages, my_user_id, match):
    print(f"Match ID: {match.id}")
    print("Conversation:")
    for message in messages:
        sender = "You" if message["from"] == my_user_id else match.person.name
        print(f"{sender} ({message['sent_date']}): {message['message']}")

def check_and_send_message(api, match):
    messages = match.messages
    my_user_id = api.user_id

    if len(messages) == 0:
        print("No messages sent yet, sending conversation starter.")
        response = conversation_starter(match.person.name)
    elif messages[-1]["from"] != my_user_id:
        print("Match has sent the last message, generating response.")
        input_text = messages[-1]["message"]
        message_count = len(messages) // 2
        response = chatbot(input_text, message_count)
        time.sleep(2)
    else:
        print("Last message was sent by me, waiting for a response from the match.")
        return

    # Check if match's phone number is included in the last message, only if there are messages
    if messages and any(char.isdigit() for char in messages[-1]["message"]):
        print("Match's phone number detected, stopping further messages.")
        return

    print_conversation(messages, my_user_id, match)
    print(f"Sending response: {response}")
    # Comment the following line to prevent sending the message to Tinder
    api.send_message(match.id, response, match.person.id)

def process_swipes(api, batch_size_swipes):
    like_count = 0
    dislike_count = 0

    people = api.nearby_persons()
    for i in range(0, len(people), batch_size_swipes):
        batch = people[i:i+batch_size_swipes]
        with ThreadPoolExecutor(max_workers=batch_size_swipes) as executor:
            results = executor.map(process_person, batch)

        for result in results:
            if result == "like":
                like_count += 1
            elif result == "dislike":
                dislike_count += 1

    return like_count, dislike_count

def process_conversations(api, batch_size_conversations):
    matches = api.matches(limit=30)

    for i in range(0, len(matches), batch_size_conversations):
        conversation_batch = matches[i:i+batch_size_conversations]
        for match in conversation_batch:
            check_and_send_message(api, match)
            sleep_time = random.uniform(2, 6)  # Random wait between 1 and 5 seconds
            print(f"Waiting {sleep_time} seconds before next API call.")
            time.sleep(sleep_time)

def check_phone_number(messages):
    phone_number_pattern = re.compile(r'\b\d{10}\b')
    for message in messages:
        if phone_number_pattern.search(message['message']):
            return True
    return False

def main():
    token = "2e99a960-024a-492e-89e2-b7efd9a6e4cc"
    api = tinderAPI(token)

    batch_size_swipes = 8
    batch_size_conversations = 5
    total_loops = 12  # You can adjust this value as needed
    matches_to_check = 15  # Set the number of matches to check before swiping again

    matches_with_sent_messages = set()

    for _ in range(total_loops):
        like_count, dislike_count = process_swipes(api, batch_size_swipes)
        print(f"Total Likes: {like_count}, Total Dislikes: {dislike_count}")

        # Add random sleep between batches of people to avoid rate limiting
        sleep_time = uniform(3, 5)
        print(f"Sleeping for {sleep_time} seconds before processing conversations.")
        sleep(sleep_time)

        matches = api.matches(limit=50)
        checked_matches = 0
        go_back_to_swiping = False

        for match in matches:
            if go_back_to_swiping:
                break

            if match.id in matches_with_sent_messages:
                print(f"Skipping match {match.id} as we already sent the last message.")
                continue

            check_and_send_message(api, match)
            sleep_time = random.uniform(3, 10)  # Random wait between 1 and 5 seconds
            print(f"Waiting {sleep_time} seconds before next API call.")
            sleep(sleep_time)

            messages = match.messages
            my_user_id = api.user_id

            if messages and messages[-1]["from"] == my_user_id:
                matches_with_sent_messages.add(match.id)

            checked_matches += 1

            if checked_matches % matches_to_check == 0:
                go_back_to_swiping = True

        sleep_time = uniform(14, 25)
        print(f"Sleeping for {sleep_time} seconds before processing next loop.")
        sleep(sleep_time)


if __name__ == "__main__":
    main()



