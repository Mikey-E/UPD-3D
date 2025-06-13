"""
This script reads one or more .txt files containing lines in the format:
    sceneID@pointCloudID
For example: abcd@roomtype1-number

For each line, the program constructs a path:
    <base_dir>/<sceneID>/<pointCloudID>/<pointCloudID>.ply
It then opens the .ply file to determine the number of points (by reading the header or counting vertices)
and reports the average points per point cloud for each room type (extracted from the pointCloudID).
The script also supports a --rebalance flag
to move lines between the first two files to get closer to the ideal ratio.
A mandatory flag --base-dir specifies the base directory for point cloud files.
At this time they exist unzipped at /gscratch/melgin/3d-grand_unzipped/3D-FRONT. This is the --base-dir

example usage:
    python utils/room_type_points_stats.py file1.txt file2.txt --base-dir /dir1/dir2 --rebalance
"""

import os
import argparse
from collections import defaultdict

def extract_room_type(line):
    # Extracts the room type from a line.
    # For a line like "abcd@roomtype1-number", this returns "roomtype1" (i.e. the substring between '@' and '-').
    try:
        at_idx = line.index('@')
        dash_idx = line.index('-', at_idx)
        return line[at_idx+1:dash_idx]
    except ValueError:
        return None

def extract_scene_and_pc_id(line):
    # Splits a line into scene ID and point cloud ID.
    # For "abcd@roomtype1-number", returns ("abcd", "roomtype1-number")
    parts = line.split('@')
    if len(parts) != 2:
        return None, None
    return parts[0].strip(), parts[1].replace("\n", "").strip()

def get_point_count(ply_path):
    # Attempts to read the .ply file header to determine the number of vertices.
    # If "element vertex" is found, its value is returned;
    # otherwise, it counts the lines after "end_header" as a fallback.
    if not os.path.isfile(ply_path):
        print(f"PLY file not found: {ply_path}")
        return 0
    with open(ply_path, 'r', encoding='utf-8', errors='replace') as f:#Our (3D-FRONT) PLY files are UTF-8 encoded, but not all ply files are.
        vertex_count = None
        for line in f:
            line = line.strip()
            if line.startswith("element vertex"):
                try:
                    vertex_count = int(line.split()[-1])
                    return vertex_count
                except Exception:
                    pass
            if line == "end_header":
                break
        # Fallback: count remaining lines
        cnt = sum(1 for _ in f)
        return cnt

def process_file(txt_path, base_dir):
    if not os.path.isfile(txt_path):
        print(f"File not found: {txt_path}")
        return None, None
    with open(txt_path, 'r') as f:
        lines = [line.strip() for line in f if line.strip()]
    # For each line, open the corresponding .ply file and obtain its point count.
    groups = defaultdict(list)
    for line in lines:
        room = extract_room_type(line)
        if room is None:
            continue
        scene, pc_id = extract_scene_and_pc_id(line)
        if scene is None or pc_id is None:
            continue
        # Construct the path: base_dir/scene/pc_id/pc_id.ply
        ply_path = os.path.join(base_dir, scene, pc_id, f"{pc_id}.ply")
        pts = get_point_count(ply_path)
        groups[room].append(pts)
    averages = {}
    counts = {}
    for room, pts_list in groups.items():
        if pts_list:
            averages[room] = sum(pts_list) / len(pts_list)
            counts[room] = len(pts_list)
        else:
            averages[room] = 0
            counts[room] = 0
    return averages, counts

