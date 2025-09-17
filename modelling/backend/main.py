import json
import os
import random
import threading
from contextlib import asynccontextmanager
from typing import Dict, List, Tuple, Any

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


# -------------------------------
# Persistent storage configuration
# -------------------------------
CURRENT_DIR: str = os.path.dirname(__file__)
DATA_DIR: str = os.path.abspath(os.path.join(CURRENT_DIR, "..", "data"))
USER_PROFILES_PATH: str = os.path.join(DATA_DIR, "user_profiles.json")
VIDEOS_BY_CLUSTER_PATH: str = os.path.join(DATA_DIR, "videos_by_cluster.json")
COMMENTS_PATH: str = os.path.join(DATA_DIR, "comments.json")
os.makedirs(DATA_DIR, exist_ok=True)


# -------------------------------
# In-memory state (backed by JSON)
# -------------------------------
user_profiles: Dict[str, Dict[str, Any]] = {}
profiles_lock: threading.RLock = threading.RLock()
comments_lock: threading.RLock = threading.RLock()


def load_user_profiles() -> None:
    """Load user profiles from JSON into memory.

    Side effects:
        Populates the module-level `user_profiles` dictionary.
    """
    global user_profiles
    if os.path.exists(USER_PROFILES_PATH):
        try:
            with open(USER_PROFILES_PATH, "r", encoding="utf-8") as file_obj:
                data = json.load(file_obj)
                user_profiles = data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            user_profiles = {}
    else:
        user_profiles = {}


def save_user_profiles() -> None:
    """Persist the current in-memory user profiles to JSON atomically."""
    tmp_path: str = USER_PROFILES_PATH + ".tmp"
    with profiles_lock:
        with open(tmp_path, "w", encoding="utf-8") as file_obj:
            json.dump(user_profiles, file_obj, ensure_ascii=False, indent=2)
        os.replace(tmp_path, USER_PROFILES_PATH)


class CreateUserRequest(BaseModel):
    """Request payload for creating a user."""
    username: str


class InteractionRequest(BaseModel):
    """Request payload for recording a user interaction (like)."""
    pid: int
    cluster_label: int


class CommentCreate(BaseModel):
    """Request payload for posting a new comment on a video."""
    username: str
    text: str


def get_user_or_404(username: str) -> Dict[str, Any]:
    """Return the user's profile or raise 404 if not found.

    Args:
        username: The user's unique identifier.

    Returns:
        The user profile dictionary.
    """
    profile = user_profiles.get(username)
    if profile is None:
        raise HTTPException(status_code=404, detail="User not found")
    return profile


def get_videos_by_cluster() -> Dict[str, List[int]]:
    """Load the cluster-to-video mapping from JSON.

    Returns:
        A dictionary mapping string cluster labels to lists of PIDs.
    """
    if not os.path.exists(VIDEOS_BY_CLUSTER_PATH):
        return {}
    with open(VIDEOS_BY_CLUSTER_PATH, "r", encoding="utf-8") as file_obj:
        data = json.load(file_obj)
    normalized: Dict[str, List[int]] = {}
    for key, value in (data or {}).items():
        try:
            str_key = str(int(key))
        except Exception:
            str_key = str(key)
        normalized[str_key] = [int(v) for v in value]
    return normalized


def build_pid_to_cluster_map(videos_by_cluster: Dict[str, List[int]]) -> Dict[int, int]:
    """Build a reverse index from PID to cluster label.

    Args:
        videos_by_cluster: Mapping of cluster label to PIDs.

    Returns:
        A dictionary mapping PID to its cluster label (int).
    """
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
    """Load the comments store from disk.

    Returns:
        Mapping from PID (as string) to list of comments.
    """
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
    """Persist the comments store atomically.

    Args:
        store: The full comments mapping to write.
    """
    tmp_path = COMMENTS_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, COMMENTS_PATH)


