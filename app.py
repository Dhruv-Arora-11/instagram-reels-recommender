import pandas as pd
import random
import requests
from requests.auth import HTTPBasicAuth
from flask import Flask, render_template, jsonify, request, session, Response
from collections import Counter

app = Flask(__name__)
app.secret_key = "supersecretkey"

# Credentials for university database
DB_USERNAME = "videodata"
DB_PASSWORD = "ShortVideo@10000"

# Load dataset
video_df = pd.read_csv("backend-ml/data/video_clusters.csv")

# Remove rows where cluster is NaN
video_df = video_df.dropna(subset=["dbscan_cluster_label"])

# Your real dataset base URL
BASE_URL = "https://fi.ee.tsinghua.edu.cn/datasets/short-video-dataset/raw_file/"


@app.route("/")
def home():
    session.clear()
    return render_template("index.html")


@app.route("/start_session", methods=["POST"])
def start_session():
    username = request.json.get("username")
    session["username"] = username
    session["liked_clusters"] = []
    return jsonify({"message": "Session started"})


@app.route("/like", methods=["POST"])
def like():
    cluster = request.json.get("cluster")
    
    # Debug: print the cluster being liked
    print(f"Like received for cluster: {cluster}, type: {type(cluster)}")

    if cluster is None:
        return jsonify({"error": "No cluster provided"}), 400

    liked = session.get("liked_clusters", [])
    liked.append(cluster)
    session["liked_clusters"] = liked
    
    print(f"Updated liked clusters: {session['liked_clusters']}")

    return jsonify({"message": "Cluster stored", "cluster": cluster})


@app.route("/get_next_reel")
def get_next_reel():

    liked = session.get("liked_clusters", [])

    # Bias towards most liked cluster
    if liked:
        fav_cluster = Counter(liked).most_common(1)[0][0]

        filtered = video_df[
            video_df["dbscan_cluster_label"] == fav_cluster
        ]

        if not filtered.empty:
            row = filtered.sample(1).iloc[0]
        else:
            row = video_df.sample(1).iloc[0]
    else:
        row = video_df.sample(1).iloc[0]

    video_id = int(row["pid"])
    cluster = int(row["dbscan_cluster_label"])

    # Use proxy endpoint instead of direct URL
    video_url = f"/proxy_video/{video_id}"

    return jsonify({
        "video_id": video_id,
        "cluster": cluster,
        "video_url": video_url,
        "likes": random.randint(50, 500)
    })


@app.route("/proxy_video/<int:video_id>")
def proxy_video(video_id):
    """Proxy endpoint to fetch video with HTTP Basic Auth"""
    video_url = f"{BASE_URL}{video_id}.mp4"
    
    try:
        # Fetch video with authentication
        response = requests.get(
            video_url,
            auth=HTTPBasicAuth(DB_USERNAME, DB_PASSWORD),
            stream=True,
            timeout=30
        )
        
        if response.status_code == 200:
            # Stream the video back to client
            return Response(
                response.iter_content(chunk_size=8192),
                content_type=response.headers.get('content-type', 'video/mp4')
            )
        else:
            return jsonify({"error": "Video not found"}), 404
    except Exception as e:
        print(f"Error proxying video {video_id}: {str(e)}")
        return jsonify({"error": "Failed to fetch video"}), 500


if __name__ == "__main__":
    app.run()