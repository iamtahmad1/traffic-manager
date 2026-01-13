# src/db/connection.py
import os
import logging
import psycopg2

logger = logging.getLogger(__name__)


def get_db_connection():
    logger.info("Connecting to database")
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )
    logger.info("Database connection established")
    return conn
