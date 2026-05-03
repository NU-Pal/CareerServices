from typing import List, Optional
from pydantic import BaseModel

class CourseSession(BaseModel):
    courseName: str
    instructor: str
    day: str
    start: str
    end: str
    section: Optional[str] = None
    room: Optional[str] = None
    subtype: Optional[str] = None

class ParsedSchedule(BaseModel):
    blockId: Optional[str] = None
    semester: str = "Fall 2025"
    courses: List[CourseSession]
