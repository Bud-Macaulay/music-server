from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List
from pymongo import MongoClient
from datetime import datetime
import os

# ==== CONFIG ====
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME = "musicdb"
COLLECTION_NAME = "tracks"

# ==== INIT ====
app = FastAPI(title="Music API", version="1.0.0")

client = MongoClient(MONGO_URI)
db = client[DB_NAME]
collection = db[COLLECTION_NAME]

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://music-frontend:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
    "http://music-frontend:4173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==== HELPERS ====
def serialize_track(doc):
    """Return only safe, public fields to the frontend"""
    if not doc:
        return None
    return {
        "music_id": doc.get("music_id"),
        "title": doc.get("title"),
        "artist": doc.get("artist"),
        "album": doc.get("album"),
        "genres": doc.get("genres", []),
        "release_date": doc.get("release_date"),
        "audio_features": doc.get("audio_features", {}),
        "sources": doc.get("sources", {}),
        "date_added": doc.get("date_added").isoformat()
        if isinstance(doc.get("date_added"), datetime)
        else None,
        "notes": doc.get("notes"),
    }


def build_search_query(
    query: Optional[str], artist: Optional[str], genre: Optional[str]
):
    filters = {}

    if query:
        filters["$or"] = [
            {"title_lower": {"$regex": query.lower()}},
            {"artist_lower": {"$regex": query.lower()}},
            {"album_lower": {"$regex": query.lower()}},
        ]
    if artist:
        filters["artist_lower"] = {"$regex": artist.lower()}
    if genre:
        filters["genres_lower"] = {"$regex": genre.lower()}

    return filters


# ==== MODELS ====
class TrackResponse(BaseModel):
    music_id: Optional[str]  # <- optional now
    title: str
    artist: str
    album: Optional[str]
    genres: List[str] = []
    release_date: Optional[str]
    audio_features: dict
    sources: dict
    date_added: Optional[str]
    notes: Optional[str]


# ==== ROUTES ====


@app.get("/")
def root():
    return {"status": "ok", "message": "Music API running"}


@app.get("/tracks", response_model=List[TrackResponse])
def list_tracks(
    query: Optional[str] = Query(None),
    artist: Optional[str] = Query(None),
    genre: Optional[str] = Query(None),
    limit: int = Query(50, le=500),
):
    mongo_query = build_search_query(query, artist, genre)
    cursor = collection.find(mongo_query).limit(limit)
    return [serialize_track(doc) for doc in cursor]


@app.get("/tracks/{music_id}", response_model=TrackResponse)
def get_track_by_music_id(music_id: str):
    doc = collection.find_one({"music_id": music_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Track not found")
    return serialize_track(doc)


@app.get("/tracks/file/{music_id}")
def stream_track_file(music_id: str):
    doc = collection.find_one({"music_id": music_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Track not found")
    return FileResponse(doc["music_file"], filename=f"{doc.get('title')}.mp3")


@app.get("/artists")
def list_artists():
    artists = collection.distinct("artist")
    return sorted(a for a in artists if a)


@app.get("/genres")
def list_genres():
    genres = collection.distinct("genres")
    flat = set()
    for g in genres:
        if isinstance(g, list):
            flat.update(g)
        else:
            flat.add(g)
    return sorted(flat)


@app.get("/stats")
def stats():
    return {
        "total_tracks": collection.count_documents({}),
        "total_artists": len(collection.distinct("artist")),
        "total_genres": len(collection.distinct("genres")),
    }
