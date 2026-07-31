// Reusable across features (not just Immichdle's guess input) - mirrors backend/src/api/dto/
// persons.py - see backend/src/api/api.py's /persons/search.

export interface PersonSearchResultOut {
  id: string
  name: string
}

export interface PersonSearchOut {
  results: PersonSearchResultOut[]
}