def recommend_with_priority_pattern(
    username: str,
    interactions: Dict[str, int],
    seen: List[int],
    videos_by_cluster: Dict[str, List[int]],
    num_items: int = 8,
) -> List[Dict[str, int]]:
    """Generate recommendations using a 2-regular + 1-priority repeating pattern.

    The priority item is drawn from the user's most-interacted cluster.

    Args:
        username: The user to recommend for (unused but helpful for future personalization hooks).
        interactions: Mapping of cluster label (as string) to interaction counts.
        seen: List of PIDs the user has already seen.
        videos_by_cluster: Mapping of cluster labels (as strings) to available PIDs.
        num_items: Number of recommendation items to produce.

    Returns:
        A list of dicts, each with keys: {"pid": int, "cluster_label": int}.
    """
    pid_to_cluster = build_pid_to_cluster_map(videos_by_cluster)
    sorted_clusters = sorted(
        videos_by_cluster.keys(), key=lambda c: interactions.get(c, 0), reverse=True
    )

    seen_set = set(seen)
    all_candidates: List[int] = []
    for video_list in videos_by_cluster.values():
        all_candidates.extend(video_list)
    random.shuffle(all_candidates)

    top_cluster = sorted_clusters[0] if sorted_clusters else None
    priority_pool = [
        pid for pid in videos_by_cluster.get(top_cluster, [])
        if pid not in seen_set
    ] if top_cluster is not None else []
    random.shuffle(priority_pool)

    regular_pool = [pid for pid in all_candidates if pid not in seen_set]

    ordered: List[int] = []
    while len(ordered) < num_items and (regular_pool or priority_pool):
        # Two regular
        for _ in range(2):
            if len(ordered) >= num_items:
                break
            while regular_pool and (regular_pool[0] in ordered):
                regular_pool.pop(0)
            if regular_pool:
                ordered.append(regular_pool.pop(0))
        if len(ordered) >= num_items:
            break
        # One priority
        while priority_pool and (priority_pool[0] in ordered):
            priority_pool.pop(0)
        if priority_pool:
            ordered.append(priority_pool.pop(0))

    items: List[Dict[str, int]] = []
    for pid in ordered[:num_items]:
        items.append({
            "pid": int(pid),
            "cluster_label": int(pid_to_cluster.get(int(pid), -1)),
        })
    return items


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan hook to load in-memory data on startup."""
    load_user_profiles()
    yield


app = FastAPI(title="Video Recommender API", lifespan=lifespan)

# CORS for local frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> Dict[str, str]:
    """Health endpoint providing minimal service discovery."""
    return {"status": "ok", "message": "Video Recommender API", "docs": "/docs"}


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    """Return an empty favicon response to avoid 404s in logs."""
    return Response(status_code=204)


@app.post("/users/")
def create_user(request: CreateUserRequest) -> Dict[str, Any]:
    """Create a user if not present; return the user profile.

    Args:
        request: Body containing the desired username.

    Returns:
        The up-to-date user profile.
    """
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
def get_user(username: str) -> Dict[str, Any]:
    """Return an existing user's profile."""
    return get_user_or_404(username)


@app.post("/users/{username}/interaction/")
def record_interaction(username: str, request: InteractionRequest) -> Dict[str, str]:
    """Record a positive interaction (like) for a given user and video.

    Increments the interaction count for the video's cluster, tracks the video
    as seen, and appends it to the liked list if not present.
    """
    with profiles_lock:
        profile = get_user_or_404(username)
        cluster_key = str(request.cluster_label)
        profile.setdefault("cluster_interactions", {})
        profile["cluster_interactions"][cluster_key] = (
            profile["cluster_interactions"].get(cluster_key, 0) + 1
        )
        if request.pid not in profile.setdefault("seen_videos", []):
            profile["seen_videos"].append(request.pid)
        liked = profile.setdefault("liked_videos", [])
        if request.pid not in liked:
            liked.append(request.pid)
        save_user_profiles()
    return {"status": "ok"}


@app.get("/users/{username}/recommendations/")
def get_recommendations(username: str) -> Dict[str, List[Dict[str, int]]]:
    """Return a list of recommendations following the 2+1 priority pattern."""
    profile = get_user_or_404(username)
    interactions: Dict[str, int] = profile.get("cluster_interactions", {})
    seen: List[int] = profile.get("seen_videos", [])
    videos_by_cluster = get_videos_by_cluster()
    if not videos_by_cluster:
        return {"recommendations": []}
    items = recommend_with_priority_pattern(
        username=username,
        interactions=interactions,
        seen=seen,
        videos_by_cluster=videos_by_cluster,
        num_items=8,
    )
    return {"recommendations": items}


@app.get("/videos/{pid}/comments")
def get_comments(pid: int) -> Dict[str, List[Dict[str, str]]]:
    """Return the list of comments for a given video PID."""
    key = str(int(pid))
    with comments_lock:
        store = load_comments_store()
        comments = store.get(key, [])
        return {"comments": comments}


@app.post("/videos/{pid}/comments")
def post_comment(pid: int, request: CommentCreate) -> Dict[str, str]:
    """Append a comment for a given video PID and persist it to disk."""
    key = str(int(pid))
    comment = {"username": request.username.strip(), "text": request.text.strip()}
    if not comment["username"] or not comment["text"]:
        raise HTTPException(status_code=400, detail="username and text are required")
    with comments_lock:
        store = load_comments_store()
        store.setdefault(key, []).append(comment)
        save_comments_store(store)
    return {"status": "ok"}


