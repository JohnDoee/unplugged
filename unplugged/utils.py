import queue
import time
from threading import Thread


def threadify(fn, cache_result=False, delay=0):
    if cache_result:
        q = queue.SimpleQueue()

    def thread(*args, **kwargs):
        if delay:
            time.sleep(delay)

        r = fn(*args, **kwargs)
        if cache_result:
            q.put(r)

    def inner(*args, **kwargs):
        t = Thread(target=thread, args=args, kwargs=kwargs, daemon=True)
        t.start()

        def innerinner():
            return q.get()

        return innerinner

    return inner
