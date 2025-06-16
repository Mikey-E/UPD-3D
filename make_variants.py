"""Expects open_ended and standard_answer base sets to have been generated first."""

import argparse
import os

# Set up argument parser
parser = argparse.ArgumentParser(description="Generate upd variants based on the standard_answer and open_ended base sets.")
parser.add_argument("folder", type=str, help="Name of the folder inside upd_text/")
args = parser.parse_args()

standard_answer_folder = os.path.join("upd_text", args.folder, "standard_answer")

additional_instruction = "If none of the above answers are correct, answer: 'F'"

def make_standard(input_folder=standard_answer_folder):
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

def make_aad(input_folder=standard_answer_folder):
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

        correct_answer = lines[-1].strip().split(" ")[-1] #Correct answer is last char
        lines = [line for line in lines if correct_answer + "." not in line[0:2]]

        # Remove last 2 lines
        lines = lines[:-2]

        # Ensure the letters still go in order starting with A.
        new_lines = []
        letter = ord('A')
        for line in lines:
            if line.strip() and len(line) > 1 and line[1] == '.':
                new_lines.append(chr(letter) + line[1:])
                letter += 1
            else:
                new_lines.append(line)
        lines = new_lines

        # Write the remaining lines to the output file
        with open(output_file_path_base, 'w') as outfile:
            outfile.writelines(lines)
        with open(output_file_path_ao, 'w') as outfile:
            # Remove trailing newline from the last line if present
            if lines and lines[-1].endswith("\n"):
                lines[-1] = lines[-1].rstrip("\n")
            last_letter = lines[-1][0] if lines else 'A'
            next_letter = chr(ord(last_letter) + 1)
            lines.append(f"\n{next_letter}. none of the above")
            outfile.writelines(lines)
        with open(output_file_path_ai, 'w') as outfile:
            lines = lines[:-1]
            if lines and lines[-1].endswith("\n"):
                lines[-1] = lines[-1].rstrip("\n")
            lines.append("\n" + additional_instruction)
            outfile.writelines(lines)

def make_iasd(input_folder=os.path.join("upd_text", args.folder, "iasd_base")):
    """Generate iasd variants from the standard_answer base set."""
    output_folder_ao = os.path.join("upd_text", args.folder, "iasd_additional_option")
    output_folder_ai = os.path.join("upd_text", args.folder, "iasd_additional_instruction")
    os.makedirs(output_folder_ao, exist_ok=True)
    os.makedirs(output_folder_ai, exist_ok=True)

    # Process each file in the input folder
    filenames = os.listdir(input_folder)
    for i in range(len(filenames)):
        filename = filenames[i]
        input_file_path = os.path.join(input_folder, filenames[i])
        output_file_path_ao = os.path.join(output_folder_ao, filename)
        output_file_path_ai = os.path.join(output_folder_ai, filename)

        # Read the contents of the current file
        with open(input_file_path, 'r') as infile:
            lines = infile.readlines()
        
        # Prepare additional option version using a copy
        ao_sample = lines[:]
        if ao_sample and ao_sample[-1].endswith("\n"):
            ao_sample[-1] = ao_sample[-1].rstrip("\n")
        last_letter = ao_sample[-1][0] if ao_sample else 'A'
        next_letter = chr(ord(last_letter) + 1)
        ao_sample.append(f"\n{next_letter}. none of the above")
        with open(output_file_path_ao, 'w') as outfile:
            outfile.writelines(ao_sample)
        # Additional instruction version
        ai_sample = lines[:]
        if ai_sample and ai_sample[-1].endswith("\n"):
            ai_sample[-1] = ai_sample[-1].rstrip("\n")
        ai_sample.append("\n" + additional_instruction)
        with open(output_file_path_ai, 'w') as outfile:
            outfile.writelines(ai_sample)

def make_ivqd(input_folder=os.path.join("upd_text", args.folder, "ivqd_base")):
    """Generate ivqd variants from the given base set (ivqd_base) by creating solely the additional option and additional instruction variants."""
    output_folder_ao = os.path.join("upd_text", args.folder, "ivqd_additional_option")
    output_folder_ai = os.path.join("upd_text", args.folder, "ivqd_additional_instruction")
    os.makedirs(output_folder_ao, exist_ok=True)
    os.makedirs(output_folder_ai, exist_ok=True)

    filenames = os.listdir(input_folder)
    for filename in filenames:
        input_file_path = os.path.join(input_folder, filename)
        output_file_path_ao = os.path.join(output_folder_ao, filename)
        output_file_path_ai = os.path.join(output_folder_ai, filename)
        
        with open(input_file_path, 'r') as infile:
            lines = infile.readlines()
        
        # Generate the additional option variant.
        ao_lines = lines[:]  # copy of lines
        if ao_lines and ao_lines[-1].endswith("\n"):
            ao_lines[-1] = ao_lines[-1].rstrip("\n")
        last_letter = ao_lines[-1][0] if ao_lines else 'A'
        next_letter = chr(ord(last_letter) + 1)
        ao_lines.append(f"\n{next_letter}. none of the above")
        with open(output_file_path_ao, 'w') as outfile:
            outfile.writelines(ao_lines)
        
        # Generate the additional instruction variant.
        ai_lines = lines[:]  # copy original base
        if ai_lines and ai_lines[-1].endswith("\n"):
            ai_lines[-1] = ai_lines[-1].rstrip("\n")
        ai_lines.append("\n" + additional_instruction)
        with open(output_file_path_ai, 'w') as outfile:
            outfile.writelines(ai_lines)
    
def make_open_ended_instruction(input_folder=os.path.join("upd_text", args.folder, "open_ended")):
    """Generate open-ended instruction variants from the open-ended set."""
    output_folder = os.path.join("upd_text", args.folder, "open_ended_additional_instruction")
    os.makedirs(output_folder, exist_ok=True)

    # Process each file in the input folder
    for filename in os.listdir(input_folder):
        input_file_path = os.path.join(input_folder, filename)
        output_file_path = os.path.join(output_folder, filename)

        # Read the contents of the current file
        with open(input_file_path, 'r') as infile:
            lines = infile.readlines()

        # Write the remaining lines to the output file
        with open(output_file_path, 'w') as outfile:
            lines.append("\nIf the question is unanswerable, please answer: 'f'")
            outfile.writelines(lines)

def main():
    # Check for required base sets
    required_dirs = [
        os.path.join("upd_text", args.folder, "standard_answer"),
        os.path.join("upd_text", args.folder, "open_ended"),
        os.path.join("upd_text", args.folder, "iasd_base"),
        os.path.join("upd_text", args.folder, "ivqd_base"),
    ]
    missing = [d for d in required_dirs if not os.path.isdir(d)]
    if missing:
        print("Error: The following required base set folders are missing:")
        for d in missing:
            print(f"  {d}")
        return

    make_standard()
    make_aad()
    make_iasd()
    make_ivqd()
    make_open_ended_instruction()

if __name__ == "__main__":
    main()