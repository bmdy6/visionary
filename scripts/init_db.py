"""Initialize empty local tables, optionally create a local administrator."""
import argparse
import getpass
from sqlalchemy import select
from backend.models.database import Base, engine, session_scope
from backend.models import models
from backend.core.security import get_password_hash
from backend.core.utils import generate_unique_uid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--admin", metavar="USERNAME", help="create an administrator; password is prompted")
    parser.add_argument("--if-missing", action="store_true", help="keep an existing administrator unchanged")
    args = parser.parse_args()
    Base.metadata.create_all(bind=engine)
    print("Database tables initialized (no seeded users).")
    if args.admin:
        with session_scope() as db:
            existing = db.scalar(select(models.User).where(models.User.username == args.admin))
            if existing:
                if args.if_missing and existing.is_admin:
                    print("Existing administrator preserved (password and credits unchanged).")
                    return
                parser.error("username already exists")
        password = getpass.getpass("New administrator password (at least 12 characters): ")
        if len(password) < 12:
            parser.error("administrator password must be at least 12 characters")
        with session_scope() as db:
            if db.scalar(select(models.User).where(models.User.username == args.admin)):
                parser.error("username already exists")
            db.add(models.User(username=args.admin, password_hash=get_password_hash(password),
                               uid=generate_unique_uid(db), is_admin=True, points=100))
        print("Local administrator created with 100 demo credits.")


if __name__ == "__main__":
    main()
