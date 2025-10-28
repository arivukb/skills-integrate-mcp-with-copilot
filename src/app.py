"""High School Management System API

This FastAPI application now persists activities to SQLite using SQLModel.

It keeps the original HTTP endpoints for compatibility, while storing
activities and participants in a small SQLite database (data.db by default).
"""

import os
from pathlib import Path
from typing import Optional, List, Dict

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from sqlmodel import SQLModel, Field, Session, create_engine, select


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data.db")

app = FastAPI(title="Mergington High School API",
              description="API for viewing and signing up for extracurricular activities")

# Mount the static files directory (if present)
current_dir = Path(__file__).parent
static_dir = current_dir / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# --- Models --------------------------------------------------------------

class Activity(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    description: str
    schedule: str
    max_participants: int


class Participant(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True)
    activity_id: int = Field(foreign_key="activity.id")


# Create engine and tables
engine = create_engine(DATABASE_URL, echo=False)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def seed_initial_data():
    """Seed the DB with initial activities only if none exist."""
    initial = {
        "Chess Club": {
            "description": "Learn strategies and compete in chess tournaments",
            "schedule": "Fridays, 3:30 PM - 5:00 PM",
            "max_participants": 12,
            "participants": ["michael@mergington.edu", "daniel@mergington.edu"]
        },
        "Programming Class": {
            "description": "Learn programming fundamentals and build software projects",
            "schedule": "Tuesdays and Thursdays, 3:30 PM - 4:30 PM",
            "max_participants": 20,
            "participants": ["emma@mergington.edu", "sophia@mergington.edu"]
        },
        "Gym Class": {
            "description": "Physical education and sports activities",
            "schedule": "Mondays, Wednesdays, Fridays, 2:00 PM - 3:00 PM",
            "max_participants": 30,
            "participants": ["john@mergington.edu", "olivia@mergington.edu"]
        },
        "Soccer Team": {
            "description": "Join the school soccer team and compete in matches",
            "schedule": "Tuesdays and Thursdays, 4:00 PM - 5:30 PM",
            "max_participants": 22,
            "participants": ["liam@mergington.edu", "noah@mergington.edu"]
        },
        "Basketball Team": {
            "description": "Practice and play basketball with the school team",
            "schedule": "Wednesdays and Fridays, 3:30 PM - 5:00 PM",
            "max_participants": 15,
            "participants": ["ava@mergington.edu", "mia@mergington.edu"]
        },
        "Art Club": {
            "description": "Explore your creativity through painting and drawing",
            "schedule": "Thursdays, 3:30 PM - 5:00 PM",
            "max_participants": 15,
            "participants": ["amelia@mergington.edu", "harper@mergington.edu"]
        },
        "Drama Club": {
            "description": "Act, direct, and produce plays and performances",
            "schedule": "Mondays and Wednesdays, 4:00 PM - 5:30 PM",
            "max_participants": 20,
            "participants": ["ella@mergington.edu", "scarlett@mergington.edu"]
        },
        "Math Club": {
            "description": "Solve challenging problems and participate in math competitions",
            "schedule": "Tuesdays, 3:30 PM - 4:30 PM",
            "max_participants": 10,
            "participants": ["james@mergington.edu", "benjamin@mergington.edu"]
        },
        "Debate Team": {
            "description": "Develop public speaking and argumentation skills",
            "schedule": "Fridays, 4:00 PM - 5:30 PM",
            "max_participants": 12,
            "participants": ["charlotte@mergington.edu", "henry@mergington.edu"]
        }
    }

    with Session(engine) as session:
        existing = session.exec(select(Activity)).first()
        if existing:
            return

        for name, data in initial.items():
            act = Activity(name=name,
                           description=data["description"],
                           schedule=data["schedule"],
                           max_participants=data["max_participants"])
            session.add(act)
            session.commit()
            session.refresh(act)
            for email in data["participants"]:
                p = Participant(email=email, activity_id=act.id)
                session.add(p)
        session.commit()


# Initialize DB and seed
create_db_and_tables()
seed_initial_data()


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/activities")
def get_activities():
    """Return all activities as a dict keyed by activity name (legacy shape)."""
    with Session(engine) as session:
        activities = session.exec(select(Activity)).all()
        result: Dict[str, Dict] = {}
        for act in activities:
            participants = session.exec(select(Participant).where(Participant.activity_id == act.id)).all()
            emails = [p.email for p in participants]
            result[act.name] = {
                "description": act.description,
                "schedule": act.schedule,
                "max_participants": act.max_participants,
                "participants": emails
            }
        return result


@app.post("/activities/{activity_name}/signup")
def signup_for_activity(activity_name: str, email: str):
    """Sign up a student for an activity (stored in SQLite)."""
    with Session(engine) as session:
        act = session.exec(select(Activity).where(Activity.name == activity_name)).first()
        if not act:
            raise HTTPException(status_code=404, detail="Activity not found")

        current = session.exec(select(Participant).where(Participant.activity_id == act.id)).all()
        if any(p.email == email for p in current):
            raise HTTPException(status_code=400, detail="Student is already signed up")

        if len(current) >= act.max_participants:
            raise HTTPException(status_code=400, detail="Activity is full")

        participant = Participant(email=email, activity_id=act.id)
        session.add(participant)
        session.commit()
        return {"message": f"Signed up {email} for {activity_name}"}


@app.delete("/activities/{activity_name}/unregister")
def unregister_from_activity(activity_name: str, email: str):
    """Unregister a student from an activity."""
    with Session(engine) as session:
        act = session.exec(select(Activity).where(Activity.name == activity_name)).first()
        if not act:
            raise HTTPException(status_code=404, detail="Activity not found")

        participant = session.exec(select(Participant).where(Participant.activity_id == act.id, Participant.email == email)).first()
        if not participant:
            raise HTTPException(status_code=400, detail="Student is not signed up for this activity")

        session.delete(participant)
        session.commit()
        return {"message": f"Unregistered {email} from {activity_name}"}

