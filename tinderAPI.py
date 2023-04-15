import datetime
import os
import time

import requests
from geopy.geocoders import Nominatim

TINDER_URL = "https://api.gotinder.com"
geolocator = Nominatim(user_agent="auto-tinder", timeout=10)
PROF_FILE = "./images/unclassified/profiles.txt"

class Person(object):

    def __init__(self, data, api):
        self._api = api

        self.id = data["_id"]
        self.name = data.get("name", "Unknown")

        self.bio = data.get("bio", "")
        self.distance = data.get("distance_mi", 0) / 1.60934

        self.birth_date = datetime.datetime.strptime(data["birth_date"], '%Y-%m-%dT%H:%M:%S.%fZ') if data.get(
            "birth_date", False) else None
        self.gender = ["Male", "Female", "Unknown"][data.get("gender", 2)]

        self.images = list(map(lambda photo: photo["url"], data.get("photos", [])))

        self.jobs = list(
            map(lambda job: {"title": job.get("title", {}).get("name"), "company": job.get("company", {}).get("name")}, data.get("jobs", [])))
        self.schools = list(map(lambda school: school["name"], data.get("schools", [])))

        if data.get("pos", False):
            self.location = geolocator.reverse(f'{data["pos"]["lat"]}, {data["pos"]["lon"]}')


    def __repr__(self):
        return f"{self.id}  -  {self.name} ({self.birth_date.strftime('%d.%m.%Y')})"


    def like(self):
        return self._api.like(self.id)

    def dislike(self):
        return self._api.dislike(self.id)

    def download_images(self, folder, sleep_max_for=0, max_retries=3):
        if not os.path.exists(folder):
            os.makedirs(folder)

        for idx, image_url in enumerate(self.images):
            success = False
            retries = 0

            while not success and retries < max_retries:
                try:
                    req = requests.get(image_url, stream=True)
                    success = True
                except ConnectionError as e:
                    print(f"ConnectionError occurred while downloading image {image_url}. Retrying...")
                    retries += 1
                    if retries >= max_retries:
                        print(f"Failed to download image {image_url} after {max_retries} retries.")
                        continue
                    time.sleep(sleep_max_for * (retries + 1))  # You can adjust the sleep time between retries

                if success:
                    local_filename = os.path.join(folder, f"{self.id}_{idx}.jpg")
                    with open(local_filename, "wb") as f:
                        for chunk in req.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)

                    print(f"Downloaded image {idx} for {self.id} to {local_filename}")

                if sleep_max_for > 0:
                    time.sleep(sleep_max_for)


class Profile(Person):

    def __init__(self, data, api):
        super().__init__(data["user"], api)

        self.email = data["account"].get("email")
        self.phone_number = data["account"].get("account_phone_number")

        self.age_min = data["user"]["age_filter_min"]
        self.age_max = data["user"]["age_filter_max"]

        self.max_distance = data["user"]["distance_filter"]
        self.gender_filter = ["Male", "Female"][data["user"]["gender_filter"]]
class Match:
    def __init__(self, data, api):
        self.api = api
        self.id = data["id"]
        self.created_date = data["created_date"]
        self.last_activity_date = data["last_activity_date"]
        self.message_count = data["message_count"]
        self.messages = data["messages"]
        self.person = Person(data["person"], api)
        self.age = self.calculate_age(self.person.birth_date)
        self.seen = data["seen"]
        self.closed = data["closed"]
        self.common_friend_count = data["common_friend_count"]
        self.common_like_count = data["common_like_count"]
        self.dead = data["dead"]
        self.pending = data["pending"]
        self.is_super_like = data["is_super_like"]
        self.is_boost_match = data["is_boost_match"]
        self.is_super_boost_match = data["is_super_boost_match"]
        self.is_primetime_boost_match = data["is_primetime_boost_match"]
        self.is_experiences_match = data["is_experiences_match"]
        self.is_fast_match = data["is_fast_match"]
        self.is_preferences_match = data["is_preferences_match"]
        self.is_matchmaker_match = data["is_matchmaker_match"]
        self.is_opener = data["is_opener"]
        self.has_shown_initial_interest = data["has_shown_initial_interest"]

    @staticmethod
    def calculate_age(birth_date):
        today = datetime.date.today()
        age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        return age

class tinderAPI():

    def __init__(self, token):
        self._token = token
        self.user_id = self.get_user_id()

    def get_user_id(self):
        profile = self.profile()
        return profile.id

    def profile(self):
        data = requests.get(TINDER_URL + "/v2/profile?include=account%2Cuser",
                            headers={"X-Auth-Token": self._token}).json()
        return Profile(data["data"], self)

    def matches(self, limit=10, sort_by_last_activity=True):
        """
        Retrieve matches.
        :param limit: Number of matches to retrieve
        :param sort_by_last_activity: Whether to sort matches by last activity date (most recent first)
        :return: List of Match objects, optionally sorted by last activity date
        """
        data = requests.get(TINDER_URL + f"/v2/matches?count={limit}", headers={"X-Auth-Token": self._token}).json()
        matches = list(map(lambda match: Match(match, self), data["data"]["matches"]))

        if sort_by_last_activity:
            # Sort matches by last activity date, in descending order (most recent first)
            matches = sorted(matches, key=lambda x: x.last_activity_date, reverse=True)

        return matches

    def like(self, user_id):
        data = requests.get(TINDER_URL + f"/like/{user_id}", headers={"X-Auth-Token": self._token}).json()
        return {
            "is_match": data["match"],
            "liked_remaining": data["likes_remaining"]
        }

    def dislike(self, user_id):
        requests.get(TINDER_URL + f"/pass/{user_id}", headers={"X-Auth-Token": self._token}).json()
        return True

    def nearby_persons(self):
        data = requests.get(TINDER_URL + "/v2/recs/core", headers={"X-Auth-Token": self._token}).json()
        return list(map(lambda user: Person(user["user"], self), data["data"]["results"]))

    def fetch_messages(self, match_id, count=100, page_token=None):
        url = TINDER_URL + f"/v2/matches/{match_id}/messages?locale=en&count={count}"
        if page_token is not None:
            url += f"&page_token={page_token}"

        headers = {"X-Auth-Token": self._token}
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            data = response.json()
            return data["data"]["messages"]
        else:
            return None

    def send_message(self, match_id, message, other_id):
        url = f"{TINDER_URL}/user/matches/{match_id}?locale=en"
        headers = {
            "X-Auth-Token": self._token,
            "Content-Type": "application/json"
        }
        payload = {
            "userId": self.user_id,
            "otherId": other_id,
            "matchId": match_id,
            "message": message,
            "sessionId": None
        }

        response = requests.post(url, json=payload, headers=headers)

        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error: {response.status_code}")
            return None
