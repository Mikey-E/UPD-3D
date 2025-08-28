# This script processes three input paths provided via command-line arguments.
# It reads a list of identifier@scene entries from a pcl_list file and creates softlinks in the specified directory,
# linking each softlink to the corresponding .ply file in the unpacked point clouds directory.
# Usage: python process_paths.py <path_where_softlinks_will_go> <pcl_list> <unpacked_point_clouds>
# This is to *effectively* add data to the objaverse folder, so MiniGPT-3D can be trained on it alongside the text samples added to, say, PointLLM_brief_description_660K.json, and alongside adding the identifier@scene entries to the object_ids_660K.txt file.

import os
import argparse

def main():
    parser = argparse.ArgumentParser(description="Process three input paths.")
    parser.add_argument("path_where_softlinks_will_go", type=str, help="Path where softlinks live (this is expected to be the objaverse folder, where soft-links to .ply files will be made).")
    parser.add_argument("pcl_list", type=str, help="Path to the pcl_list .txt file. This file contains a list of point cloud files to make soft links to.")
    parser.add_argument("unpacked_point_clouds", type=str, help="Path to unpacked point clouds directory (e.g. /gscratch/melgin/3d-grand_unzipped/3D-FRONT).")
    parser.add_argument("--execute", action="store_true", help="Actually create softlinks. Dry-run by default.")
    parser.add_argument("--extra_scene_folder", action="store_true", help="Place an extra scene folder in the path, useful for 3D-FRONT.")

    args = parser.parse_args()
    dry_run = not args.execute

    print("Path where softlinks live:", args.path_where_softlinks_will_go)
    print("PCL list:", args.pcl_list)
    print("Unpacked point clouds:", args.unpacked_point_clouds)
    print("Mode:", "Execute" if not dry_run else "Dry-run")

    count = 0
    # Process pcl_list file and create or simulate softlinks
    with open(args.pcl_list, "r") as f:
        for line in f:
            line = line.strip()
            if not line or "@" not in line:
                continue
            identifier, scene = line.split("@", 1)
            if args.extra_scene_folder:
                src = os.path.join(args.unpacked_point_clouds, identifier, scene, f"{scene}.ply")
            else:
                src = os.path.join(args.unpacked_point_clouds, identifier, f"{scene}.ply")
            dest = os.path.join(args.path_where_softlinks_will_go, f"{identifier}@{scene}.ply")
            if dry_run:
                print(f"[Dry-run] Would create softlink: {dest} -> {src}")
            else:
                try:
                    os.symlink(src, dest)
                    print(f"Created softlink: {dest} -> {src}")
                except FileExistsError:
                    print(f"Softlink already exists: {dest}")
                except Exception as e:
                    print(f"Error creating softlink for {line}: {e}")
            count += 1
            if dry_run and count >= 10:
                break

if __name__ == "__main__":
    main()