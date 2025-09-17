import json
import os
import random
import threading
from typing import Dict, List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from contextlib import asynccontextmanager


# -------------------------------
# Persistent storage configuration
# -------------------------------
CURRENT_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", "data"))
USER_PROFILES_PATH = os.path.join(DATA_DIR, "user_profiles.json")
VIDEOS_BY_CLUSTER_PATH = os.path.join(DATA_DIR, "videos_by_cluster.json")
os.makedirs(DATA_DIR, exist_ok=True)


# -------------------------------
# In-memory state (backed by JSON)
# -------------------------------
user_profiles: Dict[str, Dict] = {}
profiles_lock = threading.RLock()


def load_user_profiles() -> None:
    """Load the user profiles dictionary from JSON if present, else initialize empty."""
    global user_profiles
    if os.path.exists(USER_PROFILES_PATH):
        try:
            with open(USER_PROFILES_PATH, "r", encoding="utf-8") as file_obj:
                data = json.load(file_obj)
                user_profiles = data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            # Corrupt or empty file; start fresh
            user_profiles = {}
    else:
        user_profiles = {}


def save_user_profiles() -> None:
    """Persist the current in-memory user profiles dictionary to JSON."""
    # Write atomically via a temp file then replace
    tmp_path = USER_PROFILES_PATH + ".tmp"
    with profiles_lock:
        with open(tmp_path, "w", encoding="utf-8") as file_obj:
            json.dump(user_profiles, file_obj, ensure_ascii=False, indent=2)
        os.replace(tmp_path, USER_PROFILES_PATH)


# -------------------------------
# Pydantic request models
# -------------------------------
class CreateUserRequest(BaseModel):
    username: str


class InteractionRequest(BaseModel):
    pid: int
    cluster_label: int


# -------------------------------
# Helpers
# -------------------------------
def get_user_or_404(username: str) -> Dict:
    profile = user_profiles.get(username)
    if profile is None:
        raise HTTPException(status_code=404, detail="User not found")
    return profile


def get_videos_by_cluster() -> Dict[str, List[int]]:
    if not os.path.exists(VIDEOS_BY_CLUSTER_PATH):
        return {}
    with open(VIDEOS_BY_CLUSTER_PATH, "r", encoding="utf-8") as file_obj:
        data = json.load(file_obj)
    # Normalize keys to string cluster labels, values to list[int]
    normalized: Dict[str, List[int]] = {}
    for key, value in (data or {}).items():
        try:
            str_key = str(int(key))
        except Exception:
            str_key = str(key)
        normalized[str_key] = [int(v) for v in value]
    return normalized


# -------------------------------
# FastAPI app and lifecycle hooks
# -------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    load_user_profiles()
    yield
    # Shutdown: nothing needed; data is saved on each change


app = FastAPI(title="Video Recommender API", lifespan=lifespan)


# -------------------------------
# API endpoints
# -------------------------------
@app.post("/users/")
def create_user(request: CreateUserRequest) -> Dict:
    username = request.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="Username is required")

    with profiles_lock:
        if username not in user_profiles:
            user_profiles[username] = {
                "username": username,
                "cluster_interactions": {},  # str(cluster_label) -> count
                "seen_videos": [],           # list[int]
            }
            save_user_profiles()
    return user_profiles[username]


@app.get("/users/{username}/")
def get_user(username: str) -> Dict:
    return get_user_or_404(username)


@app.post("/users/{username}/interaction/")
def record_interaction(username: str, request: InteractionRequest) -> Dict[str, str]:
    with profiles_lock:
        profile = get_user_or_404(username)
        cluster_key = str(request.cluster_label)
        profile.setdefault("cluster_interactions", {})
        profile["cluster_interactions"][cluster_key] = (
            profile["cluster_interactions"].get(cluster_key, 0) + 1
        )
        # Track seen videos without duplicates
        if request.pid not in profile.setdefault("seen_videos", []):
            profile["seen_videos"].append(request.pid)
        save_user_profiles()
    return {"status": "ok"}


@app.get("/users/{username}/recommendations/")
def get_recommendations(username: str) -> Dict[str, List[int]]:
    profile = get_user_or_404(username)
    interactions: Dict[str, int] = profile.get("cluster_interactions", {})
    seen: set[int] = set(profile.get("seen_videos", []))

    videos_by_cluster = get_videos_by_cluster()
    if not videos_by_cluster:
        return {"recommendations": []}

    # Sort clusters by user's interaction count (desc)
    sorted_clusters = sorted(
        videos_by_cluster.keys(), key=lambda c: interactions.get(c, 0), reverse=True
    )

    recommendations: List[int] = []

    # Choose up to 7 videos from preferred clusters, skipping seen/duplicates
    for cluster in sorted_clusters:
        candidates = [
            pid for pid in videos_by_cluster.get(cluster, [])
            if pid not in seen and pid not in recommendations
        ]
        random.shuffle(candidates)
        for pid in candidates:
            if len(recommendations) >= 7:
                break
            recommendations.append(pid)
        if len(recommendations) >= 7:
            break

    # Add 1 exploration video from anywhere (not seen and not already included)
    all_candidates: List[int] = []
    for video_list in videos_by_cluster.values():
        all_candidates.extend(video_list)
    exploration_pool = [
        pid for pid in set(all_candidates) if pid not in seen and pid not in recommendations
    ]
    if exploration_pool:
        recommendations.append(random.choice(exploration_pool))

    return {"recommendations": recommendations[:8]}


