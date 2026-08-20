"""GameFactory.kwargs_for's reports-exclusion wiring - integration tests against the real dev
Immich DB (see conftest.py's module docstring). The rest of GameFactory's behavior (which kwargs
each concrete game class needs) is already exercised end-to-end via test_games_service.py; this
file is scoped to the one thing added for reports: that the content source it hands to a game is
actually filtered by services/reports_service.py::ReportsService.filter_for."""

import uuid

from games.more_or_less import GAME_TYPE as MORE_OR_LESS_TYPE
from games.more_or_less import MODE_PERSON_ASSETS
from games.registry import GAMES
from persistence.users import UserModel


def _make_reporter(session) -> UserModel:
    unique = uuid.uuid4().hex[:8]
    user = UserModel(
        email=f"factory-report-{unique}@example.com",
        username=f"factory-report-{unique}",
        full_name="Factory Report Test User",
        password_hash="irrelevant",
    )
    session.add(user)
    session.commit()
    return user


class TestKwargsForAppliesReportsExclusion:
    def test_reported_person_never_sampled_for_more_or_less_person_assets(
        self, game_factory, reports_service, immich_service, db_session
    ):
        people = immich_service.get_persons(named_only=True, limit=2)
        assert len(people) >= 2, "dev data must include at least two named people to exercise this"
        reported, _other = people
        reporter = _make_reporter(db_session)
        reports_service.create(reporter.id, "person", reported.id, ["person_name_face_mismatch"], None)

        spec = GAMES[(MORE_OR_LESS_TYPE, MODE_PERSON_ASSETS)]
        kwargs = game_factory.kwargs_for(spec, MORE_OR_LESS_TYPE, MODE_PERSON_ASSETS)
        candidates = kwargs["provider"].sample(limit=1000, exclude_ids=frozenset())

        assert reported.id not in {c.id for c in candidates}
