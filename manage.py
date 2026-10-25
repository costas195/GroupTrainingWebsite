"""Explicit database migration/bootstrap command for Render pre-deploy."""
import argparse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['init-db'])
    parser.parse_args()
    from app import app
    app.extensions['initialize_database']()
    print('Database migrations and owner initialization completed.')


if __name__ == '__main__':
    main()
