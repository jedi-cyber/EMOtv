from enum import Enum


class AccessAction(str, Enum):
    REGISTER_USER = "register_user"
    MANAGE_USERS = "manage_users"
    MANAGE_STUDENTS = "manage_students"
    MANAGE_ACTIVITIES = "manage_activities"
    START_SESSION = "start_session"
    CANCEL_SESSION = "cancel_session"
    VIEW_SESSION = "view_session"
    LIST_STUDENT_SESSIONS = "list_student_sessions"
    MANAGE_CONSENT = "manage_consent"
