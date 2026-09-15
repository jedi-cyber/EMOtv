from emotv.application import AuthenticationService
from emotv.config import get_database_url, get_jwt_secret_key
from emotv.infrastructure.persistence import (
    PostgresUserRepository,
    create_database_engine,
    create_session_factory,
)

engine = create_database_engine(get_database_url())
users = PostgresUserRepository(create_session_factory(engine))
authentication = AuthenticationService(users, get_jwt_secret_key())
user = authentication.authenticate(
    "admin@emotv.local",
    "x1BLa5MePNeU3QBVYVA4wa68",
)
print("AUTHENTICATED=" + str(user is not None))
if user is not None:
    token = authentication.create_access_token(user)
    claims = authentication.decode_access_token(token)
    print(f"ROLE={user.role.value}")
    print(f"TOKEN_SUBJECT_OK={claims.get('sub') == user.id}")
engine.dispose()
