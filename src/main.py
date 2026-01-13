# src/main.py
import logging
from db.connection import get_db_connection
from service.routing import resolve_endpoint, RouteNotFoundError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    logger.info("Starting application")
    conn = get_db_connection()

    try:
        url = resolve_endpoint(
            conn,
            tenant="team-a",
            service="payments",
            env="prod",
            version="v2",
        )
        logger.info(f"Resolved endpoint: {url}")
        print("Resolved endpoint:", url)

    except RouteNotFoundError as e:
        logger.warning(f"Route not found: {e}")
        print("Not found:", e)

    finally:
        conn.close()
        logger.info("Application finished")


if __name__ == "__main__":
    main()
