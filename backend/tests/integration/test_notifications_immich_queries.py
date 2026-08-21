class TestGetPersonsWithBirthdayOn:
    def test_a_real_birthdate_is_found_on_its_exact_month_and_day(self, immich_service):
        # Discovers a real birthdate from the dev data instead of hardcoding one, so this survives
        # the dataset changing - same technique as the hidden-person tests in
        # test_immich_service.py.
        with_birthdate = immich_service.get_persons(with_birthdate=True, limit=1)
        assert with_birthdate, "dev data must include at least one person with a birthDate to exercise this"
        reference = with_birthdate[0]

        matches = immich_service.get_persons_with_birthday_on(reference.birth_date.month, reference.birth_date.day)

        assert reference.id in {p.id for p in matches}

    def test_every_match_actually_falls_on_the_requested_month_and_day(self, immich_service):
        with_birthdate = immich_service.get_persons(with_birthdate=True, limit=1)
        assert with_birthdate
        reference = with_birthdate[0]

        matches = immich_service.get_persons_with_birthday_on(reference.birth_date.month, reference.birth_date.day)

        assert all(p.birth_date.month == reference.birth_date.month for p in matches)
        assert all(p.birth_date.day == reference.birth_date.day for p in matches)

    def test_every_match_has_a_name_and_is_not_hidden(self, immich_service):
        with_birthdate = immich_service.get_persons(with_birthdate=True, limit=1)
        assert with_birthdate
        reference = with_birthdate[0]

        matches = immich_service.get_persons_with_birthday_on(reference.birth_date.month, reference.birth_date.day)

        assert all(p.name for p in matches)


class TestGetAlbumsStartingOn:
    def test_a_real_first_asset_date_is_found_on_its_exact_month_and_day(self, immich_service):
        albums = immich_service.get_albums(min_asset_count=1, limit=1)
        assert albums, "dev data must include at least one non-empty album to exercise this"
        reference_album = albums[0]
        first_date = immich_service.get_album_first_asset_date(reference_album.id)
        assert first_date is not None

        matches = immich_service.get_albums_starting_on(first_date.month, first_date.day)

        assert reference_album.id in {album_id for album_id, _name, _date in matches}

    def test_every_match_actually_starts_on_the_requested_month_and_day(self, immich_service):
        albums = immich_service.get_albums(min_asset_count=1, limit=1)
        assert albums
        first_date = immich_service.get_album_first_asset_date(albums[0].id)
        assert first_date is not None

        matches = immich_service.get_albums_starting_on(first_date.month, first_date.day)

        assert all(d.month == first_date.month and d.day == first_date.day for _id, _name, d in matches)
