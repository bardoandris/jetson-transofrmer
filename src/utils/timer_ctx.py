import time
class Timer:
    def __enter__(self):
        self._enter_time = time.time()

    def __exit__(self, *exc_args):
        self._exit_time = time.time()
        self.elapsed_time = self._exit_time - self._enter_time
        print(f"{self._exit_time - self._enter_time:.2f} seconds elapsed")