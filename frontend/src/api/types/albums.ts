// Reusable across features (not just Albumdle's guess input) - mirrors backend/src/api/dto/
// albums.py - see backend/src/api/api.py's /albums/search.

export interface AlbumSearchResultOut {
  id: string
  name: string
}

export interface AlbumSearchOut {
  results: AlbumSearchResultOut[]
}
