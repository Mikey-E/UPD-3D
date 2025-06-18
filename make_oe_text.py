import argparse
import os
import openai

if not os.environ.get("OPENAI_API_KEY"):
    raise RuntimeError("Error: OPENAI_API_KEY environment variable is not set.")

# Set up argument Parser
parser = argparse.ArgumentParser(description="Take text_basis files and generate upd open-ended samples using OpenAI API.")
parser.add_argument("pcl_list", type=str, help="File containing list of point cloud filenames to process.")
parser.add_argument("--text_basis_folder", type=str, default="3D-FRONT", help="Name of the folder inside text_basis/")
parser.add_argument("--prompt_file", type=str, default="oe_prompt.txt", help="Name of the .txt file containing the prompt.")

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
output_folder = os.path.join("upd_text", pcl_list_name, "open_ended")
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
    filenames = [line.strip() for line in pl if line.strip()]

total_files = len(filenames)
for i, filename in enumerate(filenames, start=1):
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

    # Write the response to the output file
    with open(output_file_path, 'w') as outfile:
        outfile.write(generated_text)