
import os

from backend.agentdeal.auth import create_user
from backend.agentdeal.db import conn, init_db


# Read demo password from environment variable
PW = os.getenv("AGENTDEAL_DEMO_PASSWORD")

if not PW or len(PW) < 12:
    raise SystemExit(
        "Error: Set AGENTDEAL_DEMO_PASSWORD to a password "
        "containing at least 12 characters."
    )


# Demo marketplace listings
LISTINGS = [
    ("Logo design", 5000, 3200, 3, 8),
    ("Landing page website", 12000, 8000, 5, 12),
    ("Printed T-shirts (100 pcs)", 9000, 6500, 4, 9),
]


def seed_demo():
    # Initialize database
    init_db()

    # Create demo buyer and seller accounts
    demo_users = [
        ("Demo Buyer", "buyer@demo.test", "buyer"),
        ("Demo Seller", "seller@demo.test", "seller"),
    ]

    for name, email, role in demo_users:
        try:
            create_user(name, email, PW, role)
            print(f"Created demo account: {email}")
        except ValueError:
            print(f"Demo account already exists: {email}")

    # Create demo listings if they do not already exist
    with conn() as c:
        have = c.execute(
            """
            SELECT COUNT(*) AS n
            FROM listings
            WHERE owner_email = ?
            """,
            ("seller@demo.test",),
        ).fetchone()["n"]

        if have == 0:
            for product, ask, minimum, fastest, ideal in LISTINGS:
                c.execute(
                    """
                    INSERT INTO listings
                    (product, ask_price, min_price, fastest_days,
                     ideal_days, owner_email)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        product,
                        ask,
                        minimum,
                        fastest,
                        ideal,
                        "seller@demo.test",
                    ),
                )

            print(f"Created {len(LISTINGS)} demo listings.")
        else:
            print("Demo listings already exist.")

    print("Demo data seeding completed successfully.")


if __name__ == "__main__":
    seed_demo()
