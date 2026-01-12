# src/main.py
from db.connection import get_db_connection
from service.routing import resolve_endpoint, RouteNotFoundError


def main():
    conn = get_db_connection()

    try:
        url = resolve_endpoint(
            conn,
            tenant="team-a",
            service="payments",
            env="prod",
            version="v2",
        )
        print("Resolved endpoint:", url)

    except RouteNotFoundError as e:
        print("Not found:", e)

    finally:
        conn.close()


if __name__ == "__main__":
    main()
