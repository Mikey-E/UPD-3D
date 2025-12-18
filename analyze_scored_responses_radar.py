"""
This file takes a folder of _scored json files of model responses to UPD subsets, and makes a radar chart of the scores

Example run:
python analyze_scored_responses_radar.py \
    ./scored_model_responses/3D-FRONT_test_mgpt3d \
    ./scored_model_responses/3D-FRONT_test_gplm \
    ./scored_model_responses/3D-FRONT_test_pllm \
    ./scored_model_responses/3D-FRONT_test_shpllm_ft-cap3d \
    ./scored_model_responses/3D-FRONT_test_llava3d_base \
    --legend_names "MiniGPT-3D" "GreenPLM" "PointLLM" "ShapeLLM" "LLaVA-3D" \
    --title "Model Comparison on UPD Tasks"
"""

import argparse
import json
import matplotlib.pyplot as plt
import numpy as np
import os
import re

def main():
    parser = argparse.ArgumentParser(description="Analyze scored responses and create a radar chart.")
    parser.add_argument("folder_paths", type=str, nargs='+', help="Path(s) to folder(s) containing JSON files with scored responses.")
    parser.add_argument("--legend_names", type=str, nargs='*', help="Custom legend names for each folder (default: use last folder names).")
    parser.add_argument("--naming_delim", type=str, help="Delimiter in the file names to separate out subset name.", default="_3D-FRONT_test_")
    parser.add_argument("--title", type=str, required=True, help="Graph title.")
    parser.add_argument("--tick_fontsize", type=int, default=21, help="Font size for axis ticks and labels.")
    parser.add_argument("--legend_fontsize", type=int, default=20, help="Font size for legend text.")
    parser.add_argument("--title_fontsize", type=int, default=29, help="Font size for title text.")
    parser.add_argument("--fontscale", type=float, default=1.0, help="Scale factor to multiply all font sizes.")
    parser.add_argument("--figsize_width", type=int, default=12, help="Width of the figure in inches.")
    parser.add_argument("--figsize_height", type=int, default=10, help="Height of the figure in inches.")
    parser.add_argument("--legend_bbox_to_anchor", type=str, default="1.3,1.1", help="Legend position as 'x,y'.")
    parser.add_argument("--fig_pad", type=float, default=1.5, help="Padding for the figure to prevent cutoff.")
    parser.add_argument("--plot_upd", action="store_true", default=True, help="Plot UPD accuracy series.")
    parser.add_argument("--plot_dual", action="store_true", default=True, help="Plot Dual accuracy series.")
    parser.add_argument("--no_plot_upd", action="store_false", dest="plot_upd", help="Do not plot UPD accuracy series.")
    parser.add_argument("--no_plot_dual", action="store_false", dest="plot_dual", help="Do not plot Dual accuracy series.")
    args = parser.parse_args()

    # Apply font scaling
    tick_fontsize = int(args.tick_fontsize * args.fontscale)
    legend_fontsize = int(args.legend_fontsize * args.fontscale)
    title_fontsize = int(args.title_fontsize * args.fontscale)
    
    # Get legend names (either custom or from folder names)
    legend_base_names = []
    if args.legend_names and len(args.legend_names) == len(args.folder_paths):
        legend_base_names = args.legend_names
    else:
        for folder_path in args.folder_paths:
            legend_base_names.append(os.path.basename(os.path.normpath(folder_path)))
    
    # Process each folder and collect data
    all_categories = set()
    folder_data = []
    
    for folder_idx, folder_path in enumerate(args.folder_paths):
        json_files = [os.path.join(folder_path, file) for file in os.listdir(folder_path) if file.endswith('.json')]
        
        results = {}
        standard_upd_accuracies = {}
        standard_file = None
        for json_file in json_files:
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)
                if "standard" in json_file:
                    standard_file = json_file
                # Extract scores from the data
                results[json_file] = [item["score"] for item in data.values()]
                standard_upd_accuracies[json_file] = len([score for score in results[json_file] if score == 'T'])
            except KeyError as e:
                print(f"ERROR: Missing key {e} in file: {json_file}")
                print(f"  File path: {os.path.abspath(json_file)}")
                print(f"  Sample data keys: {list(next(iter(data.values())).keys()) if data else 'No data'}")
                raise
            except Exception as e:
                print(f"ERROR: Failed to process file: {json_file}")
                print(f"  Error type: {type(e).__name__}")
                print(f"  Error message: {str(e)}")
                raise
        
        # Check if sample counts are consistent across categories
        sample_counts = [len(results[k]) for k in standard_upd_accuracies.keys()]
        if len(set(sample_counts)) != 1:
            print(f"WARNING: Not all categories in {folder_path} have the same number of samples.")
        
        # Compute dual accuracies
        dual_accuracies = {}
        if standard_file:
            standard_score_list = results[standard_file]
            for json_file in json_files:
                if "standard" in json_file or "open_ended" in json_file:
                    dual_accuracies[json_file] = 0
                    continue
                if json_file != standard_file:
                    upd_score_list = results[json_file]
                    for i in range(len(standard_score_list)):
                        if standard_score_list[i] == 'T' and upd_score_list[i] == 'T':
                            dual_accuracies[json_file] = dual_accuracies.get(json_file, 0) + 1
        
        # Prepare category names for the radar chart
        names_list = list(standard_upd_accuracies.keys())
        # Remove scoring model name pattern (e.g., _gpt-4.1-mini_scored.json or _gpt-5-nano_scored.json)
        names_list = [re.sub(r'_[^_/]+_scored\.json$', '', name) for name in names_list]
        names_list = [name.split(args.naming_delim)[1] for name in names_list]
        names_list = [name.replace("_", " ") for name in names_list]
        names_list = [name.title() for name in names_list]

        def fix_acronyms(s):
            for acr in ["aad", "iasd", "ivqd"]:
                s = re.sub(r'(?i)\b' + acr + r'\b', acr.upper(), s)
            return s
        
        categories = [fix_acronyms(name) for name in names_list]
        all_categories.update(categories)
        
        # Store folder data
        folder_data.append({
            'legend_name': legend_base_names[folder_idx],
            'categories': categories,
            'standard_accuracies': list(standard_upd_accuracies.values()),
            'dual_accuracies': [dual_accuracies.get(k, 0) for k in standard_upd_accuracies.keys()],
            'max_samples': max(len(results[k]) for k in standard_upd_accuracies.keys())
        })
    
    # Create the combined radar chart
    # Use the union of all categories from all folders
    all_categories = sorted(list(all_categories))
    N = len(all_categories)
    
    # Set up the angles for the radar chart
    angles = np.linspace(0, 2*np.pi, N, endpoint=False).tolist()
    angles += angles[:1]
    all_categories += all_categories[:1]  # Close the loop for labels
    
    # Create figure and polar axis
    fig, ax = plt.subplots(figsize=(args.figsize_width, args.figsize_height), subplot_kw=dict(polar=True))
    
    # Colors for different folders
    colors = ['blue', 'red', 'green', 'purple', 'orange', 'brown', 'pink', 'gray', 'olive', 'cyan']
    max_y_value = 0
    
    # Plot each folder's data
    for folder_idx, data in enumerate(folder_data):
        # Map this folder's data to the common category list
        std_values = []
        dual_values = []
        
        for category in all_categories[:-1]:  # Skip the duplicated last one
            if category in data['categories']:
                idx = data['categories'].index(category)
                std_values.append(data['standard_accuracies'][idx])
                dual_values.append(data['dual_accuracies'][idx])
            else:
                std_values.append(0)
                dual_values.append(0)
        
        # Close the loop for plotting
        std_values += [std_values[0]]
        dual_values += [dual_values[0]]
        
        color_idx = folder_idx % len(colors)
        
        # Plot standard accuracies if requested
        if args.plot_upd:
            ax.plot(angles, std_values, 'o-', linewidth=2, 
                    label=f"{data['legend_name']} - UPD", color=colors[color_idx])
            ax.fill(angles, std_values, alpha=0.1, color=colors[color_idx])
        
        # Plot dual accuracies if requested
        if args.plot_dual:
            ax.plot(angles, dual_values, 'o--', linewidth=2, 
                    label=f"{data['legend_name']} - Dual", color=colors[color_idx], alpha=0.7)
            ax.fill(angles, dual_values, alpha=0.05, color=colors[color_idx])
        
        max_y_value = max(max_y_value, data['max_samples'])
    
    # Set category labels
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(all_categories[:-1], size=tick_fontsize)
    
    # Parse the legend position
    legend_x, legend_y = map(float, args.legend_bbox_to_anchor.split(','))
    
    # Set title and legend
    plt.title(args.title, size=title_fontsize, y=1.1)
    plt.legend(loc='upper right', bbox_to_anchor=(legend_x, legend_y), fontsize=legend_fontsize)
    
    # Set y-axis limit
    ax.set_ylim(0, max_y_value)
    
    # Add padding to prevent text cutoff
    plt.tight_layout(pad=args.fig_pad)
    
    # Save the figure
    output_dir = "./results/radar_graphs"
    os.makedirs(output_dir, exist_ok=True)
    
    # Extract scoring model name from first folder name (last underscore-separated part)
    first_folder_basename = os.path.basename(os.path.normpath(args.folder_paths[0]))
    parts = first_folder_basename.split('_')
    scoring_model = parts[-1] if len(parts) > 1 else "unknown"
    
    # Create a name based on all folder names (without scoring model suffix)
    if len(args.folder_paths) == 1:
        # Remove scoring model from folder name for the base output name
        name_for_saving = '_'.join(parts[:-1]) if len(parts) > 1 else first_folder_basename
    else:
        name_for_saving = "combined_analysis"
    
    # Add scoring model to filename
    output_path = os.path.join(output_dir, f"{name_for_saving}_{scoring_model}_radar.png")
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Radar chart saved to: {os.path.abspath(output_path)}")

if __name__ == "__main__":
    main()