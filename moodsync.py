import json
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
import threading
import webbrowser
from flask import Flask, jsonify, redirect, request, url_for
from flask_cors import CORS
from flask import jsonify
from spotipy import SpotifyException, SpotifyOauthError

# Spotify application credentials (replace with yours)
CLIENT_ID = "2a5e5d4a0d2b4567ae2a841ac2359df6"
CLIENT_SECRET = "cf72c10fff1d41e780e844759f3318d1"
REDIRECT_URI = "http://localhost:5000/callback"

# Flask app for handling authorization callback
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Global variables
access_token = None
authorization_url = None
authorization_completed = False
sp = None

def start_flask_server():
    app.run(debug=False, port=5000)

@app.route("/authorize", methods=["GET"])
def authorize():
    global access_token, authorization_url

    # Open Spotify login page in the user's web browser
    sp_oauth = SpotifyOAuth(client_id=CLIENT_ID,
                            client_secret=CLIENT_SECRET,
                            redirect_uri=REDIRECT_URI,
                            scope="user-read-recently-played")

    authorization_url = sp_oauth.get_authorize_url()
    
    # Return the authorization URL to the client
    return jsonify({"authorization_url": authorization_url}), 200


def get_audio_features(track_id):
    global sp
    audio_features = sp.audio_features(tracks=[track_id])
    if audio_features:
        track_features = audio_features[0]
        valence = track_features['valence']
        energy = track_features['energy']
        return valence, energy
    else:
        return None, None

@app.route("/show_songs_list", methods=["GET"])
def show_songs_list():
    global access_token, authorization_completed, sp
    print("Access token", access_token)

    if not authorization_completed:
        return jsonify({"error": "Authorization not completed"}), 500

    if access_token:
        # Create a Spotify object with the access token
        sp = Spotify(auth=access_token)

        results = sp.current_user_recently_played()
        tracks = [item['track'] for item in results['items']]
        return jsonify({"tracks": tracks}), 200

@app.route('/analysis')
def analysis():
    return open("analysis.html", "r").read()

@app.route("/analyze", methods=["GET"])
def analyze():
    global access_token, authorization_completed, sp
    # print("Access token", access_token)
    
    if not authorization_completed:
        return jsonify({"error": "Authorization not completed"}), 500

    if access_token:
        # Create a Spotify object with the access token
        sp = Spotify(auth=access_token)

        results = sp.current_user_recently_played()
        tracks = [item['track']['name'] for item in results['items']]
            
        # Define sliding window parameters
        window_size = 20
        window_jump = 10

        # Initialize mood progression
        mood_progression = []

        # Process sliding windows
        for i in range(0, len(tracks), window_jump):
            window_tracks = tracks[i:i+window_size]
            valences = []
            energies = []
            for track_name in window_tracks:
                track_info = sp.search(q=track_name, type='track')
                if track_info and track_info['tracks']['items']:
                    track_id = track_info['tracks']['items'][0]['id']
                    print(f"Processing track: {track_name} ({track_id})")  # Print track being processed
                    valence, energy = get_audio_features(track_id)
                    if valence is not None and energy is not None:
                        valences.append(valence)
                        energies.append(energy)

            # Calculate average valence and arousal for the window
            if valences and energies:
                avg_valence = sum(valences) / len(valences)
                avg_energy = sum(energies) / len(energies)

                # Determine mood based on average valence and arousal
                if avg_valence > 0.5:
                    mood = "calm" if avg_energy < 0.5 else "happy"
                else:
                    mood = "anxious" if avg_energy < 0.5 else "sad"
            else:
                mood = "unknown"  # Mood cannot be determined

            mood_progression.append(mood)

        # Construct mood distribution data
        mood_distribution = {
            "calm": mood_progression.count("calm"),
            "happy": mood_progression.count("happy"),
            "anxious": mood_progression.count("anxious"),
            "sad": mood_progression.count("sad"),
            "unknown": mood_progression.count("unknown")
        }

        # Construct mood progression message
        mood_message = "<br>".join([f"Window {i+1}: {mood}" for i, mood in enumerate(mood_progression)])
        print(mood_message)

        # Return data in the expected format
        return jsonify({"mood_data": mood_distribution, "mood_text": mood_message})



@app.route("/")
def index():
    return open("index.html", "r").read()

@app.route("/callback")
def callback():
    global access_token, authorization_completed

    # Extract authorization code from the callback URL
    code = request.args.get("code")

    # Use SpotifyOAuth to exchange code for an access token
    sp_oauth = SpotifyOAuth(client_id=CLIENT_ID,
                            client_secret=CLIENT_SECRET,
                            redirect_uri=REDIRECT_URI)
    try:
        token_data = sp_oauth.get_access_token(code)
        access_token = token_data['access_token']
        # Authorization successful, proceed with accessing Spotify API
    except SpotifyOauthError as e:
        # Handle OAuth error
        print("OAuth Error:", e)
    except Exception as e:
        # Handle other exceptions
        print("Error:", e)
        access_token = token_data["access_token"]

    authorization_completed = True

    return redirect(url_for('show_songs'))

@app.route("/show_songs")
def show_songs():
    return open("show_songs.html", "r").read()


if __name__ == "__main__":
    app.run(debug=True, port=5000)
