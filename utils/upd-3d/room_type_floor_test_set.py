"""
This script ensures that every category has at least one file in the test set.

PREREQUISITE: This script should be run AFTER:
    1. room_type_stats.py (with --ratio and --rebalance flags)
    2. room_type_points_stats.py (with --rebalance flag)

Purpose:
After the initial rebalancing steps, some categories may have 0 files in the test set
(especially when the category has very few total files and the 3:1 ratio puts all files in train).
This script identifies such categories and moves exactly one file from the train set to the 
test set for each affected category, ensuring every category has at least one test sample.

Usage:
    python room_type_floor_test_set.py <train_file> <test_file>

Example:
    python utils/upd-3d/room_type_floor_test_set.py pcl_lists/GIW529_train.txt pcl_lists/GIW529_test.txt
"""

import sys
import os
from collections import defaultdict

def extract_room_type(line):
    """
    Extracts the room type/category from a line.
    For GIW format "Category@identifier", returns "Category".
    For original format "scene@RoomType-number", returns "RoomType" (substring between '@' and '-').
    """
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

def analyze_categories(train_lines, test_lines):
    """
    Analyzes which categories exist in train and test sets.
    Returns:
        train_by_category: dict mapping category -> list of (line_index, line)
        test_by_category: dict mapping category -> list of (line_index, line)
        categories_needing_test: set of categories with 0 test files
    """
    train_by_category = defaultdict(list)
    test_by_category = defaultdict(list)
    
    for idx, line in enumerate(train_lines):
        line = line.strip()
        if not line:
            continue
        category = extract_room_type(line)
        if category:
            train_by_category[category].append((idx, line))
    
    for idx, line in enumerate(test_lines):
        line = line.strip()
        if not line:
            continue
        category = extract_room_type(line)
        if category:
            test_by_category[category].append((idx, line))
    
    # Find categories with 0 test files but at least 1 train file
    all_categories = set(train_by_category.keys()) | set(test_by_category.keys())
    categories_needing_test = set()
    
    for category in all_categories:
        test_count = len(test_by_category.get(category, []))
        train_count = len(train_by_category.get(category, []))
        if test_count == 0 and train_count > 0:
            categories_needing_test.add(category)
    
    return train_by_category, test_by_category, categories_needing_test

def move_files_to_test(train_file_path, test_file_path):
    """
    Moves one file from train to test for each category that has 0 test files.
    """
    # Read both files
    with open(train_file_path, 'r') as f:
        train_lines = f.readlines()
    with open(test_file_path, 'r') as f:
        test_lines = f.readlines()
    
    # Analyze categories
    train_by_category, test_by_category, categories_needing_test = analyze_categories(train_lines, test_lines)
    
    if not categories_needing_test:
        print("All categories already have at least one test file. No changes needed.")
        return
    
    print(f"Found {len(categories_needing_test)} categories with 0 test files:")
    for category in sorted(categories_needing_test):
        train_count = len(train_by_category[category])
        print(f"  - {category}: {train_count} train files, 0 test files")
    print()
    
    # Move one file from train to test for each affected category
    lines_to_move = []
    indices_to_remove = set()
    
    for category in sorted(categories_needing_test):
        # Get the first file from this category in the train set
        first_file_idx, first_file_line = train_by_category[category][0]
        lines_to_move.append(first_file_line if first_file_line.endswith('\n') else first_file_line + '\n')
        indices_to_remove.add(first_file_idx)
    
    # Create new train lines (excluding moved files)
    new_train_lines = [line for idx, line in enumerate(train_lines) if idx not in indices_to_remove]
    
    # Add moved lines to test set
    new_test_lines = test_lines + lines_to_move
    
    # Write updated files
    with open(train_file_path, 'w') as f:
        f.writelines(new_train_lines)
    with open(test_file_path, 'w') as f:
        f.writelines(new_test_lines)
    
    print(f"Moved {len(lines_to_move)} files from train to test:")
    for category in sorted(categories_needing_test):
        print(f"  - {category}: 1 file moved")
    print()
    
    # Print summary
    old_train_count = len(train_lines)
    old_test_count = len(test_lines)
    new_train_count = len(new_train_lines)
    new_test_count = len(new_test_lines)
    
    print("Summary:")
    print(f"  Train set: {old_train_count} -> {new_train_count} files (moved {old_train_count - new_train_count})")
    print(f"  Test set: {old_test_count} -> {new_test_count} files (added {new_test_count - old_test_count})")
    
    if new_train_count > 0:
        ratio = new_train_count / new_test_count
        print(f"  New ratio: {ratio:.2f}:1")

def main():
    if len(sys.argv) != 3:
        print("Usage: python room_type_floor_test_set.py <train_file> <test_file>")
        print()
        print("Example:")
        print("  python utils/upd-3d/room_type_floor_test_set.py pcl_lists/GIW529_train.txt pcl_lists/GIW529_test.txt")
        sys.exit(1)
    
    train_file = sys.argv[1]
    test_file = sys.argv[2]
    
    # Validate files exist
    if not os.path.isfile(train_file):
        print(f"Error: Train file not found: {train_file}")
        sys.exit(1)
    if not os.path.isfile(test_file):
        print(f"Error: Test file not found: {test_file}")
        sys.exit(1)
    
    print("="*60)
    print("Ensuring Minimum Test Set Coverage per Category")
    print("="*60)
    print()
    print(f"Train file: {train_file}")
    print(f"Test file: {test_file}")
    print()
    
    move_files_to_test(train_file, test_file)
    
    print()
    print("="*60)
    print("Floor test set operation complete!")
    print("="*60)

if __name__ == "__main__":
    main()
