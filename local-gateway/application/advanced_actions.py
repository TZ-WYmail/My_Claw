"""
Advanced-domain compatibility facade.

The historical HTTP advanced routes have already been removed. This module
remains only as an import-stable aggregation layer for compatibility callers
and dedicated tests; domain-specific application modules are the real owners.
Compatibility access now emits `DeprecationWarning` and should migrate toward
the direct owner module.
"""
from __future__ import annotations

import warnings

from application.calendar_actions import (
    create_calendar_event_action as _create_calendar_event_action,
    delete_calendar_event_action as _delete_calendar_event_action,
    get_calendar_view_action as _get_calendar_view_action,
    list_calendar_events_action as _list_calendar_events_action,
)
from application.pomodoro_actions import (
    complete_pomodoro_action as _complete_pomodoro_action,
    get_pomodoro_history_action as _get_pomodoro_history_action,
    get_pomodoro_stats_action as _get_pomodoro_stats_action,
    get_pomodoro_status_action as _get_pomodoro_status_action,
    interrupt_pomodoro_action as _interrupt_pomodoro_action,
    start_pomodoro_action as _start_pomodoro_action,
)
from application.subtask_actions import (
    create_subtask_action as _create_subtask_action,
    delete_subtask_action as _delete_subtask_action,
    list_subtasks_action as _list_subtasks_action,
    update_subtask_action as _update_subtask_action,
)
from application.tag_actions import (
    add_task_tags_action as _add_task_tags_action,
    create_tag_action as _create_tag_action,
    delete_tag_action as _delete_tag_action,
    list_tags_action as _list_tags_action,
    remove_task_tags_action as _remove_task_tags_action,
)
from application.task_detail_actions import (
    batch_update_tasks_action as _batch_update_tasks_action,
    get_task_detail_action as _get_task_detail_action,
)

_COMPAT_EXPORTS = {
    "add_task_tags_action": (_add_task_tags_action, "application.tag_actions.add_task_tags_action"),
    "batch_update_tasks_action": (_batch_update_tasks_action, "application.task_detail_actions.batch_update_tasks_action"),
    "complete_pomodoro_action": (_complete_pomodoro_action, "application.pomodoro_actions.complete_pomodoro_action"),
    "create_calendar_event_action": (_create_calendar_event_action, "application.calendar_actions.create_calendar_event_action"),
    "create_subtask_action": (_create_subtask_action, "application.subtask_actions.create_subtask_action"),
    "create_tag_action": (_create_tag_action, "application.tag_actions.create_tag_action"),
    "delete_calendar_event_action": (_delete_calendar_event_action, "application.calendar_actions.delete_calendar_event_action"),
    "delete_subtask_action": (_delete_subtask_action, "application.subtask_actions.delete_subtask_action"),
    "delete_tag_action": (_delete_tag_action, "application.tag_actions.delete_tag_action"),
    "get_calendar_view_action": (_get_calendar_view_action, "application.calendar_actions.get_calendar_view_action"),
    "get_pomodoro_history_action": (_get_pomodoro_history_action, "application.pomodoro_actions.get_pomodoro_history_action"),
    "get_pomodoro_stats_action": (_get_pomodoro_stats_action, "application.pomodoro_actions.get_pomodoro_stats_action"),
    "get_pomodoro_status_action": (_get_pomodoro_status_action, "application.pomodoro_actions.get_pomodoro_status_action"),
    "get_task_detail_action": (_get_task_detail_action, "application.task_detail_actions.get_task_detail_action"),
    "interrupt_pomodoro_action": (_interrupt_pomodoro_action, "application.pomodoro_actions.interrupt_pomodoro_action"),
    "list_calendar_events_action": (_list_calendar_events_action, "application.calendar_actions.list_calendar_events_action"),
    "list_subtasks_action": (_list_subtasks_action, "application.subtask_actions.list_subtasks_action"),
    "list_tags_action": (_list_tags_action, "application.tag_actions.list_tags_action"),
    "remove_task_tags_action": (_remove_task_tags_action, "application.tag_actions.remove_task_tags_action"),
    "start_pomodoro_action": (_start_pomodoro_action, "application.pomodoro_actions.start_pomodoro_action"),
    "update_subtask_action": (_update_subtask_action, "application.subtask_actions.update_subtask_action"),
}

__all__ = list(_COMPAT_EXPORTS)


def __getattr__(name: str):
    target = _COMPAT_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    value, owner = target
    warnings.warn(
        f"application.advanced_actions.{name} is deprecated; use {owner} instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return value


def __dir__():
    return sorted(set(globals()) | set(__all__))
