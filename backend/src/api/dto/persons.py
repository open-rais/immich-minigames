"""Person-search DTOs - reusable across features, not game-specific (see api.py's
/persons/search)."""

from uuid import UUID

from pydantic import BaseModel

from domain.person import Person


class PersonSearchResultOut(BaseModel):
    id: UUID
    name: str

    @classmethod
    def from_person(cls, person: Person) -> "PersonSearchResultOut":
        return cls(id=person.id, name=person.name)


class PersonSearchOut(BaseModel):
    results: list[PersonSearchResultOut]

    @classmethod
    def from_persons(cls, persons: list[Person]) -> "PersonSearchOut":
        return cls(results=[PersonSearchResultOut.from_person(p) for p in persons])
