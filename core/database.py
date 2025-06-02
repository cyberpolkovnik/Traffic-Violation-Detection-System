import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import uuid
from config import SPEED_THRESHOLD_KMH 

class Database:
    def __init__(self, db_config):
        """
        Initialize the Database handler with connection configuration.
        
        Args:
            db_config (dict): Dictionary containing database connection parameters
                             (e.g., host, database, user, password, port)
        """
        self.db_config = db_config  # Store DB connection parameters
        self.conn = None  # Will hold the database connection
        self.cursor = None  # Will hold the database cursor

    def connect(self):
        """Establish a connection to the PostgreSQL database."""
        try:
            # Create connection with RealDictCursor for dictionary-like results
            self.conn = psycopg2.connect(**self.db_config, cursor_factory=RealDictCursor)
            self.cursor = self.conn.cursor()
            print("Database connection established")
        except psycopg2.Error as e:
            print(f"Error connecting to database: {e}")
            raise

    def close(self):
        """Close the database connection and cursor."""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
            print("Database connection closed")

    def insert_report(self, track_id, speed_kmh, duration_s, timestamp, clip_path, video_filename):
        """
        Insert a new speed report into the reports table.
        
        Args:
            track_id (int): ID of the tracked vehicle
            speed_kmh (float): Measured speed in km/h
            duration_s (float): Time taken to cross measurement zone in seconds
            timestamp (float): Unix timestamp of the measurement
            clip_path (str): Path to the video clip of the violation
            video_filename (str): Source video filename
            
        Returns:
            str: The generated UUID report_id
        """
        try:
            report_id = str(uuid.uuid4())  # Generate unique ID for the report
            query = """
                INSERT INTO reports (id, track_id, speed_kmh, duration_s, timestamp, clip_path, video_filename)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            # Execute the query with parameters
            self.cursor.execute(query, (
                report_id,
                track_id,
                speed_kmh,
                duration_s,
                datetime.fromtimestamp(timestamp),  # Convert timestamp to datetime
                clip_path,
                video_filename
            ))
            self.conn.commit()  # Commit the transaction
            print(f"Inserted report for track_id {track_id}")
            return report_id
        except psycopg2.Error as e:
            self.conn.rollback()  # Rollback on error
            print(f"Error inserting report: {e}")
            raise

    def fetch_reports(self):
        """
        Retrieve all reports with speed exceeding the threshold.
        
        Returns:
            list: List of dictionaries containing report data, ordered by timestamp (newest first)
        """
        try:
            self.cursor.execute(
                "SELECT * FROM reports WHERE speed_kmh > %s ORDER BY timestamp DESC",
                (SPEED_THRESHOLD_KMH,)
            )
            return self.cursor.fetchall()
        except psycopg2.Error as e:
            print(f"Error fetching reports: {e}")
            raise

    def fetch_report_by_id(self, report_id):
        """
        Retrieve a single report by its ID.
        
        Args:
            report_id (str): UUID of the report to fetch
            
        Returns:
            dict: Report data if found, None otherwise
        """
        try:
            self.cursor.execute("SELECT * FROM reports WHERE id = %s", (report_id,))
            report = self.cursor.fetchone()
            if not report:
                return None
            return report
        except psycopg2.Error as e:
            print(f"Error fetching report by ID {report_id}: {e}")
            raise

    def __enter__(self):
        """Context manager entry - establishes connection."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures connection is closed."""
        self.close()