from datetime import date
from uuid import uuid4

import pytest


class TestGetAssets:
    def test_media_type_photo_returns_only_images(self, immich_service):
        assets = immich_service.get_assets(media_type="photo", limit=50)

        assert assets
        assert all(a.type == "IMAGE" for a in assets)

    def test_local_date_is_populated_as_a_calendar_day(self, immich_service):
        # localDateTime is NOT NULL in Immich, so every asset must carry a plain calendar day
        # (Dateguessr's answer key) - and it's the local day, which can differ from file_created_at's
        # UTC day for shots taken late in the local evening (see domain/asset.py's local_date).
        assets = immich_service.get_assets(limit=100)

        assert assets
        assert all(isinstance(a.local_date, date) for a in assets)

    def test_media_type_video_returns_only_videos(self, immich_service):
        assets = immich_service.get_assets(media_type="video", limit=50)

        assert assets
        assert all(a.type == "VIDEO" for a in assets)

    def test_with_location_true_excludes_assets_without_gps(self, immich_service):
        assets = immich_service.get_assets(with_location=True, limit=50)

        assert assets
        assert all(a.latitude is not None and a.longitude is not None for a in assets)

    def test_with_location_false_excludes_assets_with_gps(self, immich_service):
        assets = immich_service.get_assets(with_location=False, limit=50)

        assert assets
        assert all(a.latitude is None and a.longitude is None for a in assets)

    def test_respects_limit(self, immich_service):
        assets = immich_service.get_assets(limit=3)

        assert len(assets) == 3

    def test_excludes_given_ids(self, immich_service):
        [first] = immich_service.get_assets(limit=1)

        rest = immich_service.get_assets(limit=100, exclude_ids=frozenset({first.id}))

        assert first.id not in {a.id for a in rest}


class TestGetPersons:
    def test_named_only_excludes_blank_names(self, immich_service):
        persons = immich_service.get_persons(named_only=True, limit=100)

        assert persons
        assert all(p.name != "" for p in persons)

    def test_with_birthdate_true_excludes_persons_without_one(self, immich_service):
        persons = immich_service.get_persons(with_birthdate=True, named_only=False, limit=100)

        assert persons
        assert all(p.birth_date is not None for p in persons)

    def test_asset_count_is_populated(self, immich_service):
        persons = immich_service.get_persons(named_only=True, limit=100)

        assert persons
        assert any(p.asset_count > 0 for p in persons)
        assert all(p.asset_count >= 0 for p in persons)

    def test_min_asset_count_filters(self, immich_service):
        everyone = immich_service.get_persons(named_only=True, limit=100)
        threshold = max(p.asset_count for p in everyone)

        filtered = immich_service.get_persons(named_only=True, min_asset_count=threshold, limit=100)

        assert filtered
        assert all(p.asset_count >= threshold for p in filtered)

    def test_respects_limit(self, immich_service):
        persons = immich_service.get_persons(named_only=True, limit=3)

        assert len(persons) == 3

    def test_excludes_given_ids(self, immich_service):
        [first] = immich_service.get_persons(named_only=True, limit=1)

        rest = immich_service.get_persons(named_only=True, limit=100, exclude_ids=frozenset({first.id}))

        assert first.id not in {p.id for p in rest}

    def test_ids_filters_to_only_the_given_people(self, immich_service):
        everyone = immich_service.get_persons(named_only=True, limit=100)
        wanted = {everyone[0].id, everyone[1].id}

        matches = immich_service.get_persons(named_only=True, ids=frozenset(wanted), limit=100)

        assert {p.id for p in matches} == wanted

    def test_ids_with_unknown_id_returns_empty(self, immich_service):
        matches = immich_service.get_persons(named_only=True, ids=frozenset({uuid4()}), limit=100)

        assert matches == []


class TestGetPersonFirstAssetDate:
    def test_returns_a_date_for_a_person_with_assets(self, immich_service):
        persons = immich_service.get_persons(named_only=True, limit=100)
        person_with_assets = next(p for p in persons if p.asset_count > 0)

        first_date = immich_service.get_person_first_asset_date(person_with_assets.id)

        assert isinstance(first_date, date)

    def test_returns_none_for_unknown_person(self, immich_service):
        assert immich_service.get_person_first_asset_date(uuid4()) is None


class TestGetAssetsTogetherCount:
    def test_returns_zero_for_unrelated_people(self, immich_service):
        assert immich_service.get_assets_together_count(uuid4(), uuid4()) == 0

    def test_returns_a_non_negative_count_for_real_people(self, immich_service):
        [a, b] = immich_service.get_persons(named_only=True, limit=2)

        count = immich_service.get_assets_together_count(a.id, b.id)

        assert count >= 0


class TestSearchPersons:
    def test_single_letter_query_returns_results(self, immich_service):
        persons = immich_service.get_persons(named_only=True, limit=100)
        letter = persons[0].name[0].lower()

        results = immich_service.search_persons(letter, limit=50)

        assert results

    def test_matches_a_word_prefix_anywhere_in_the_name(self, immich_service):
        persons = immich_service.get_persons(named_only=True, limit=100)
        multi_word = next(p for p in persons if " " in p.name)
        last_word = multi_word.name.split(" ")[-1]
        query = last_word[:2]

        results = immich_service.search_persons(query, limit=100)

        assert multi_word.id in {p.id for p in results}

    def test_does_not_match_mid_word(self, immich_service):
        # e.g. "ar" must match "Argimiro Rodriguez" / "Juan Arturo" (word-prefix) but not "Martin
        # Perez" (mid-word) - build the same scenario from whatever real names the dev data has:
        # slice a 2-letter query out of the *middle* of some word, then confirm that word's owner
        # doesn't match on it (a different person coincidentally having a word start with the same
        # 2 letters is possible in principle, but vanishingly unlikely for a random mid-word slice).
        persons = immich_service.get_persons(named_only=True, limit=100)
        words = [(p, w) for p in persons for w in p.name.split(" ") if len(w) >= 4]
        assert words, "dev data needs at least one name with a word >=4 chars for this test"
        owner, long_word = words[0]
        mid_word_query = long_word[1:3]

        results = immich_service.search_persons(mid_word_query, limit=100)

        assert owner.id not in {p.id for p in results}

    def test_offset_and_limit_paginate_without_overlap(self, immich_service):
        all_matches = immich_service.search_persons("a", limit=100)
        if len(all_matches) < 4:
            pytest.skip("dev data needs at least 4 people matching 'a' for this pagination test")

        first_page = immich_service.search_persons("a", offset=0, limit=2)
        second_page = immich_service.search_persons("a", offset=2, limit=2)

        assert len(first_page) == 2
        assert len(second_page) == 2
        assert {p.id for p in first_page}.isdisjoint({p.id for p in second_page})

    def test_unknown_query_returns_empty(self, immich_service):
        assert immich_service.search_persons("zzzzzzzzzz_no_such_person", limit=10) == []

    def test_escapes_like_wildcards_in_the_query(self, immich_service):
        # A literal "%"/"_" in the search text must not behave as a SQL wildcard.
        assert immich_service.search_persons("%", limit=10) == []
        assert immich_service.search_persons("_", limit=10) == []