def main(txt_paths, base_dir):
    results = []   # List of dict: room -> average point count
    totals = []    # List of dict: room -> number of point clouds
    all_rooms = set()
    for path in txt_paths:
        averages, counts = process_file(path, base_dir)
        if averages is None:
            continue
        results.append(averages)
        totals.append(counts)
        all_rooms.update(averages.keys())
    all_rooms = sorted(all_rooms)
    file_labels = [os.path.basename(p) for p in txt_paths]
    # Print total number of point clouds (per file)
    for label, counts in zip(file_labels, totals):
        total_clouds = sum(counts.values())
        print(f"Total point clouds in {label}: {total_clouds:,}")
    print()
    # Header
    header = f"{'Room Type':<20}" + "".join([f"{label:>20}" for label in file_labels])
    print(header)
    print("-" * (20 + 20 * len(file_labels)))
    # Rows of average points per room type
    for room in all_rooms:
        row = f"{room:<20}"
        for averages in results:
            avg_int = int(round(averages.get(room, 0)))
            row += f"{avg_int:>20,d}"
        print(row)
    return results, totals

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process one or more .txt files containing lines of the form scene@PointCloudID, "
                                                 "reporting the average point count (from corresponding .ply files) per room type. "
                                                 "Also supports a rebalance option to trade lines on a 1-to-1 basis to balance averages.")
    parser.add_argument("files", nargs='+', help="Path(s) to .txt file(s)")
    parser.add_argument("--base-dir", type=str, required=True, help="Base directory for point cloud files")
    parser.add_argument("--rebalance", action="store_true", help="Perform 1-to-1 trading of lines to balance average point counts per room type")
    args = parser.parse_args()

    results, totals = main(args.files, args.base_dir)

    # Perform rebalancing if requested.
    if args.rebalance and len(args.files) >= 2:
        file1_path = args.files[0]
        file2_path = args.files[1]
        with open(file1_path, 'r') as f:
            file1_lines = f.readlines()
        with open(file2_path, 'r') as f:
            file2_lines = f.readlines()
        
        from collections import defaultdict
        mapping1 = defaultdict(list)  # room type -> list of (index, line, point_count)
        mapping2 = defaultdict(list)
        for idx, line in enumerate(file1_lines):
            rt = extract_room_type(line)
            if rt:
                scene, pc_id = extract_scene_and_pc_id(line)
                ply_path = os.path.join(args.base_dir, scene, pc_id, f"{pc_id}.ply")
                pts = get_point_count(ply_path)
                mapping1[rt].append((idx, line, pts))
        for idx, line in enumerate(file2_lines):
            rt = extract_room_type(line)
            if rt:
                scene, pc_id = extract_scene_and_pc_id(line)
                ply_path = os.path.join(args.base_dir, scene, pc_id, f"{pc_id}.ply")
                pts = get_point_count(ply_path)
                mapping2[rt].append((idx, line, pts))
        
        # For every room type present in both files, apply the new rebalancing algorithm.
        for rt in set(mapping1.keys()) & set(mapping2.keys()):
            list1 = mapping1[rt]  # from file1
            list2 = mapping2[rt]  # from file2
            n1 = len(list1)
            n2 = len(list2)
            sum1 = sum(item[2] for item in list1)
            sum2 = sum(item[2] for item in list2)
            avg1 = sum1 / n1
            avg2 = sum2 / n2
            improved = True
            while improved:
                improved = False
                for i in range(n1):
                    for j in range(n2):
                        a_idx, a_line, a_pts = list1[i]
                        b_idx, b_line, b_pts = list2[j]
                        new_sum1 = sum1 - a_pts + b_pts
                        new_sum2 = sum2 - b_pts + a_pts
                        new_avg1 = new_sum1 / n1
                        new_avg2 = new_sum2 / n2
                        if abs(new_avg1 - new_avg2) < abs(avg1 - avg2):
                            # Swap the two: file1 gets b's entry and file2 gets a's entry.
                            list1[i] = (a_idx, b_line, b_pts)
                            list2[j] = (b_idx, a_line, a_pts)
                            sum1 = new_sum1
                            sum2 = new_sum2
                            avg1 = new_avg1
                            avg2 = new_avg2
                            improved = True
                            # Restart both loops on a successful swap.
                            break
                    if improved:
                        break
            # Update file lines with the new mappings.
            for item in list1:
                idx, line, pts = item
                file1_lines[idx] = line
            for item in list2:
                idx, line, pts = item
                file2_lines[idx] = line
        with open(file1_path, 'w') as f:
            f.writelines(file1_lines)
        with open(file2_path, 'w') as f:
            f.writelines(file2_lines)
        print("\nRebalancing complete. Files have been updated.")