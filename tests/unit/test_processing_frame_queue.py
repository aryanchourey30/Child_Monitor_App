from __future__ import annotations

from processing.frame_queue import FrameQueue


def test_queue_fifo_order() -> None:
    q = FrameQueue(max_size=10, overflow_strategy="drop_oldest")
    q.enqueue("a")
    q.enqueue("b")
    q.enqueue("c")
    assert q.get() == "a"
    assert q.get() == "b"
    assert q.get() == "c"


def test_queue_drop_oldest_strategy() -> None:
    q = FrameQueue(max_size=2, overflow_strategy="drop_oldest")
    q.enqueue("a")
    q.enqueue("b")
    q.enqueue("c")
    assert q.get() == "b"
    assert q.get() == "c"
