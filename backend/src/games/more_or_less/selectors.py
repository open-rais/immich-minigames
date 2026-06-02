import random
from typing import Iterable

from src.games.more_or_less.dto import PersonItem
from src.infraestructure.immich.provider import ImmichProvider


class PersonItemsSelector:
    def __init__(
        self,
        immich_provider: ImmichProvider,
        min_asset_count: int = 3,
        min_difference_ratio: float = 0.90,
        max_retries: int = 50,
    ) -> None:
        self.immich = immich_provider
        self.min_asset_count = min_asset_count
        self.min_difference_ratio = min_difference_ratio
        self.max_retries = max_retries

    async def select_person_pair(
        self,
        used_ids: Iterable[str] | None = None,
        forced_left_person_id: str | None = None,
    ) -> tuple[PersonItem, PersonItem]:

        used_ids = set(used_ids or [])

        people = await self.immich._load_people()

        valid = [
            self._to_person_item(p)
            for p in people
        ]

        if len(valid) < 2:
            valid = [self._to_person_item(p) for p in people]

        if len(valid) < 2:
            raise ValueError(
                f"Immich returned too few usable people: {len(people)}"
            )

        left = self._select_left(valid, forced_left_person_id)

        available = [
            p for p in valid
            if p.id != left.id and p.id not in used_ids
        ]

        # 🔥 fallback: si el filtro de usados deja vacío, relajamos used_ids
        if not available:
            available = [p for p in valid if p.id != left.id]

        if not available:
            raise ValueError("No available people")

        for _ in range(self.max_retries):
            right = random.choice(available)

            if self._is_good_match(left, right):
                return left, right

        # 🔥 fallback final: devolver cualquiera válida
        return left, random.choice(available)

    def _select_left(self, valid, forced_id):
        if forced_id:
            for p in valid:
                if p.id == forced_id:
                    return p
            # si el forced no existe, fallback silencioso
            return random.choice(valid)

        return random.choice(valid)

    def _is_good_match(self, left, right):
        ratio = abs(left.asset_count - right.asset_count) / max(
            left.asset_count,
            right.asset_count,
            1,
        )

        # 🔥 FIX PRINCIPAL: lógica correcta del juego
        # queremos pares similares o controlados, no imposibles
        return ratio <= self.min_difference_ratio

    def _to_person_item(self, dto) -> PersonItem:
        return PersonItem(
            id=dto.id,
            name=dto.name or "Unknown",
            thumbnail_url=getattr(dto, "thumbnail_url", None),
            asset_count=dto.asset_count or 0,
        )


# -------------------------
# API wrapper funcional
# -------------------------

_selector_cache = {}


def get_selector(immich: ImmichProvider) -> PersonItemsSelector:
    key = id(immich)
    if key not in _selector_cache:
        _selector_cache[key] = PersonItemsSelector(immich)
    return _selector_cache[key]


async def select_person_pair(
    immich_provider: ImmichProvider,
    used_ids: Iterable[str] | None = None,
    forced_left_person_id: str | None = None,
):
    selector = get_selector(immich_provider)

    return await selector.select_person_pair(
        used_ids=used_ids,
        forced_left_person_id=forced_left_person_id,
    )
