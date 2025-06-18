import argparse
import os
import openai

if not os.environ.get("OPENAI_API_KEY"):
    raise RuntimeError("Error: OPENAI_API_KEY environment variable is not set.")

# Set up argument Parser
parser = argparse.ArgumentParser(description="Take text_basis files and generate upd ivqd multiple-choice samples using OpenAI API.")
parser.add_argument("pcl_list", type=str, help="File containing list of point cloud filenames to process.")
parser.add_argument("--text_basis_folder", type=str, default="3D-FRONT", help="Name of the folder inside text_basis/")
parser.add_argument("--prompt_file", type=str, default="ivqd_prompt.txt", help="Name of the .txt file containing the prompt.")

args = parser.parse_args()

# Resolve pcl_list input as absolute/relative path or from pcl_lists/
if os.path.exists(args.pcl_list):
    pcl_list_path = args.pcl_list
elif os.path.exists(os.path.join("pcl_lists", args.pcl_list)):
    pcl_list_path = os.path.join("pcl_lists", args.pcl_list)
elif os.path.exists(os.path.join("pcl_lists", args.pcl_list + ".txt")):
    pcl_list_path = os.path.join("pcl_lists", args.pcl_list + ".txt")
else:
    raise FileNotFoundError(f"pcl_list file '{args.pcl_list}' not found in current dir or pcl_lists/")

# derive output subfolder name from pcl_list_path
pcl_list_name = os.path.splitext(os.path.basename(pcl_list_path))[0]
output_folder = os.path.join("upd_text", pcl_list_name, "ivqd_base")
prompt_file = args.prompt_file

# Read the prompt text
if not os.path.exists(prompt_file):
    print(f"Error: Prompt file '{prompt_file}' does not exist.")
    exit(1)

# Ensure the output folder exists
os.makedirs(output_folder, exist_ok=True)

with open(prompt_file, 'r') as pf:
    prompt_text = pf.read()

# Get list of filenames to process from pcl_list_path
with open(pcl_list_path, 'r') as pl:
    filenames_to_process = [line.strip() for line in pl if line.strip()]

# Process each file in the input folder or triage list
total_files = len(filenames_to_process)
for i, filename in enumerate(filenames_to_process, start=1):
    print(f"Processing file {i}/{total_files}: {filename}")
    text_basis_input_file_path = os.path.join("text_basis", args.text_basis_folder, filename + ".txt")
    output_file_path = os.path.join(output_folder, filename + ".txt")

    # Read the contents of the current file
    with open(text_basis_input_file_path, 'r') as infile:
        text_basis_file_content = infile.read()

    # Combine the prompt text and the file content
    combined_text = f"{prompt_text}\n\n{text_basis_file_content}"

    client = openai.OpenAI()

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": combined_text}],
            max_tokens=10000
        )
        generated_text = response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error processing file '{filename}': {str(e)}\ngenerated_text = {generated_text}")
        continue

    if not generated_text.strip():
        print(f"Generated text for file '{filename}' is empty or whitespace only.")
        continue

    # Split the generated text into lines and ensure the first line contains text, then the second line is blank, and the rest are lines of answer choices, with each line stripped of leading/trailing whitespace
    lines = generated_text.splitlines()
    if len(lines) < 2 or not lines[0].strip() or lines[1].strip():
        print(f"Generated text for file '{filename}' does not follow the expected format.")
        continue
    # Remove any leading or trailing whitespace from each line, but keep a blank line after the question
    lines = [line.strip() for line in lines if line.strip() or line == '']

    # Write the response to the output file
    with open(output_file_path, 'w') as outfile:
        # Write the question on its own line, followed by a blank line, then each answer choice on its own line
        outfile.write(lines[0])  # Question + blank line
        for line in lines[1:]:
            outfile.write("\n")
            outfile.write(line)