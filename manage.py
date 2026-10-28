"""Explicit database migration/bootstrap command for Render pre-deploy."""
import argparse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['init-db'])
    parser.parse_args()
    from app import app
    app.extensions['initialize_database']()
    print('Database migrations and owner initialization completed.')
    from database import Connection
    connection = Connection(app.config)
    try:
        for owner in connection.execute("SELECT username FROM users WHERE role='owner'").fetchall():
            print('Owner username:', owner['username'])
    finally:
        connection.close()


if __name__ == '__main__':
    main()
