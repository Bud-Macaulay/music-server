from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime
import os

# ==== CONFIG ====
MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "musicdb"
COLLECTION_NAME = "tracks"

# ==== INIT ====
app = FastAPI(title="Music API", version="1.0.0")

client = MongoClient(MONGO_URI)
db = client[DB_NAME]
collection = db[COLLECTION_NAME]


# ==== HELPERS ====
def serialize_doc(doc):
    if not doc:
        return None

    doc["id"] = str(doc["_id"])
    del doc["_id"]

    if isinstance(doc.get("date_added"), datetime):
        doc["date_added"] = doc["date_added"].isoformat()

    return doc


def build_search_query(
    query: Optional[str],
    artist: Optional[str],
    genre: Optional[str],
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
    id: str
    music_id: Optional[str]
    music_file: str
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

    results = [serialize_doc(doc) for doc in cursor]
    return results


@app.get("/tracks/{track_id}", response_model=TrackResponse)
def get_track(track_id: str):
    doc = collection.find_one({"_id": track_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Track not found")

    return serialize_doc(doc)


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
