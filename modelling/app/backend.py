import json
import os
import random
import threading
from typing import Dict, List

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager


# -------------------------------
# Persistent storage configuration
# -------------------------------
CURRENT_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", "data"))
USER_PROFILES_PATH = os.path.join(DATA_DIR, "user_profiles.json")
VIDEOS_BY_CLUSTER_PATH = os.path.join(DATA_DIR, "videos_by_cluster.json")
COMMENTS_PATH = os.path.join(DATA_DIR, "comments.json")
os.makedirs(DATA_DIR, exist_ok=True)


# -------------------------------
# In-memory state (backed by JSON)
# -------------------------------
user_profiles: Dict[str, Dict] = {}
profiles_lock = threading.RLock()
comments_lock = threading.RLock()


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


class CommentCreate(BaseModel):
    username: str
    text: str


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


def build_pid_to_cluster_map(videos_by_cluster: Dict[str, List[int]]) -> Dict[int, int]:
    mapping: Dict[int, int] = {}
    for cluster_str, pids in videos_by_cluster.items():
        try:
            cluster_int = int(cluster_str)
        except Exception:
            continue
        for pid in pids:
            mapping[int(pid)] = cluster_int
    return mapping


def load_comments_store() -> Dict[str, List[Dict[str, str]]]:
    if os.path.exists(COMMENTS_PATH):
        try:
            with open(COMMENTS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except json.JSONDecodeError:
            return {}
    return {}


def save_comments_store(store: Dict[str, List[Dict[str, str]]]) -> None:
    tmp_path = COMMENTS_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, COMMENTS_PATH)


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

# CORS for local frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------------
# API endpoints
# -------------------------------
@app.get("/")
def root() -> Dict[str, str]:
    return {"status": "ok", "message": "Video Recommender API", "docs": "/docs"}


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=204)

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
                "liked_videos": [],          # list[int]
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
        # Also record like into liked_videos if not present
        liked = profile.setdefault("liked_videos", [])
        if request.pid not in liked:
            liked.append(request.pid)
        save_user_profiles()
    return {"status": "ok"}


@app.get("/users/{username}/recommendations/")
def get_recommendations(username: str) -> Dict[str, List[Dict[str, int]]]:
    profile = get_user_or_404(username)
    interactions: Dict[str, int] = profile.get("cluster_interactions", {})
    seen: set[int] = set(profile.get("seen_videos", []))

    videos_by_cluster = get_videos_by_cluster()
    if not videos_by_cluster:
        return {"recommendations": []}

    pid_to_cluster = build_pid_to_cluster_map(videos_by_cluster)

    # Sort clusters by user's interaction count (desc)
    sorted_clusters = sorted(
        videos_by_cluster.keys(), key=lambda c: interactions.get(c, 0), reverse=True
    )

    recommendations: List[int] = []

    # Build pools
    all_candidates: List[int] = []
    for video_list in videos_by_cluster.values():
        all_candidates.extend(video_list)
    random.shuffle(all_candidates)

    # Determine top cluster for priority picks
    top_cluster = sorted_clusters[0] if sorted_clusters else None
    priority_pool = [
        pid for pid in videos_by_cluster.get(top_cluster, [])
        if pid not in seen
    ] if top_cluster is not None else []
    random.shuffle(priority_pool)

    # Regular pool excludes seen and will be used for non-priority slots
    regular_pool = [pid for pid in all_candidates if pid not in seen]

    # Fill 8 slots with 2 regular + 1 priority pattern
    slot = 0
    while len(recommendations) < 8 and (regular_pool or priority_pool):
        # Two regular
        for _ in range(2):
            if len(recommendations) >= 8:
                break
            while regular_pool and (regular_pool[0] in recommendations):
                regular_pool.pop(0)
            if regular_pool:
                recommendations.append(regular_pool.pop(0))
        if len(recommendations) >= 8:
            break
        # One priority
        while priority_pool and (priority_pool[0] in recommendations):
            priority_pool.pop(0)
        if priority_pool:
            recommendations.append(priority_pool.pop(0))
        slot += 1

    # Convert to list of objects with cluster labels
    items: List[Dict[str, int]] = []
    for pid in recommendations[:8]:
        items.append({
            "pid": int(pid),
            "cluster_label": int(pid_to_cluster.get(int(pid), -1)),
        })

    return {"recommendations": items}


# -------------------------------
# Comments endpoints
# -------------------------------
@app.get("/videos/{pid}/comments")
def get_comments(pid: int) -> Dict[str, List[Dict[str, str]]]:
    key = str(int(pid))
    with comments_lock:
        store = load_comments_store()
        comments = store.get(key, [])
        return {"comments": comments}


@app.post("/videos/{pid}/comments")
def post_comment(pid: int, request: CommentCreate) -> Dict[str, str]:
    key = str(int(pid))
    comment = {"username": request.username.strip(), "text": request.text.strip()}
    if not comment["username"] or not comment["text"]:
        raise HTTPException(status_code=400, detail="username and text are required")
    with comments_lock:
        store = load_comments_store()
        store.setdefault(key, []).append(comment)
        save_comments_store(store)
    return {"status": "ok"}