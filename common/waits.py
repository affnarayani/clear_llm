import random
import time


def sleep_random(min_sec, max_sec):
    seconds = random.uniform(min_sec, max_sec)
    print(f"[WAIT] Sleeping for {seconds:.2f} seconds...", flush=True)
    time.sleep(seconds)


def sleep_fixed(seconds):
    print(f"[WAIT] Sleeping for {seconds} seconds...", flush=True)
    time.sleep(seconds)