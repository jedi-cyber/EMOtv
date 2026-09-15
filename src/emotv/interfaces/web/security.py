"""Configuración explícita de la frontera HTTP y WebSocket."""
from collections.abc import Mapping
from dataclasses import dataclass
import os
from urllib.parse import urlsplit

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware


@dataclass(frozen=True)
class WebSecuritySettings:
    production: bool = False
    origins: tuple[str, ...] = ("http://localhost:5173", "http://127.0.0.1:5173")
    hosts: tuple[str, ...] = ("localhost", "127.0.0.1", "testserver")


def load_web_settings(environ: Mapping[str, str] | None = None) -> WebSecuritySettings:
    source = os.environ if environ is None else environ
    environment = source.get("ENVIRONMENT", "development").strip()
    if environment not in {"development", "test", "production"}:
        raise ValueError("ENVIRONMENT debe ser development, test o production")
    production = environment == "production"
    origins = tuple(value.strip().rstrip("/") for value in source.get(
        "CORS_ORIGINS", "" if production else "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",") if value.strip())
    hosts = tuple(value.strip() for value in source.get(
        "TRUSTED_HOSTS", "" if production else "localhost,127.0.0.1,testserver"
    ).split(",") if value.strip())
    for origin in origins:
        parsed = urlsplit(origin)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.username or parsed.password or parsed.path or parsed.query
                or parsed.fragment or "*" in origin or (production and parsed.scheme != "https")):
            raise ValueError("CORS_ORIGINS requiere orígenes explícitos y HTTPS en producción")
    if any("*" in host or ":" in host or "/" in host for host in hosts):
        raise ValueError("TRUSTED_HOSTS requiere nombres de host explícitos sin puerto")
    if not hosts or (production and not origins):
        raise ValueError("Configura TRUSTED_HOSTS y CORS_ORIGINS explícitamente")
    if production:
        secret = source.get("JWT_SECRET_KEY", "")
        if len(secret) < 32 or secret.startswith("replace-") or not source.get("DATABASE_URL", "").strip():
            raise ValueError("Producción requiere DATABASE_URL y JWT_SECRET_KEY no provisional")
    return WebSecuritySettings(production, origins, hosts)


class SecurityBoundaryMiddleware:
    def __init__(self, app, settings: WebSecuritySettings) -> None:
        self.app, self.settings = app, settings

    async def __call__(self, scope, receive, send):
        if scope["type"] == "websocket":
            headers = dict(scope.get("headers", ()))
            origin = headers.get(b"origin", b"").decode("latin-1")
            if ((origin and origin not in self.settings.origins)
                    or (self.settings.production and not origin)):
                await send({"type": "websocket.close", "code": 1008})
                return

        async def secure_send(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", ()))
                names = {name.lower() for name, _ in headers}
                additions = {
                    b"x-content-type-options": b"nosniff",
                    b"x-frame-options": b"DENY",
                    b"referrer-policy": b"no-referrer",
                    b"permissions-policy": b"camera=(self), microphone=(), geolocation=()",
                    b"cache-control": b"no-store",
                }
                if self.settings.production:
                    additions[b"strict-transport-security"] = b"max-age=31536000"
                    additions[b"content-security-policy"] = b"default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
                headers.extend((name, value) for name, value in additions.items() if name not in names)
                message = {**message, "headers": headers}
            await send(message)
        await self.app(scope, receive, secure_send)


def configure_web_security(app: FastAPI, settings: WebSecuritySettings) -> None:
    app.add_middleware(SecurityBoundaryMiddleware, settings=settings)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(settings.hosts))
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.origins),
                       allow_credentials=False,
                       allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
                       allow_headers=["Authorization", "Content-Type", "Accept"])
