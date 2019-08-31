import wrapt

from twisted.internet import threads


@wrapt.decorator
def deferToThreadWrapper(wrapped, instance, args, kwargs):
    return threads.deferToThread(wrapped, *args, **kwargs)
