import hashlib
import hmac
from datetime import datetime, timedelta, timezone

from flask import current_app, request
from sqlalchemy import func, text

from app.extensions import db
from app.models import AuthRateLimitEvent


def _key_hash(action, scope, value):
    secret = str(current_app.config.get("SECRET_KEY", ""))
    message = f"{action}:{scope}:{value}".encode("utf-8", errors="ignore")
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def consume_auth_limits(action, identity=None, ip_limit=30, identity_limit=None, window_seconds=900):
    """Persist authentication attempts and enforce limits across app workers."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=window_seconds)
    remote_ip = request.remote_addr or "unknown"
    checks = [("ip", remote_ip, ip_limit)]
    if identity and identity_limit is not None:
        checks.append(("identity", str(identity).strip().lower(), identity_limit))

    hashed_checks = [
        (scope, _key_hash(action, scope, value), limit)
        for scope, value, limit in checks
    ]

    # PostgreSQL advisory locks make the count-and-insert sequence atomic for
    # concurrent requests across Gunicorn workers. Sorted lock order avoids deadlocks.
    if db.engine.dialect.name == "postgresql":
        for lock_hash in sorted(item[1] for item in hashed_checks):
            lock_id = int(lock_hash[:16], 16)
            if lock_id >= 2**63:
                lock_id -= 2**64
            db.session.execute(
                text("SELECT pg_advisory_xact_lock(:lock_id)"),
                {"lock_id": lock_id},
            )

    for _scope, hashed, limit in hashed_checks:
        query = AuthRateLimitEvent.query.filter(
            AuthRateLimitEvent.action == action,
            AuthRateLimitEvent.key_hash == hashed,
            AuthRateLimitEvent.created_at >= cutoff,
        )
        count = query.count()
        if count >= limit:
            oldest = query.with_entities(func.min(AuthRateLimitEvent.created_at)).scalar()
            if oldest and oldest.tzinfo is None:
                oldest = oldest.replace(tzinfo=timezone.utc)
            retry_after = max(1, int((oldest + timedelta(seconds=window_seconds) - now).total_seconds())) if oldest else window_seconds
            # Release any PostgreSQL advisory locks before returning the throttle response.
            db.session.rollback()
            return {"error": "Too many attempts. Please wait before trying again."}, 429, retry_after

    for _scope, hashed, _limit in hashed_checks:
        db.session.add(AuthRateLimitEvent(action=action, key_hash=hashed, created_at=now))

    # Keep the persistent throttle table bounded without requiring a scheduled job.
    db.session.query(AuthRateLimitEvent).filter(
        AuthRateLimitEvent.created_at < now - timedelta(days=14)
    ).delete(synchronize_session=False)
    db.session.commit()
    return None
