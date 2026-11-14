"""Initialize empty local tables, optionally create a local administrator."""
import argparse
import getpass
from sqlalchemy import select
from backend.models.database import Base, engine, session_scope
from backend.models import models
from backend.core.security import get_password_hash
from backend.core.utils import generate_unique_uid
from backend.core.billing_config import new_user_points


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--admin", metavar="USERNAME", help="create an administrator; password is prompted")
    parser.add_argument("--if-missing", action="store_true", help="keep an existing administrator unchanged")
    parser.add_argument("--unlimited", action="store_true", help="enable unlimited credits for the administrator being created")
    args = parser.parse_args()
    if args.unlimited and not args.admin:
        parser.error("--unlimited requires --admin")
    from backend.models.migrations import migrate
    migrate(engine)
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
                               uid=generate_unique_uid(db), is_admin=True, unlimited_credits=args.unlimited, points=new_user_points()))
        print("Local administrator created with configured registration credits.")


if __name__ == "__main__":
    main()
