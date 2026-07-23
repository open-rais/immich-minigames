from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import select

from persistence.immich_tables import person


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

    def test_random_true_still_respects_limit(self, immich_service):
        persons = immich_service.get_persons(named_only=True, randomize=True, limit=5)

        assert len(persons) == 5

    def test_asset_count_weight_of_zero_does_not_error(self, immich_service):
        persons = immich_service.get_persons(named_only=True, randomize=True, asset_count_weight=0, limit=1)

        assert len(persons) == 1

    def test_asset_count_weight_biases_towards_higher_asset_count(self, immich_service):
        """w=1 (peso = c_fotos ^ w) should make the person with far more photos win almost every
        draw against one with far fewer - checked by restricting the candidate pool to exactly
        those two (via ids=) rather than asserting anything about the full random distribution,
        so this can't flake on an ordinary shuffle of similar-sized candidates."""
        everyone = immich_service.get_persons(named_only=True, limit=500)
        highest = max(everyone, key=lambda p: p.asset_count)
        lowest = min(everyone, key=lambda p: p.asset_count)
        assert highest.asset_count > lowest.asset_count * 10  # real dev data has enough spread

        picks = [
            immich_service.get_persons(
                named_only=True,
                randomize=True,
                asset_count_weight=1.0,
                ids=frozenset({highest.id, lowest.id}),
                limit=1,
            )[0].id
            for _ in range(30)
        ]

        assert picks.count(highest.id) > picks.count(lowest.id)


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


class TestGetRandomAssetWithNamedFaces:
    def test_returns_faces_for_a_named_person(self, immich_service):
        faces = immich_service.get_random_asset_with_named_faces(max_faces=5)

        assert faces
        assert all(face.person_name != "" for face in faces)
        assert len({face.asset_id for face in faces}) == 1, "every returned face must belong to the same asset"

    def test_respects_max_faces(self, immich_service):
        faces = immich_service.get_random_asset_with_named_faces(max_faces=1)

        assert len(faces) == 1

    def test_bounding_box_and_image_size_are_populated(self, immich_service):
        [face] = immich_service.get_random_asset_with_named_faces(max_faces=1)

        assert face.image_width > 0
        assert face.image_height > 0
        assert face.bounding_box_x2 > face.bounding_box_x1
        assert face.bounding_box_y2 > face.bounding_box_y1

    def test_excludes_given_asset_ids(self, immich_service):
        [face] = immich_service.get_random_asset_with_named_faces(max_faces=1)

        rest = immich_service.get_random_asset_with_named_faces(
            max_faces=1, exclude_asset_ids=frozenset({face.asset_id})
        )

        assert rest == [] or rest[0].asset_id != face.asset_id

    def test_returns_empty_when_no_eligible_asset_exists(self, immich_service):
        # Excluding a huge batch of already-eligible assets should eventually exhaust the pool -
        # the dev data has far fewer than 100000 assets with a named face.
        excluded = set()
        for _ in range(1000):
            faces = immich_service.get_random_asset_with_named_faces(max_faces=1, exclude_asset_ids=frozenset(excluded))
            if not faces:
                return
            excluded.add(faces[0].asset_id)
        pytest.fail("never ran out of eligible assets after excluding 1000 distinct ones")

    def test_never_returns_faces_of_hidden_people(self, immich_service, immich_engine):
        # A hidden person (Immich's own isHidden flag) never shows up in search_persons/get_persons,
        # so a round that blacked out their face would be unguessable - see the dev data's
        # "Enrique Waugh"/"Emi Sandoval"/"Vivi Blanlot" and the two assets whose only named face is
        # one of them. Walk the whole eligible-asset pool (same exhaustion pattern as
        # test_returns_empty_when_no_eligible_asset_exists) so this exercises those assets, not just
        # whichever one random() happens to land on.
        with immich_engine.connect() as conn:
            hidden_ids = {row.id for row in conn.execute(select(person.c.id).where(person.c.isHidden.is_(True)))}
        assert hidden_ids, "dev data must include at least one hidden named person to exercise this"

        excluded = set()
        for _ in range(1000):
            faces = immich_service.get_random_asset_with_named_faces(max_faces=5, exclude_asset_ids=frozenset(excluded))
            if not faces:
                return
            assert all(face.person_id not in hidden_ids for face in faces)
            excluded.add(faces[0].asset_id)
        pytest.fail("never ran out of eligible assets after excluding 1000 distinct ones")


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

    def test_matches_multiple_tokens_regardless_of_order(self, immich_service):
        # e.g. "rai rodriguez" must match "Raimundo Rodriguez" - each token prefixes a different
        # word in the name, and the order they're typed in doesn't have to match the name's order.
        persons = immich_service.get_persons(named_only=True, limit=100)
        multi_word = next(p for p in persons if len(p.name.split(" ")) >= 2)
        first_word, last_word = multi_word.name.split(" ")[0], multi_word.name.split(" ")[-1]
        reversed_query = f"{last_word[:2]} {first_word[:2]}"

        results = immich_service.search_persons(reversed_query, limit=100)

        assert multi_word.id in {p.id for p in results}

    def test_every_token_must_match_a_word(self, immich_service):
        # AND semantics, not OR - a real prefix plus a garbage token must exclude the person that
        # only the real prefix would have matched on its own.
        persons = immich_service.get_persons(named_only=True, limit=100)
        multi_word = next(p for p in persons if " " in p.name)
        first_word = multi_word.name.split(" ")[0]

        results = immich_service.search_persons(f"{first_word[:2]} zzzzzzzzzz_no_such_word", limit=100)

        assert results == []

    def test_matches_regardless_of_accents(self, immich_service):
        # e.g. querying "Rodríguez" (or "Rodriguez") must match a stored name spelled the other
        # way - fold both sides of the comparison the same way search_persons does internally.
        persons = immich_service.get_persons(named_only=True, limit=100)
        accented_word = next(
            (w for p in persons for w in p.name.split(" ") if any(c in w for c in "áéíóúÁÉÍÓÚñÑüÜ")),
            None,
        )
        if accented_word is None:
            pytest.skip("dev data needs at least one accented name to exercise accent-folding")

        owner = next(p for p in persons if accented_word in p.name.split(" "))
        folded_query = accented_word[:3].translate(str.maketrans("áéíóúÁÉÍÓÚñÑüÜ", "aeiouAEIOUnNuU"))

        results = immich_service.search_persons(folded_query, limit=100)

        assert owner.id in {p.id for p in results}
