import argparse
import os
import openai

# Set up argument parser
parser = argparse.ArgumentParser(description="Take text_basis files and generate upd multiple-choice samples using OpenAI API.")
parser.add_argument("folder", type=str, help="Name of the folder inside text_basis/")
parser.add_argument("--prompt_file", type=str, default="mc_prompt.txt", help="Name of the .txt file containing the prompt.")

args = parser.parse_args()

# Define paths
input_folder = os.path.join("text_basis", args.folder)
output_folder = os.path.join("upd_text", args.folder, "standard_answer")
prompt_file = args.prompt_file

# Ensure the output folder exists
os.makedirs(output_folder, exist_ok=True)

# Read the prompt text
if not os.path.exists(prompt_file):
    print(f"Error: Prompt file '{prompt_file}' does not exist.")
    exit(1)

with open(prompt_file, 'r') as pf:
    prompt_text = pf.read()

# Process each file in the input folder
for filename in os.listdir(input_folder):
    input_file_path = os.path.join(input_folder, filename)
    output_file_path = os.path.join(output_folder, filename)

    # Read the contents of the current file
    with open(input_file_path, 'r') as infile:
        file_content = infile.read()

    # Combine the prompt text and the file content
    combined_text = f"{prompt_text}\n\n{file_content}"

    client = openai.OpenAI()

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": combined_text}],
            max_tokens=10000
        )
        generated_text = response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error processing file '{filename}': {str(e)}")
        continue

    # Write the response to the output file
    with open(output_file_path, 'w') as outfile:
        outfile.write(generated_text)