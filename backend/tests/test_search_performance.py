"""Search speed check against many generated freelancers. Off by default.

Run with (from backend/):
  RUN_PERF_TESTS=1 PERF_FREELANCERS=100000 uv run pytest tests/test_search_performance.py -s
Target (docs/specification/07-non-functional.md): p95 under 500 ms with 100,000 freelancers.
"""

import os
import statistics
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.api_helpers import API, signup

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
    count = int(os.environ.get("PERF_FREELANCERS", "20000"))
    host = signup(client, session, "workhost", "perf.host@example.com")
    session.execute(
        text(
            """
            INSERT INTO freelancers (user_email, mobile_number, password_hash, rate_per_hour,
                                     rate_currency, is_rate_negotiable)
            SELECT 'perf' || g || '@example.com', '+971500000000', 'unused',
                   10 + (g % 90), 'AED', (g % 3 = 0)
            FROM generate_series(1, :n) AS g
            """
        ),
        {"n": count},
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
                    FROM freelancers WHERE user_email LIKE 'perf%'
                )
                INSERT INTO freelancer_labels (freelancer_id, label_id)
                SELECT f.id, l.id FROM f JOIN l ON l.n = f.g % l.total
                """
            ),
            {"t": label_type},
        )
    session.execute(
        text(
            """
            INSERT INTO user_ratings (work_host_id, freelancer_id, rating)
            SELECT :host, id, 1 + (row_number() OVER (ORDER BY id) % 10)
            FROM freelancers WHERE user_email LIKE 'perf%' AND id::text < '8'
            """
        ),
        {"host": host.id},
    )
    session.execute(text("ANALYZE"))

    timings: list[float] = []
    for _ in range(5):
        for query in QUERIES:
            started = time.perf_counter()
            response = client.get(f"{API}/search/freelancers?{query}", headers=host.headers)
            timings.append(time.perf_counter() - started)
            assert response.status_code == 200
    timings.sort()
    p95 = timings[int(len(timings) * 0.95) - 1]
    print(f"\n{count} freelancers: median {statistics.median(timings):.3f}s, p95 {p95:.3f}s")
    assert p95 < 0.5
