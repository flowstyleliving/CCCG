"""Stable event ordering, including events exactly at an action's finish time."""

import heapq
from dataclasses import dataclass, field

from .scenario import END, START


@dataclass(order=True)
class Event:
    time: int
    sequence: int
    kind: str = field(compare=False)
    data: dict = field(compare=False)


class Clock:
    def __init__(self):
        self.now = START
        self._events = []
        self._sequence = 0

    def schedule(self, time, kind, **data):
        if time < self.now or time > END:
            raise ValueError("event outside the remaining simulation horizon")
        self._sequence += 1
        heapq.heappush(self._events, Event(time, self._sequence, kind, data))

    def advance(self, minutes, fire):
        if type(minutes) is not int or minutes < 0 or self.now + minutes > END:
            raise ValueError("minutes must be a nonnegative integer within the horizon")
        target = self.now + minutes
        while self._events and self._events[0].time <= target:
            event = heapq.heappop(self._events)
            self.now = event.time
            fire(event)
        self.now = target
