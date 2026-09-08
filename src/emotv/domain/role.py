from enum import Enum


class Role(str, Enum):
    STUDENT = "student"
    PSYCHOLOGIST = "psychologist"
    ADMIN = "admin"
