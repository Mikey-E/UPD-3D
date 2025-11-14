"""
This script reads one or more .txt files containing scene@RoomType-... keys (one per line),
extracts the room type, and prints a table with the absolute count and percentage for each room type
in each file, as well as the total count for each file.

example usage: python utils/room_type_stats.py pcl_lists/v1.txt pcl_lists/v2.txt
ratio flag can be used to specify an ideal ratio between the first two files.
"""

import sys
import os
from collections import Counter

def extract_room_type(line):
    try:
        at_idx = line.index('@')
        # For GIW format (Category@identifier), extract the category (before @)
        category = line[:at_idx].strip()
        if category:
            # Check if there's a dash after @ (original format: scene@RoomType-number)
            try:
                dash_idx = line.index('-', at_idx)
                # Original format: extract room type between @ and -
                return line[at_idx+1:dash_idx]
            except ValueError:
                # GIW format: return the category before @
                return category
        return None
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
    import argparse
    parser = argparse.ArgumentParser(description="Process one or more .txt files containing scene@RoomType-... keys and optionally adjust room type counts between first two files to reach a given ratio.")
    parser.add_argument("files", nargs='+', help="Path(s) to .txt file(s)")
    parser.add_argument("--ratio", type=str, help="Ideal ratio for first file to second file in the form number1:number2")
    parser.add_argument("--rebalance", action="store_true", help="Actually perform the rebalancing moves between the first two files based on the ratio flag")
    args = parser.parse_args()

    main(args.files)

    # If ratio flag specified and at least 2 files given, compute adjustments
    if args.ratio and len(args.files) >= 2:
        try:
            x_str, y_str = args.ratio.split(":")
            x = float(x_str)
            y = float(y_str)
        except Exception:
            print("Error: ratio must be in the form number1:number2")
            sys.exit(1)

        counter1, total1 = process_file(args.files[0])
        counter2, total2 = process_file(args.files[1])
        all_rooms = sorted(set(list(counter1.keys()) + list(counter2.keys())))

        print(f"\nAdjustments to reach ratio {args.ratio} between {os.path.basename(args.files[0])} and {os.path.basename(args.files[1])}:")
        adjustments = {}
        for room in all_rooms:
            c1 = counter1.get(room, 0)
            c2 = counter2.get(room, 0)
            # Compute delta: positive means move from file1 to file2; negative means move from file2 to file1.
            delta = (y * c1 - x * c2) / (x + y)
            move = int(round(delta))
            adjustments[room] = move
            if move > 0:
                print(f"{room:<20}: move {move} from {os.path.basename(args.files[0])} to {os.path.basename(args.files[1])}")
            elif move < 0:
                print(f"{room:<20}: move {abs(move)} from {os.path.basename(args.files[1])} to {os.path.basename(args.files[0])}")
            else:
                print(f"{room:<20}: no move needed")

        # If --rebalance flag is specified, actually perform the moves between the first two files.
        if args.rebalance:
            # Read all lines from both files
            file1_path = args.files[0]
            file2_path = args.files[1]
            with open(file1_path, 'r') as f:
                file1_lines = f.readlines()
            with open(file2_path, 'r') as f:
                file2_lines = f.readlines()

            # Ensure the last line of each file ends with a newline to avoid concatenation.
            if file1_lines and not file1_lines[-1].endswith("\n"):
                file1_lines[-1] = file1_lines[-1] + "\n"
            if file2_lines and not file2_lines[-1].endswith("\n"):
                file2_lines[-1] = file2_lines[-1] + "\n"

            # Function to remove up-to N lines matching a room type from a list of lines.
            def remove_lines(lines, room, n):
                removed = []
                new_lines = []
                count = 0
                for line in lines:
                    rt = extract_room_type(line)
                    if count < n and rt == room:
                        removed.append(line)
                        count += 1
                    else:
                        new_lines.append(line)
                return new_lines, removed

            # Process each room type adjustment
            # Positive move: remove from file1 and append to file2.
            # Negative move: remove from file2 and append to file1.
            for room, move in adjustments.items():
                if move > 0:
                    file1_lines, removed = remove_lines(file1_lines, room, move)
                    file2_lines.extend(removed)
                elif move < 0:
                    n = abs(move)
                    file2_lines, removed = remove_lines(file2_lines, room, n)
                    file1_lines.extend(removed)
                # move==0: do nothing

            # Write the updated contents back to the files
            with open(file1_path, 'w') as f:
                f.writelines(file1_lines)
            with open(file2_path, 'w') as f:
                f.writelines(file2_lines)
            print("\nRebalancing complete. Files have been updated.")