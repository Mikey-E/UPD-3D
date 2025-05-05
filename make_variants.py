"""Expects open_ended and standard_answer base sets to have been generated first."""

import argparse
import os

# Set up argument parser
parser = argparse.ArgumentParser(description="Generate upd variants based on the standard_answer and open_ended base sets.")
parser.add_argument("folder", type=str, help="Name of the folder inside upd_text/")

args = parser.parse_args()

input_folder = os.path.join("upd_text", args.folder, "standard_answer")

additional_instruction = "If none of the above answers are correct, answer: 'f'"

def make_standard(input_folder=input_folder):
    """Generate standard variants from the standard_answer base set."""
    output_folder = os.path.join("upd_text", args.folder, "standard")
    os.makedirs(output_folder, exist_ok=True)

    # Process each file in the input folder
    for filename in os.listdir(input_folder):
        input_file_path = os.path.join(input_folder, filename)
        output_file_path = os.path.join(output_folder, filename)

        # Read the contents of the current file
        with open(input_file_path, 'r') as infile:
            lines = infile.readlines()

        # Remove last 2 lines
        lines = lines[:-2]

        # Write the remaining lines to the output file
        with open(output_file_path, 'w') as outfile:
            outfile.writelines(lines)

def make_aad(input_folder=input_folder):
    """Generate aad variants from the standard_answer base set."""
    output_folder_base = os.path.join("upd_text", args.folder, "aad_base")
    output_folder_ao = os.path.join("upd_text", args.folder, "aad_additional_option")
    output_folder_ai = os.path.join("upd_text", args.folder, "aad_additional_instruction")
    os.makedirs(output_folder_base, exist_ok=True)
    os.makedirs(output_folder_ao, exist_ok=True)
    os.makedirs(output_folder_ai, exist_ok=True)

    # Process each file in the input folder
    for filename in os.listdir(input_folder):
        input_file_path = os.path.join(input_folder, filename)
        output_file_path_base = os.path.join(output_folder_base, filename)
        output_file_path_ao = os.path.join(output_folder_ao, filename)
        output_file_path_ai = os.path.join(output_folder_ai, filename)

        # Read the contents of the current file
        with open(input_file_path, 'r') as infile:
            lines = infile.readlines()

        correct_answer = lines[-1].strip().split(" ")[-1]
        lines = [line for line in lines if correct_answer + ")" not in line]

        # Remove last 2 lines
        lines = lines[:-2]

        # Write the remaining lines to the output file
        with open(output_file_path_base, 'w') as outfile:
            outfile.writelines(lines)
        with open(output_file_path_ao, 'w') as outfile:
            lines.append("\ne) none of the above")
            outfile.writelines(lines)
        with open(output_file_path_ai, 'w') as outfile:
            lines = lines[:-1]
            lines.append("\n" + additional_instruction)
            outfile.writelines(lines)

def make_iasd(input_folder=os.path.join("upd_text", args.folder, "standard")):
    """Generate iasd variants from the standard_answer base set."""
    output_folder_base = os.path.join("upd_text", args.folder, "iasd_base")
    output_folder_ao = os.path.join("upd_text", args.folder, "iasd_additional_option")
    output_folder_ai = os.path.join("upd_text", args.folder, "iasd_additional_instruction")
    os.makedirs(output_folder_base, exist_ok=True)
    os.makedirs(output_folder_ao, exist_ok=True)
    os.makedirs(output_folder_ai, exist_ok=True)

    # Process each file in the input folder
    filenames = os.listdir(input_folder)
    for i in range(len(filenames)):
        filename = filenames[i]
        input_file_path = os.path.join(input_folder, filenames[i])
        next_file_path = os.path.join(input_folder, filenames[i + 1]) if i + 1 < len(filenames) else os.path.join(input_folder, filenames[0])

        output_file_path_base = os.path.join(output_folder_base, filename)
        output_file_path_ao = os.path.join(output_folder_ao, filename)
        output_file_path_ai = os.path.join(output_folder_ai, filename)

        # Read the contents of the current file
        with open(input_file_path, 'r') as infile:
            lines = infile.readlines()
            question = [lines[0].strip()]
        with open(next_file_path, 'r') as infile:
            lines_next = infile.readlines()
            answers = lines_next[1:]
        
        new_sample = question + answers

        # Write the remaining lines to the output file
        with open(output_file_path_base, 'w') as outfile:
            outfile.writelines(new_sample)
        with open(output_file_path_ao, 'w') as outfile:
            new_sample.append("\ne) none of the above")
            outfile.writelines(new_sample)
        with open(output_file_path_ai, 'w') as outfile:
            new_sample = new_sample[:-1]
            new_sample.append("\n" + additional_instruction)
            outfile.writelines(new_sample)
#------------------------------------
def main():
    # make_standard()
    # make_aad()
    make_iasd()

if __name__ == "__main__":
    main()