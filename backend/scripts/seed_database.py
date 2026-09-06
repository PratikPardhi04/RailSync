import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime, timedelta
from app.database.connection import SessionLocal, init_db
from app.models.models import User, Train
from app.auth.security import hash_password


# ---------------------------------------------------------------------------
# Busy, real-life Pune - Mumbai corridor demo corpus.
#
# The mainline section "Shivajinagar - Khadki" carries ~30 trains/day in both
# directions (premium expresses, intercity, locals, freight). Any daytime
# maintenance block catches several of them - and with the congestion-aware
# delay model, premium trains push the hard-conflict gate to replan while the
# express/passenger trains get held or DIVERTed via the network-registered
# Yerwada diversion (ALT-SK-1).
# ---------------------------------------------------------------------------
DEMO_TRAINS = [
    # --- Shivajinagar - Khadki (busy mainline corridor) ---------------------
    dict(train_number="11009", train_name="Sinhagad Express", train_type="Express", priority="EXPRESS", origin="Pune", destination="Mumbai CST", section="Shivajinagar - Khadki", arrival_time="06:10", departure_time="06:15", average_speed=90),
    dict(train_number="51317", train_name="Pune Local", train_type="Passenger", priority="PASSENGER", origin="Pune", destination="Mumbai CST", section="Shivajinagar - Khadki", arrival_time="07:05", departure_time="07:10", average_speed=60),
    dict(train_number="12127", train_name="Intercity Express", train_type="Express", priority="EXPRESS", origin="Pune", destination="Mumbai CST", section="Shivajinagar - Khadki", arrival_time="08:15", departure_time="08:20", average_speed=100),
    dict(train_number="12951", train_name="Mumbai Rajdhani", train_type="Rajdhani", priority="RAJDHANI", origin="New Delhi", destination="Mumbai CST", section="Shivajinagar - Khadki", arrival_time="08:35", departure_time="08:40", average_speed=130),
    dict(train_number="12025", train_name="Shatabdi Express", train_type="Shatabdi", priority="SHATABDI", origin="Pune", destination="Mumbai CST", section="Shivajinagar - Khadki", arrival_time="09:10", departure_time="09:15", average_speed=120),
    dict(train_number="11039", train_name="Maharashtra Express", train_type="Express", priority="EXPRESS", origin="Gondia", destination="Mumbai CST", section="Shivajinagar - Khadki", arrival_time="09:30", departure_time="09:35", average_speed=85),
    dict(train_number="12125", train_name="Pragati Express", train_type="Superfast", priority="SUPERFAST", origin="Pune", destination="Mumbai CST", section="Shivajinagar - Khadki", arrival_time="10:10", departure_time="10:15", average_speed=110),
    dict(train_number="22219", train_name="Vande Bharat Express", train_type="Vande Bharat", priority="VANDE_BHARAT", origin="Pune", destination="Mumbai CST", section="Shivajinagar - Khadki", arrival_time="11:00", departure_time="11:05", average_speed=140),
    dict(train_number="11010", train_name="Sinhagad Express", train_type="Express", priority="EXPRESS", origin="Mumbai CST", destination="Pune", section="Shivajinagar - Khadki", arrival_time="11:30", departure_time="11:35", average_speed=90),
    dict(train_number="12128", train_name="Intercity Express", train_type="Express", priority="EXPRESS", origin="Mumbai CST", destination="Pune", section="Shivajinagar - Khadki", arrival_time="12:05", departure_time="12:10", average_speed=100),
    dict(train_number="11020", train_name="Mumbai Mail", train_type="Express", priority="EXPRESS", origin="Mumbai CST", destination="Pune", section="Shivajinagar - Khadki", arrival_time="12:30", departure_time="12:35", average_speed=80),
    dict(train_number="51316", train_name="Pune Local", train_type="Passenger", priority="PASSENGER", origin="Mumbai CST", destination="Pune", section="Shivajinagar - Khadki", arrival_time="13:10", departure_time="13:15", average_speed=60),
    dict(train_number="11401", train_name="Nandigram Express", train_type="Express", priority="EXPRESS", origin="Mumbai CST", destination="Nagpur", section="Shivajinagar - Khadki", arrival_time="13:40", departure_time="13:45", average_speed=88),
    dict(train_number="12123", train_name="Deccan Queen", train_type="Express", priority="EXPRESS", origin="Pune", destination="Mumbai CST", section="Shivajinagar - Khadki", arrival_time="14:15", departure_time="14:20", average_speed=110),
    dict(train_number="11041", train_name="Mumbai - Chennai Express", train_type="Express", priority="EXPRESS", origin="Mumbai CST", destination="Chennai Central", section="Shivajinagar - Khadki", arrival_time="14:50", departure_time="14:55", average_speed=70),
    dict(train_number="16351", train_name="Nagercoil Express", train_type="Express", priority="EXPRESS", origin="Mumbai CST", destination="Nagercoil", section="Shivajinagar - Khadki", arrival_time="15:30", departure_time="15:35", average_speed=70),
    dict(train_number="22106", train_name="Indrayani Express", train_type="Superfast", priority="SUPERFAST", origin="Pune", destination="Mumbai CST", section="Shivajinagar - Khadki", arrival_time="15:55", departure_time="16:00", average_speed=110),
    dict(train_number="12028", train_name="Shatabdi Express", train_type="Shatabdi", priority="SHATABDI", origin="Mumbai CST", destination="Pune", section="Shivajinagar - Khadki", arrival_time="16:30", departure_time="16:35", average_speed=120),
    dict(train_number="12952", train_name="Mumbai Rajdhani", train_type="Rajdhani", priority="RAJDHANI", origin="Mumbai CST", destination="New Delhi", section="Shivajinagar - Khadki", arrival_time="17:20", departure_time="17:25", average_speed=130),
    dict(train_number="51318", train_name="Mumbai Local", train_type="Passenger", priority="PASSENGER", origin="Mumbai CST", destination="Pune", section="Shivajinagar - Khadki", arrival_time="18:10", departure_time="18:15", average_speed=60),
    dict(train_number="12124", train_name="Deccan Queen", train_type="Express", priority="EXPRESS", origin="Mumbai CST", destination="Pune", section="Shivajinagar - Khadki", arrival_time="18:40", departure_time="18:45", average_speed=110),
    dict(train_number="11019", train_name="Konark Express", train_type="Express", priority="EXPRESS", origin="Mumbai CST", destination="Bhubaneswar", section="Shivajinagar - Khadki", arrival_time="19:20", departure_time="19:25", average_speed=85),
    dict(train_number="12213", train_name="Duronto Express", train_type="Express", priority="EXPRESS", origin="Mumbai CST", destination="Pune", section="Shivajinagar - Khadki", arrival_time="20:00", departure_time="20:05", average_speed=120),
    dict(train_number="50103", train_name="Ratnagiri Freight", train_type="Freight", priority="FREIGHT", origin="Ratnagiri", destination="Pune", section="Shivajinagar - Khadki", arrival_time="22:15", departure_time="22:25", average_speed=45),
    dict(train_number="50104", train_name="Nagpur Freight", train_type="Freight", priority="FREIGHT", origin="Nagpur", destination="Mumbai CST", section="Shivajinagar - Khadki", arrival_time="23:10", departure_time="23:20", average_speed=40),
    dict(train_number="22893", train_name="Sampark Kranti", train_type="Express", priority="EXPRESS", origin="Pune", destination="Hari Dwar", section="Shivajinagar - Khadki", arrival_time="23:45", departure_time="23:50", average_speed=75),
    dict(train_number="12779", train_name="Goa Express", train_type="Express", priority="EXPRESS", origin="Goa", destination="Hazrat Nizamuddin", section="Shivajinagar - Khadki", arrival_time="00:15", departure_time="00:20", average_speed=80),
    dict(train_number="50107", train_name="Pune Goods", train_type="Freight", priority="FREIGHT", origin="Pune", destination="Mumbai CST", section="Shivajinagar - Khadki", arrival_time="01:20", departure_time="01:30", average_speed=40),
    dict(train_number="50108", train_name="Mumbai Goods", train_type="Freight", priority="FREIGHT", origin="Mumbai CST", destination="Pune", section="Shivajinagar - Khadki", arrival_time="03:10", departure_time="03:20", average_speed=40),
    dict(train_number="51320", train_name="Panvel Local", train_type="Passenger", priority="PASSENGER", origin="Panvel", destination="Pune", section="Shivajinagar - Khadki", arrival_time="04:20", departure_time="04:25", average_speed=55),

    # --- Supporting sections --------------------------------------------------
    dict(train_number="22131", train_name="Lonavala Intercity", train_type="Express", priority="EXPRESS", origin="Pune", destination="Lonavala", section="Pune - Lonavala", arrival_time="07:45", departure_time="07:50", average_speed=70),
    dict(train_number="51351", train_name="Lonavala Local", train_type="Passenger", priority="PASSENGER", origin="Pune", destination="Lonavala", section="Pune - Lonavala", arrival_time="16:30", departure_time="16:35", average_speed=55),
    dict(train_number="50131", train_name="Lonavala Freight", train_type="Freight", priority="FREIGHT", origin="Pune", destination="Lonavala", section="Pune - Lonavala", arrival_time="00:45", departure_time="00:55", average_speed=40),
    dict(train_number="57106", train_name="Hadapsar Local", train_type="Passenger", priority="PASSENGER", origin="Hadapsar", destination="Loni", section="Hadapsar - Loni", arrival_time="06:20", departure_time="06:25", average_speed=50),
    dict(train_number="50111", train_name="Loni Freight", train_type="Freight", priority="FREIGHT", origin="Loni", destination="Pune", section="Hadapsar - Loni", arrival_time="09:05", departure_time="09:15", average_speed=40),
    dict(train_number="51315", train_name="Dapodi Local", train_type="Passenger", priority="PASSENGER", origin="Pune", destination="Dapodi", section="Khadki - Dapodi", arrival_time="08:30", departure_time="08:35", average_speed=50),
    dict(train_number="51314", train_name="Kasarwadi Local", train_type="Passenger", priority="PASSENGER", origin="Pune", destination="Kasarwadi", section="Dapodi - Kasarwadi", arrival_time="09:00", departure_time="09:05", average_speed=50),
    dict(train_number="51403", train_name="Hadapsar Passenger", train_type="Passenger", priority="PASSENGER", origin="Pune", destination="Hadapsar", section="Shivajinagar - Hadapsar", arrival_time="07:30", departure_time="07:35", average_speed=50),
    dict(train_number="21201", train_name="Hadapsar Passenger", train_type="Passenger", priority="PASSENGER", origin="Mumbai CST", destination="Hadapsar", section="Shivajinagar - Hadapsar", arrival_time="18:30", departure_time="18:35", average_speed=50),
]


def seed_all():
    db = SessionLocal()
    try:
        existing_users = db.query(User).count()
        if existing_users == 0:
            users = [
            User(name="Rajesh Kumar", email="engineer@railsync.in", password_hash=hash_password("engineer123"), role="engineer"),
            User(name="Priya Sharma", email="engineer2@railsync.in", password_hash=hash_password("engineer123"), role="engineer"),
            User(name="Amit Patel", email="engineer3@railsync.in", password_hash=hash_password("engineer123"), role="engineer"),
            User(name="Suresh Iyer", email="officer@railsync.in", password_hash=hash_password("officer123"), role="officer"),
            User(name="Vikram Singh", email="officer2@railsync.in", password_hash=hash_password("officer123"), role="officer"),
        ]
        db.add_all(users)
        db.flush()
        db.commit()

        # Always keep the demo train corpus in sync with the busy-network
        # scenario in code, even when the database already exists. Demo trains
        # are owned by the seed and no other table references them by key.
        db.query(Train).delete()
        db.flush()
        for t in DEMO_TRAINS:
            db.add(Train(**t))
        db.commit()

    except Exception as e:
        print(f"SEED ERROR: {e}", flush=True)
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
    seed_all()
    print("Database seeded successfully!")
