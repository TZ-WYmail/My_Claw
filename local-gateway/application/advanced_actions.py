"""
Advanced-domain compatibility facade.

The historical HTTP advanced routes have already been removed. This module
remains only as an import-stable aggregation layer for compatibility callers
and dedicated tests; domain-specific application modules are the real owners.
"""
from __future__ import annotations

from application.calendar_actions import (
    create_calendar_event_action,
    delete_calendar_event_action,
    get_calendar_view_action,
    list_calendar_events_action,
)
from application.pomodoro_actions import (
    complete_pomodoro_action,
    get_pomodoro_history_action,
    get_pomodoro_stats_action,
    get_pomodoro_status_action,
    interrupt_pomodoro_action,
    start_pomodoro_action,
)
from application.subtask_actions import (
    create_subtask_action,
    delete_subtask_action,
    list_subtasks_action,
    update_subtask_action,
)
from application.tag_actions import (
    add_task_tags_action,
    create_tag_action,
    delete_tag_action,
    list_tags_action,
    remove_task_tags_action,
)
from application.task_detail_actions import (
    batch_update_tasks_action,
    get_task_detail_action,
)

__all__ = [
    "add_task_tags_action",
    "batch_update_tasks_action",
    "complete_pomodoro_action",
    "create_calendar_event_action",
    "create_subtask_action",
    "create_tag_action",
    "delete_calendar_event_action",
    "delete_subtask_action",
    "delete_tag_action",
    "get_calendar_view_action",
    "get_pomodoro_history_action",
    "get_pomodoro_stats_action",
    "get_pomodoro_status_action",
    "get_task_detail_action",
    "interrupt_pomodoro_action",
    "list_calendar_events_action",
    "list_subtasks_action",
    "list_tags_action",
    "remove_task_tags_action",
    "start_pomodoro_action",
    "update_subtask_action",
]
