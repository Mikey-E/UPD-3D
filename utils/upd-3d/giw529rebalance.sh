#!/bin/bash

# Script to rebalance GIW529 dataset into train/test splits with:
# 1. 3:1 train:test ratio by scene count per category
# 2. Balanced average point counts per category between train and test

set -e  # Exit on any error

# Paths
BASE_DIR="/project/3dllms/melgin/UPD-3D"
PCL_LISTS_DIR="${BASE_DIR}/pcl_lists"
UTILS_DIR="${BASE_DIR}/utils/upd-3d"
POINT_CLOUD_BASE="/project/3dllms/melgin/datasets/GIW/giw529subcat"

INPUT_FILE="${PCL_LISTS_DIR}/GIW529.txt"
TRAIN_FILE="${PCL_LISTS_DIR}/GIW529_train.txt"
TEST_FILE="${PCL_LISTS_DIR}/GIW529_test.txt"

echo "========================================"
echo "GIW529 Dataset Rebalancing Pipeline"
echo "========================================"
echo ""

# Check if input file exists
if [ ! -f "$INPUT_FILE" ]; then
    echo "Error: Input file not found: $INPUT_FILE"
    exit 1
fi

# Count total lines
TOTAL_LINES=$(wc -l < "$INPUT_FILE")
echo "Total scenes in GIW529.txt: $TOTAL_LINES"
echo ""

# Step 1: Split the file in half to create initial train and test sets
echo "Step 1: Creating initial 50/50 split..."
HALF_LINES=$((TOTAL_LINES / 2))

head -n "$HALF_LINES" "$INPUT_FILE" > "$TRAIN_FILE"
tail -n +$((HALF_LINES + 1)) "$INPUT_FILE" > "$TEST_FILE"

TRAIN_COUNT=$(wc -l < "$TRAIN_FILE")
TEST_COUNT=$(wc -l < "$TEST_FILE")
echo "  Initial train set: $TRAIN_COUNT scenes"
echo "  Initial test set: $TEST_COUNT scenes"
echo ""

# Step 2: Rebalance by category counts (3:1 ratio)
echo "Step 2: Rebalancing category scene counts (3:1 train:test ratio)..."
echo "----------------------------------------"
python "$UTILS_DIR/room_type_stats.py" "$TRAIN_FILE" "$TEST_FILE" --ratio 3:1 --rebalance
echo ""

# Print post-rebalance category stats
echo "Category distribution after scene count rebalancing:"
echo "----------------------------------------"
python "$UTILS_DIR/room_type_stats.py" "$TRAIN_FILE" "$TEST_FILE"
echo ""

# Step 3: Rebalance by average point counts per category
echo "Step 3: Rebalancing average point counts per category (1:1 swaps)..."
echo "----------------------------------------"
python "$UTILS_DIR/room_type_points_stats.py" "$TRAIN_FILE" "$TEST_FILE" \
    --base-dir "$POINT_CLOUD_BASE" --rebalance
echo ""

echo "========================================"
echo "Rebalancing Complete!"
echo "========================================"
echo ""
echo "Output files:"
echo "  Train: $TRAIN_FILE"
echo "  Test: $TEST_FILE"
echo ""

# Final summary
FINAL_TRAIN=$(wc -l < "$TRAIN_FILE")
FINAL_TEST=$(wc -l < "$TEST_FILE")
RATIO=$(echo "scale=2; $FINAL_TRAIN / $FINAL_TEST" | bc)
echo "Final counts:"
echo "  Train: $FINAL_TRAIN scenes"
echo "  Test: $FINAL_TEST scenes"
echo "  Ratio: ${RATIO}:1"
