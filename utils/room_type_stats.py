"""
This script reads one or more .txt files containing scene@RoomType-... keys (one per line),
extracts the room type, and prints a table with the absolute count and percentage for each room type
in each file, as well as the total count for each file.

example usage: python utils/room_type_stats.py pcl_lists/v1.txt pcl_lists/v2.txt
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

def process_file(txt_path):
    if not os.path.isfile(txt_path):
        print(f"File not found: {txt_path}")
        return None, None

    with open(txt_path, 'r') as f:
        lines = [line.strip() for line in f if line.strip()]

    room_types = [extract_room_type(line) for line in lines]
    room_types = [rt for rt in room_types if rt is not None]

    total = len(room_types)
    counter = Counter(room_types)
    return counter, total

def main(txt_paths):
    results = []
    totals = []
    all_room_types = set()

    for path in txt_paths:
        counter, total = process_file(path)
        if counter is None:
            continue
        results.append(counter)
        totals.append(total)
        all_room_types.update(counter.keys())

    all_room_types = sorted(all_room_types)
    file_labels = [os.path.basename(p) for p in txt_paths]

    # Print totals for each file
    for label, total in zip(file_labels, totals):
        print(f"Total entries in {label}: {total}")
    print()

    # Header
    header = f"{'Room Type':<20}" + "".join([f"{label:>20}" for label in file_labels])
    print(header)
    print("-" * (20 + 20 * len(file_labels)))

    # Rows
    for room in all_room_types:
        row = f"{room:<20}"
        for counter, total in zip(results, totals):
            count = counter.get(room, 0)
            percent = (count / total) * 100 if total > 0 else 0
            count_percent = f"{count} ({percent:.2f}%)"
            row += f"{count_percent:>20}"
        print(row)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python room_type_stats.py /path/to/list1.txt [/path/to/list2.txt ...]")
    else:
        main(sys.argv[1:])