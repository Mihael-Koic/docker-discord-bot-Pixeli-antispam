import sqlite3
from pathlib import Path


DATABASE_PATH = "/app/data/antispam.db"


class Database:

    def __init__(self):

        Path(
            DATABASE_PATH
        ).parent.mkdir(
            parents=True,
            exist_ok=True
        )

        self.connection = sqlite3.connect(
            DATABASE_PATH,
            check_same_thread=False
        )

        self.create_tables()


    # =====================================================
    # CREATE TABLES
    # =====================================================

    def create_tables(self):

        cursor = self.connection.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS link_block_channels (

                guild_id INTEGER NOT NULL,

                channel_id INTEGER NOT NULL,

                enabled INTEGER NOT NULL DEFAULT 1,

                PRIMARY KEY (
                    guild_id,
                    channel_id
                )

            )
        """)

        self.connection.commit()


    # =====================================================
    # ENABLE LINK BLOCK
    # =====================================================

    def enable_link_block(
        self,
        guild_id: int,
        channel_id: int
    ):

        cursor = self.connection.cursor()

        cursor.execute("""
            INSERT INTO link_block_channels
            (
                guild_id,
                channel_id,
                enabled
            )

            VALUES (?, ?, 1)

            ON CONFLICT(
                guild_id,
                channel_id
            )

            DO UPDATE SET
                enabled = 1
        """, (
            guild_id,
            channel_id
        ))

        self.connection.commit()


    # =====================================================
    # DISABLE LINK BLOCK
    # =====================================================

    def disable_link_block(
        self,
        guild_id: int,
        channel_id: int
    ):

        cursor = self.connection.cursor()

        cursor.execute("""
            DELETE FROM link_block_channels

            WHERE guild_id = ?
            AND channel_id = ?
        """, (
            guild_id,
            channel_id
        ))

        self.connection.commit()


    # =====================================================
    # CHECK LINK BLOCK
    # =====================================================

    def is_link_block_enabled(
        self,
        guild_id: int,
        channel_id: int
    ) -> bool:

        cursor = self.connection.cursor()

        cursor.execute("""
            SELECT enabled

            FROM link_block_channels

            WHERE guild_id = ?
            AND channel_id = ?
        """, (
            guild_id,
            channel_id
        ))

        result = cursor.fetchone()

        if result is None:

            return False

        return bool(
            result[0]
        )


    # =====================================================
    # GET ALL PROTECTED CHANNELS
    # =====================================================

    def get_link_block_channels(
        self,
        guild_id: int
    ):

        cursor = self.connection.cursor()

        cursor.execute("""
            SELECT channel_id

            FROM link_block_channels

            WHERE guild_id = ?
            AND enabled = 1
        """, (
            guild_id,
        ))

        return [
            row[0]
            for row in cursor.fetchall()
        ]