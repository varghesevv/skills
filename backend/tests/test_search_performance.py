"""Search speed check against many generated providers. Off by default.

Run with (from backend/):
  RUN_PERF_TESTS=1 PERF_PROVIDERS=100000 uv run pytest tests/test_search_performance.py -s
Target (docs/specification/07-non-functional.md): p95 under 500 ms with 100,000 freelancers.
"""

import os
import statistics
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.api_helpers import API
from tests.test_admission import headers_of
from tests.test_person_auth import add_member
from tests.trust_helpers import World

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_PERF_TESTS") != "1", reason="set RUN_PERF_TESTS=1 to run"
)

QUERIES = [
    "skill=plumbing&max_rate=60&currency=AED&sort=rate",
    "skill=plumbing&skill=electrical&skill_match=all&sort=rating",
    "language=English&timing=24h&negotiable=true",
    "min_rating=7&sort=rating",
    "",
]


def test_search_p95_under_half_a_second(client: TestClient, session: Session) -> None:
    count = int(os.environ.get("PERF_PROVIDERS", "20000"))
    world = World(session)
    viewer = add_member(world, "searcher")
    headers = headers_of(client, viewer)
    session.execute(
        text(
            """
            INSERT INTO people (status, church_id, home_group_id, full_name, email, mobile_number,
                                password_hash, rate_per_hour, rate_currency, is_rate_negotiable)
            SELECT 'provider', :church, :grp, 'Perf ' || g, 'perf' || g || '@example.com',
                   '+9716' || lpad(g::text, 8, '0'), 'unused', 10 + (g % 90), 'AED', (g % 3 = 0)
            FROM generate_series(1, :n) AS g
            """
        ),
        {"n": count, "church": world.church.id, "grp": world.group.id},
    )
    for label_type in ("skill", "language", "timing"):
        session.execute(
            text(
                """
                WITH l AS (
                    SELECT id, row_number() OVER (ORDER BY label_name) - 1 AS n,
                           count(*) OVER () AS total
                    FROM labels WHERE label_type = :t
                ),
                f AS (
                    SELECT id, row_number() OVER (ORDER BY id) AS g
                    FROM people WHERE email LIKE 'perf%'
                )
                INSERT INTO person_labels (person_id, label_id)
                SELECT f.id, l.id FROM f JOIN l ON l.n = f.g % l.total
                """
            ),
            {"t": label_type},
        )
    session.execute(
        text(
            """
            INSERT INTO ratings (rater_id, provider_id, rating)
            SELECT :rater, id, 1 + (row_number() OVER (ORDER BY id) % 10)
            FROM people WHERE email LIKE 'perf%' AND id::text < '8'
            """
        ),
        {"rater": viewer.person.id},
    )
    session.execute(text("ANALYZE"))

    timings: list[float] = []
    for _ in range(5):
        for query in QUERIES:
            started = time.perf_counter()
            response = client.get(f"{API}/search/freelancers?{query}", headers=headers)
            timings.append(time.perf_counter() - started)
            assert response.status_code == 200
    timings.sort()
    p95 = timings[int(len(timings) * 0.95) - 1]
    print(f"\n{count} providers: median {statistics.median(timings):.3f}s, p95 {p95:.3f}s")
    assert p95 < 0.5
