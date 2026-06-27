"""
User-scoped session state with disk persistence.
Backward-compatible accessors (global_processed_df, etc.) delegate to the active user session.
"""

from __future__ import annotations

import json
import shutil
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

_current_user_id: ContextVar[Optional[int]] = ContextVar("_current_user_id", default=None)

UPLOAD_DIR = "data/api_uploads"
SESSION_DIR = Path("data/user_sessions")


@dataclass
class UserSession:
    processed_df: Optional[pd.DataFrame] = None
    prediction_model: Any = None
    historical_stats: Optional[Dict[str, Any]] = None
    cycle_metrics: Optional[Dict[str, Any]] = None
    feature_importance: Optional[Any] = None
    model_metrics: Optional[Any] = None


_cache: dict[int, UserSession] = {}


def set_current_user(user_id: int) -> None:
    _current_user_id.set(user_id)


def get_current_user_id() -> Optional[int]:
    return _current_user_id.get()


def _require_user_id() -> int:
    user_id = _current_user_id.get()
    if user_id is None:
        raise RuntimeError("Authenticated user required")
    return user_id


def _session_dir(user_id: int) -> Path:
    return SESSION_DIR / str(user_id)


def get_user_session(user_id: int) -> UserSession:
    if user_id not in _cache:
        _cache[user_id] = _load_session(user_id)
    return _cache[user_id]


def _load_session(user_id: int) -> UserSession:
    session = UserSession()
    base = _session_dir(user_id)
    stats_file = base / "stats.json"
    df_file = base / "processed.parquet"

    if stats_file.exists():
        session.historical_stats = json.loads(stats_file.read_text(encoding="utf-8"))

    if df_file.exists():
        session.processed_df = pd.read_parquet(df_file)

    return session


def persist_session(user_id: int) -> None:
    session = get_user_session(user_id)
    base = _session_dir(user_id)
    base.mkdir(parents=True, exist_ok=True)

    if session.processed_df is not None and not session.processed_df.empty:
        session.processed_df.to_parquet(base / "processed.parquet")
    elif (base / "processed.parquet").exists():
        (base / "processed.parquet").unlink(missing_ok=True)

    if session.historical_stats:
        (base / "stats.json").write_text(
            json.dumps(session.historical_stats), encoding="utf-8"
        )
    elif (base / "stats.json").exists():
        (base / "stats.json").unlink(missing_ok=True)


def clear_session(user_id: int) -> None:
    _cache.pop(user_id, None)
    base = _session_dir(user_id)
    if base.exists():
        shutil.rmtree(base)


def _active_session() -> UserSession:
    return get_user_session(_require_user_id())


class _StateAccessor:
    """Proxy so existing endpoints keep using state.global_processed_df."""

    @property
    def global_processed_df(self) -> Optional[pd.DataFrame]:
        return _active_session().processed_df

    @global_processed_df.setter
    def global_processed_df(self, value: Optional[pd.DataFrame]) -> None:
        _active_session().processed_df = value
        persist_session(_require_user_id())

    @property
    def global_prediction_model(self) -> Any:
        return _active_session().prediction_model

    @global_prediction_model.setter
    def global_prediction_model(self, value: Any) -> None:
        _active_session().prediction_model = value

    @property
    def global_historical_stats(self) -> Optional[Dict[str, Any]]:
        return _active_session().historical_stats

    @global_historical_stats.setter
    def global_historical_stats(self, value: Optional[Dict[str, Any]]) -> None:
        _active_session().historical_stats = value
        persist_session(_require_user_id())

    @property
    def global_cycle_metrics(self) -> Optional[Dict[str, Any]]:
        return _active_session().cycle_metrics

    @global_cycle_metrics.setter
    def global_cycle_metrics(self, value: Optional[Dict[str, Any]]) -> None:
        _active_session().cycle_metrics = value

    @property
    def global_feature_importance(self) -> Optional[Any]:
        return _active_session().feature_importance

    @global_feature_importance.setter
    def global_feature_importance(self, value: Optional[Any]) -> None:
        _active_session().feature_importance = value

    @property
    def global_model_metrics(self) -> Optional[Any]:
        return _active_session().model_metrics

    @global_model_metrics.setter
    def global_model_metrics(self, value: Optional[Any]) -> None:
        _active_session().model_metrics = value


state = _StateAccessor()
