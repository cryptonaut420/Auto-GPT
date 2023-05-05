"""Task Statuses module."""
from __future__ import annotations

from typing import NoReturn

from autogpt.commands.command import command
from autogpt.logs import logger


@command(
    "shutdown_autogpt",
    "All Tasks Complete / Nothing Left to Do, No More Reason to Live (Shutdown)",
    '"reason": "<reason>"',
)
def shutdown_autogpt(reason: str) -> NoReturn:
    """
    A function that takes in a string and exits the program

    Parameters:
        reason (str): The reason for shutting down.
    Returns:
        A result string from create chat completion. A list of suggestions to
            improve the code.
    """
    logger.info(title="Shutting down...\n", message=reason)
    quit()
