"""Album-search DTOs - reusable across features, not game-specific (see api.py's
/albums/search). Mirrors api/dto/persons.py exactly."""

from uuid import UUID

from pydantic import BaseModel

from domain.album import Album


class AlbumSearchResultOut(BaseModel):
    id: UUID
    name: str

    @classmethod
    def from_album(cls, album: Album) -> "AlbumSearchResultOut":
        return cls(id=album.id, name=album.name)


class AlbumSearchOut(BaseModel):
    results: list[AlbumSearchResultOut]

    @classmethod
    def from_albums(cls, albums: list[Album]) -> "AlbumSearchOut":
        return cls(results=[AlbumSearchResultOut.from_album(a) for a in albums])
