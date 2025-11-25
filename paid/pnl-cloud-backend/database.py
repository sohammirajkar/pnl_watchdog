from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 1. Define the Database URL
# Using SQLite for local development (creates a file named 'pnl.db')
SQLALCHEMY_DATABASE_URL = "sqlite:///./pnl.db"

# 2. Create the Engine
# check_same_thread=False is required only for SQLite
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

# 3. Create SessionLocal class
# Each instance of this class will be a database session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 4. Create Base class
# All database models will inherit from this
Base = declarative_base()
