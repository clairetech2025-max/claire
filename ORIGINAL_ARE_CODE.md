# Original ARE Code

Source path: `/home/LuciusPrime/original_are.pyiginal_are.py/are.py`

Memory path used by global instance: `/home/LuciusPrime/original_are.pyiginal_are.py/are_data/are_mem.jsonl`

## Behavior Summary

- `AREStore.ingest(text)` creates a chronological memory record.
- Record shape: `{"ts": int(time.time()), "sha": sha256(text)[:10], "text": text[:8000]}`.
- Records are written as JSONL by a background writer thread.
- `last_n(n)` reads the last `n` JSONL records and returns their `text` fields in file order.
- Memory is external to the model. The model does not own or rewrite records.
- The original implementation includes a RAM watchdog that adjusts `max_lines` and trims the file window when it exceeds the current line limit.

## Code

```python
import os
import json
import time
import hashlib
import threading
import queue
import gc
from pathlib import Path
from typing import List

# --- GOVERNOR CONFIG ---
# The RAM 'Red Line' (in kB) based on your ADB check
CRITICAL_RAM_KB = 350000  # Start aggressive trimming below 350MB

class AREStore:
    def __init__(self, fpath: Path):
        self.fpath = fpath
        self.lock = threading.RLock()
        self.q = queue.Queue()
        self._stop = False
        self.max_lines = 5000  # Default window
        
        # Initialize file
        self.fpath.parent.mkdir(parents=True, exist_ok=True)
        self.fpath.touch(exist_ok=True)

        # Start Threads: 1. Writer, 2. Memory Watchdog
        self._bg_writer = threading.Thread(target=self._writer_loop, daemon=True)
        self._bg_gov = threading.Thread(target=self._memory_watchdog, daemon=True)
        
        self._bg_writer.start()
        self._bg_gov.start()

    def _get_avail_kb(self):
        """Zero-Day check: Bypass OS and read Kernel directly"""
        try:
            with open('/proc/meminfo', 'r') as f:
                for line in f:
                    if 'MemAvailable' in line:
                        return int(line.split()[1])
        except: return 1000000 # Fallback

    def _memory_watchdog(self):
        """The Sentinel: Adjusts window size based on real-time RAM"""
        while not self._stop:
            avail = self._get_avail_kb()
            if avail < CRITICAL_RAM_KB:
                self.max_lines = 500 # Emergency Shrink
                gc.collect() # Force Python to release dead objects
            elif avail < 600000:
                self.max_lines = 2000 # Pre-emptive Warning
            else:
                self.max_lines = 5000 # Full Power
            time.sleep(10)

    def _writer_loop(self):
        while not self._stop:
            try:
                item = self.q.get(timeout=1.0)
                with self.lock, self.fpath.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(item, ensure_ascii=False) + "\n")
                self._trim_if_needed()
            except queue.Empty: continue

    def _trim_if_needed(self):
        try:
            with self.lock:
                lines = self.fpath.read_text().splitlines()
                if len(lines) > self.max_lines:
                    self.fpath.write_text("\n".join(lines[-self.max_lines:]) + "\n")
        except: pass

    def ingest(self, text: str):
        doc = {"ts": int(time.time()), "sha": hashlib.sha256(text.encode()).hexdigest()[:10], "text": text[:8000]}
        self.q.put(doc)

    def last_n(self, n: int) -> List[str]:
        try:
            lines = self.fpath.read_text().splitlines()
            return [json.loads(l).get("text", "") for l in lines[-n:]]
        except: return []

# GLOBAL INSTANCE
BASE_DIR = Path(__file__).resolve().parent
GLOBAL_ARE = AREStore(BASE_DIR / "are_data" / "are_mem.jsonl")

```
