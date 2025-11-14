"""
Creates validation split from training set.

This script splits a training set into:
1. train_minus_val: The remaining training samples after validation is extracted
2. val_subset_of_train: A validation subset taken from the original training set

Strategy (Option B - Minimum coverage with proportional distribution):
- Ensure each category with 4+ train samples has at least 1 validation sample
- Distribute remaining validation slots proportionally across categories
- Target ~25% of train set for validation (similar to Crops3D)

Usage:
    python create_val_split.py <train_file> <output_prefix>

Example:
    python utils/upd-3d/create_val_split.py pcl_lists/GIW529_train.txt pcl_lists/GIW529
    
    This creates:
        pcl_lists/GIW529_val_subset_of_train.txt
        pcl_lists/GIW529_train_minus_val.txt
"""

import sys
import os
import random
from collections import defaultdict

def extract_room_type(line):
    """
    Extracts the room type/category from a line.
    For GIW format "Category@identifier", returns "Category".
    For original format "scene@RoomType-number", returns "RoomType" (substring between '@' and '-').
    """
    try:
        at_idx = line.index('@')
        category = line[:at_idx].strip()
        if category:
            try:
                dash_idx = line.index('-', at_idx)
                return line[at_idx+1:dash_idx]
            except ValueError:
                return category
        return None
    except ValueError:
        return None

def create_val_split(train_file, output_prefix, target_val_ratio=0.25, random_seed=42):
    """
    Splits training file into train_minus_val and val_subset_of_train.
    
    Args:
        train_file: Path to the training file
        output_prefix: Prefix for output files (e.g., "pcl_lists/GIW529")
        target_val_ratio: Target ratio of validation samples (default 0.25 = 25%)
        random_seed: Random seed for reproducibility
    """
    random.seed(random_seed)
    
    # Read training file
    with open(train_file, 'r') as f:
        train_lines = [line for line in f if line.strip()]
    
    total_train = len(train_lines)
    target_val_count = int(total_train * target_val_ratio)
    
    print(f"Total training samples: {total_train}")
    print(f"Target validation samples: {target_val_count} ({target_val_ratio*100:.1f}%)")
    print()
    
    # Group by category
    by_category = defaultdict(list)
    for idx, line in enumerate(train_lines):
        category = extract_room_type(line.strip())
        if category:
            by_category[category].append((idx, line))
    
    print(f"Found {len(by_category)} categories")
    print()
    
    # Step 1: Allocate 1 val sample to each category with 4+ train samples
    val_indices = set()
    category_val_counts = defaultdict(int)
    
    for category, samples in sorted(by_category.items()):
        if len(samples) >= 4:
            # Randomly select 1 sample for validation
            selected = random.choice(samples)
            val_indices.add(selected[0])
            category_val_counts[category] = 1
    
    print(f"Step 1: Allocated {len(val_indices)} samples (1 per category with 4+ train samples)")
    print()
    
    # Step 2: Distribute remaining val slots proportionally
    remaining_val_slots = target_val_count - len(val_indices)
    
    if remaining_val_slots > 0:
        # Calculate how many additional val samples each category should get
        # based on their proportion of the remaining training samples
        remaining_samples = []
        for category, samples in by_category.items():
            # Get samples not yet in validation
            available = [s for s in samples if s[0] not in val_indices]
            if available:
                remaining_samples.append((category, available))
        
        # Calculate proportional allocation
        total_remaining = sum(len(samples) for _, samples in remaining_samples)
        allocations = []
        
        for category, samples in remaining_samples:
            proportion = len(samples) / total_remaining
            additional = int(proportion * remaining_val_slots)
            if additional > 0 and additional < len(samples):
                allocations.append((category, samples, additional))
        
        # Allocate additional val samples
        additional_count = 0
        for category, samples, count in allocations:
            selected = random.sample(samples, count)
            for idx, line in selected:
                val_indices.add(idx)
                category_val_counts[category] += 1
                additional_count += 1
        
        print(f"Step 2: Allocated {additional_count} additional samples proportionally")
        print()
    
    # Create output lists
    val_lines = []
    train_minus_val_lines = []
    
    for idx, line in enumerate(train_lines):
        if idx in val_indices:
            val_lines.append(line)
        else:
            train_minus_val_lines.append(line)
    
    # Write output files
    val_file = f"{output_prefix}_val_subset_of_train.txt"
    train_minus_val_file = f"{output_prefix}_train_minus_val.txt"
    
    with open(val_file, 'w') as f:
        f.writelines(val_lines)
    
    with open(train_minus_val_file, 'w') as f:
        f.writelines(train_minus_val_lines)
    
    print("="*60)
    print("Validation Split Complete")
    print("="*60)
    print()
    print(f"Output files:")
    print(f"  Validation: {val_file} ({len(val_lines)} samples)")
    print(f"  Train-minus-val: {train_minus_val_file} ({len(train_minus_val_lines)} samples)")
    print()
    print(f"Actual validation ratio: {len(val_lines)/total_train*100:.1f}%")
    print()
    
    # Print category distribution
    print("Validation samples per category:")
    for category in sorted(category_val_counts.keys()):
        total = len(by_category[category])
        val_count = category_val_counts[category]
        print(f"  {category:20} {val_count}/{total} samples in validation")

def main():
    if len(sys.argv) < 3:
        print("Usage: python create_val_split.py <train_file> <output_prefix>")
        print()
        print("Example:")
        print("  python utils/upd-3d/create_val_split.py pcl_lists/GIW529_train.txt pcl_lists/GIW529")
        print()
        print("This creates:")
        print("  <output_prefix>_val_subset_of_train.txt")
        print("  <output_prefix>_train_minus_val.txt")
        sys.exit(1)
    
    train_file = sys.argv[1]
    output_prefix = sys.argv[2]
    
    if not os.path.isfile(train_file):
        print(f"Error: Train file not found: {train_file}")
        sys.exit(1)
    
    create_val_split(train_file, output_prefix)

if __name__ == "__main__":
    main()
