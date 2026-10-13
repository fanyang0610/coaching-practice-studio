#!/usr/bin/env python3
"""Account administration from a shell, against the database in DATABASE_URL (default: local erickson.db).

    python3 scripts/manage.py create-admin you@example.com --name "Your Name"
    python3 scripts/manage.py invite --role trainer --email coach@example.com --base-url https://your-app
    python3 scripts/manage.py reset-link someone@example.com --base-url https://your-app
    python3 scripts/manage.py list-users
"""

from __future__ import annotations

import argparse
import getpass
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import accounts  # noqa: E402
import db  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manage Erickson Coach accounts.")
    commands = parser.add_subparsers(dest="command", required=True)

    create_admin = commands.add_parser("create-admin", help="Create an admin account (prompts for the password).")
    create_admin.add_argument("email")
    create_admin.add_argument("--name", default="")

    invite = commands.add_parser("invite", help="Print a one-use invite link.")
    invite.add_argument("--role", choices=accounts.ROLES, default="user")
    invite.add_argument("--email", default="", help="Only this email can use the invite.")
    invite.add_argument("--trainer", default="", help="Trainer email to assign the new person to.")
    invite.add_argument("--base-url", default="http://127.0.0.1:7860")

    reset = commands.add_parser("reset-link", help="Print a one-use password reset link.")
    reset.add_argument("email")
    reset.add_argument("--base-url", default="http://127.0.0.1:7860")

    commands.add_parser("list-users", help="List accounts.")

    args = parser.parse_args(argv)
    store = db.Store(db.database_url())

    if args.command == "create-admin":
        if store.get_user_by_email(args.email):
            print(f"{args.email} already has an account.", file=sys.stderr)
            return 1
        password = getpass.getpass("Password: ")
        problem = accounts.password_problem(password, getpass.getpass("Confirm password: "))
        if problem:
            print(f"Password not accepted ({problem.replace('_', ' ')}; minimum {accounts.MIN_PASSWORD_LENGTH} characters).", file=sys.stderr)
            return 1
        user_id = store.create_user(args.email, args.name or args.email.split("@")[0], accounts.hash_password(password),
                                    role="admin", consented=True)
        store.log(None, "account_created", target_user_id=user_id, detail="admin from scripts/manage.py")
        print(f"Admin account created for {args.email}.")
    elif args.command == "invite":
        trainer_id = None
        if args.trainer:
            trainer = store.get_user_by_email(args.trainer)
            if not trainer or trainer["role"] not in ("trainer", "admin"):
                print(f"{args.trainer} is not a trainer or admin.", file=sys.stderr)
                return 1
            trainer_id = trainer["id"]
        code = store.create_invite(None, role=args.role, trainer_id=trainer_id, email=args.email or None)
        store.log(None, "invite_created", detail=f"{args.role} invite {code[:6]}… from scripts/manage.py")
        print(f"{args.base_url.rstrip('/')}/invite/{code}")
    elif args.command == "reset-link":
        user = store.get_user_by_email(args.email)
        if not user:
            print(f"No account for {args.email}.", file=sys.stderr)
            return 1
        token = store.create_password_reset(user["id"])
        store.log(None, "reset_link_created", target_user_id=user["id"], detail="from scripts/manage.py")
        print(f"{args.base_url.rstrip('/')}/reset/{token}")
    else:
        for user in store.list_users():
            print(f"{user['id']:>4}  {user['role']:<8} {user['status']:<9} {user['email']}  ({user['display_name']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
