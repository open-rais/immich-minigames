from datetime import date


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
