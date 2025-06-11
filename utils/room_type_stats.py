"""
This script reads a .txt file containing scene@RoomType-... keys (one per line),
extracts the room type, and prints both the absolute count and percentage for each room type.

example usage: python utils/room_type_stats.py pcl_lists/v1.txt
"""

import sys
import os
from collections import Counter

def extract_room_type(line):
    try:
        at_idx = line.index('@')
        dash_idx = line.index('-', at_idx)
        return line[at_idx+1:dash_idx]
    except ValueError:
        return None

def main(txt_path):
    if not os.path.isfile(txt_path):
        print(f"File not found: {txt_path}")
        return

    with open(txt_path, 'r') as f:
        lines = [line.strip() for line in f if line.strip()]

    room_types = [extract_room_type(line) for line in lines]
    room_types = [rt for rt in room_types if rt is not None]

    total = len(room_types)
    counter = Counter(room_types)

    print(f"Total entries: {total}\n")
    print(f"{'Room Type':<20} {'Count (Percent)':>20}")
    print("-" * 40)
    for room in sorted(counter.keys()):
        count = counter[room]
        percent = (count / total) * 100 if total > 0 else 0
        count_percent = f"{count} ({percent:.2f}%)"
        print(f"{room:<20} {count_percent:>20}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python room_type_stats.py /path/to/list.txt")
    else:
        main(sys.argv[1])