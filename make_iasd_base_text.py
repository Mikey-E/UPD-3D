import argparse
import os
import openai

# Set up argument Parser
parser = argparse.ArgumentParser(description="Take standard_answer files and generate iasd base text using OpenAI API.")
parser.add_argument("upd_version_folder", type=str, help="Folder containing upd standard_answer subfolder.")
parser.add_argument("--prompt_file", type=str, default="iasd_prompt.txt", help="Name of the .txt file containing the prompt.")

args = parser.parse_args()

# Resolve upd_version_folder similar to how pcl_list is resolved.
if os.path.exists(args.upd_version_folder):
    upd_version_folder = args.upd_version_folder
elif os.path.exists(os.path.join("upd_text", args.upd_version_folder)):
    upd_version_folder = os.path.join("upd_text", args.upd_version_folder)
else:
    raise FileNotFoundError(f"upd_version_folder '{args.upd_version_folder}' not found in current directory or in 'upd_text/'.")

standard_answer_path = os.path.join(upd_version_folder, "standard_answer")

if not os.path.isdir(standard_answer_path):
    raise FileNotFoundError(f"The folder '{upd_version_folder}' does not contain a 'standard_answer' subfolder.")

# derive output subfolder name from pcl_list_path
output_folder = os.path.join("upd_text", os.path.basename(upd_version_folder), "iasd_base")
prompt_file = args.prompt_file

# Read the prompt text
if not os.path.exists(prompt_file):
    print(f"Error: Prompt file '{prompt_file}' does not exist.")
    exit(1)

# Ensure the output folder exists
os.makedirs(output_folder, exist_ok=True)

with open(prompt_file, 'r') as pf:
    prompt_text = pf.read()

# Get list of filenames to process from standard_answer_path
filenames_to_process = [filename for filename in os.listdir(standard_answer_path)]

# Process each file in the input folder or triage list
total_files = len(filenames_to_process)
for i, filename in enumerate(filenames_to_process, start=1):
    print(f"Processing file {i}/{total_files}: {filename}")
    standard_answer_input_file_path = os.path.join(standard_answer_path, filename)
    output_file_path = os.path.join(output_folder, filename + ".txt")

    # Read the contents of the current file
    with open(standard_answer_input_file_path, 'r') as infile:
        content = infile.read()
        #gather just the first line, raise exception if empty
        if not content.strip():
            raise ValueError(f"File '{standard_answer_input_file_path}' is empty or contains only whitespace.")
        question = content.splitlines()[0]  # Get the first line of the file

    # Combine the prompt text and the file content
    combined_text = f"{prompt_text}\n\n{question}"

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

    # Confirm the response from the API is high-quality. There should be a series of lines of answer options, prefixed in alphabetical order (A, B, C, etc.). For example:
    # A. Option 1
    # B. Option 2
    if not generated_text or not any(line.strip().startswith(tuple(chr(i) for i in range(ord('A'), ord('Z') + 1))) for line in generated_text.splitlines()):
        print(f"Generated text for {upd_version_folder} file '{filename}' does not contain valid answer options.")
        continue

    #Remove any extra whitespace from the generated text, both before the lines and at the beginning and end of each line
    generated_text = "\n".join(line.strip() for line in generated_text.splitlines() if line.strip())

    # Write the response to the output file
    with open(output_file_path, 'w') as outfile:
        outfile.write(question + "\n\n" + generated_text)