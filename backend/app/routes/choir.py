from fastapi import APIRouter

router = APIRouter(
    prefix="/choir",
    tags=["Choir"]
)

songs = []

@router.get("/")
def get_songs():
    return songs

@router.post("/")
def add_song(song: dict):

    songs.append(song)

    return {
        "message": "song added",
        "song": song
    }