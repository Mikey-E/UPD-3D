import argparse

# Set up argument parser
parser = argparse.ArgumentParser(description="Generate a .txt file listing point cloud files from 3D-FRONT data.")
parser.add_argument("txt_file", type=str, help="Name of the .txt file to create")
parser.add_argument("data_path", type=str, help="Path to the unpacked 3D-FRONT data")

# Parse arguments
args = parser.parse_args()

txt_file = args.txt_file
data_path = args.data_path

import os

def make_pcl_list(txt_file, data_path):
    with open(os.path.join("pcl_lists", txt_file), 'w') as f:
        dirs = os.listdir(data_path)
        for i, dir in enumerate(dirs):
            subdirs = os.listdir(os.path.join(data_path, dir))
            for j, subdir in enumerate(subdirs):
                if i == len(dirs) - 1 and j == len(subdirs) - 1:
                    f.write(dir + '@' + subdir)
                else:
                    f.write(dir + '@' + subdir + '\n')

if __name__ == "__main__":
    make_pcl_list(txt_file, data_path)