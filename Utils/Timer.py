import time


def timer(function):
    def function_metrics(*args, **kwargs):
        start = time.time()
        c = function(*args, **kwargs)
        print(f"{str(function)}: {time.time() - start}")
        return c

    return function_metrics
