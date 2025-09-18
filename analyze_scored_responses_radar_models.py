"""
This file takes lists of scored json files and creates a radar chart where each file becomes a point on the radar.
This is useful for comparing different models on the same question types.
"""

import argparse
import json
import matplotlib.pyplot as plt
import numpy as np
import os
import re

def extract_model_name_from_path(file_path):
    """Extract a clean model name from the file path."""
    basename = os.path.basename(file_path)
    
    # Remove common suffixes
    basename = basename.replace("_scored.json", "")
    basename = basename.replace("_3D-FRONT_test_standard", "")
    
    # Naming conversion dictionary (case insensitive)
    name_conversions = {
        'mgpt3d': 'MiniGPT-3D',
        'gplm': 'GreenPLM', 
        'pllm': 'PointLLM',
        'shpllm': 'ShapeLLM'
    }
    
    # Check for specific patterns in the basename (case insensitive)
    basename_lower = basename.lower()
    for key, value in name_conversions.items():
        if key in basename_lower:
            return value
    
    # Legacy patterns for backwards compatibility
    if "MiniGPT-3D" in basename:
        return "MiniGPT-3D"
    elif "shapellm" in basename_lower:
        return "ShapeLLM"
    else:
        # Fallback: clean up the basename
        basename = re.sub(r'^(inf_rslts_|inference_results_)', '', basename)
        basename = re.sub(r'_ft-.*$', '', basename)
        return basename

def parse_file_lists(args):
    """Parse the command line arguments to extract series of file paths and their names."""
    series_data = []
    
    # Parse series arguments
    i = 0
    while i < len(args.remaining_args):
        if args.remaining_args[i] == '--series':
            if i + 2 >= len(args.remaining_args):
                raise ValueError("--series requires a name and at least one file path")
            
            series_name = args.remaining_args[i + 1]
            file_paths = []
            
            # Collect file paths until we hit another --series or end of args
            j = i + 2
            while j < len(args.remaining_args) and args.remaining_args[j] != '--series':
                file_paths.append(args.remaining_args[j])
                j += 1
            
            if not file_paths:
                raise ValueError(f"No file paths provided for series '{series_name}'")
            
            series_data.append({
                'name': series_name,
                'files': file_paths
            })
            
            i = j
        else:
            i += 1
    
    return series_data

def process_series_files(series_data):
    """Process all series and extract scores, treating each file as a radar point."""
    all_model_names = set()
    processed_series = []
    
    for series in series_data:
        model_scores = {}
        max_samples = 0
        
        for json_file in series['files']:
            if not os.path.exists(json_file):
                print(f"WARNING: File {json_file} does not exist, skipping.")
                continue
                
            with open(json_file, 'r') as f:
                data = json.load(f)
            
            # Extract scores and count correct answers
            scores = [item["score"] for item in data.values()]
            correct_count = len([score for score in scores if score == 'T'])
            total_count = len(scores)
            
            # Get model name from file path
            model_name = extract_model_name_from_path(json_file)
            all_model_names.add(model_name)
            
            model_scores[model_name] = {
                'correct': correct_count,
                'total': total_count,
                'accuracy': correct_count / total_count if total_count > 0 else 0
            }
            
            max_samples = max(max_samples, total_count)
        
        # Store series data
        processed_series.append({
            'name': series['name'],
            'model_scores': model_scores,
            'max_samples': max_samples
        })
    
    return processed_series, sorted(list(all_model_names))

def main():
    parser = argparse.ArgumentParser(
        description="Analyze scored responses and create a radar chart where each file represents a model.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
  python script.py --title "Model Performance" --series "Standard QA" model1.json model2.json model3.json --series "Complex QA" model1_complex.json model2_complex.json

Each --series argument should be followed by a name and then one or more JSON file paths.
Each file becomes a point on the radar chart (representing a model).
        """
    )
    
    parser.add_argument("--title", type=str, required=True, help="Graph title.")
    parser.add_argument("--tick_fontsize", type=int, default=14, help="Font size for axis ticks and labels.")
    parser.add_argument("--legend_fontsize", type=int, default=13, help="Font size for legend text.")
    parser.add_argument("--title_fontsize", type=int, default=19, help="Font size for title text.")
    parser.add_argument("--fontscale", type=float, default=1.0, help="Scale factor to multiply all font sizes.")
    parser.add_argument("--figsize_width", type=int, default=12, help="Width of the figure in inches.")
    parser.add_argument("--figsize_height", type=int, default=10, help="Height of the figure in inches.")
    parser.add_argument("--legend_bbox_to_anchor", type=str, default="1.3,1.1", help="Legend position as 'x,y'.")
    parser.add_argument("--fig_pad", type=float, default=1.5, help="Padding for the figure to prevent cutoff.")
    parser.add_argument("--output_name", type=str, help="Custom name for the output file (without extension).")
    parser.add_argument("--use_accuracy", action="store_true", help="Use accuracy (0-1) instead of raw counts.")
    
    # Parse known args first, then handle the series manually
    args, remaining = parser.parse_known_args()
    args.remaining_args = remaining
    
    # Parse series data
    try:
        series_data = parse_file_lists(args)
    except ValueError as e:
        print(f"Error parsing series: {e}")
        return
    
    if not series_data:
        print("No series specified. Use --series <name> <file1> <file2> ... to specify data series.")
        return
    
    # Apply font scaling
    tick_fontsize = int(args.tick_fontsize * args.fontscale)
    legend_fontsize = int(args.legend_fontsize * args.fontscale)
    title_fontsize = int(args.title_fontsize * args.fontscale)
    
    # Process all series
    processed_series, all_model_names = process_series_files(series_data)
    
    if not all_model_names:
        print("No valid data found in any series.")
        return
    
    # Create the radar chart
    N = len(all_model_names)
    
    # Set up the angles for the radar chart
    angles = np.linspace(0, 2*np.pi, N, endpoint=False).tolist()
    angles += angles[:1]
    all_model_names += all_model_names[:1]  # Close the loop for labels
    
    # Create figure and polar axis
    fig, ax = plt.subplots(figsize=(args.figsize_width, args.figsize_height), subplot_kw=dict(polar=True))
    
    # Colors for different series
    colors = ['blue', 'red', 'green', 'purple', 'orange', 'brown', 'pink', 'gray', 'olive', 'cyan']
    max_y_value = 0
    
    # Plot each series' data
    for series_idx, data in enumerate(processed_series):
        # Map this series' data to the common model list
        values = []
        
        for model_name in all_model_names[:-1]:  # Skip the duplicated last one
            if model_name in data['model_scores']:
                if args.use_accuracy:
                    values.append(data['model_scores'][model_name]['accuracy'])
                else:
                    values.append(data['model_scores'][model_name]['correct'])
            else:
                values.append(0)
        
        # Close the loop for plotting
        values += [values[0]]
        
        # Plot the series
        color_idx = series_idx % len(colors)
        ax.plot(angles, values, 'o-', linewidth=2, 
                label=data['name'], color=colors[color_idx])
        ax.fill(angles, values, alpha=0.1, color=colors[color_idx])
        
        if args.use_accuracy:
            max_y_value = max(max_y_value, 1.0)  # Accuracy is 0-1
        else:
            max_y_value = max(max_y_value, data['max_samples'])
    
    # Set category labels (model names)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(all_model_names[:-1], size=tick_fontsize)
    
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
    output_dir = "./results/multi_model_radar"
    os.makedirs(output_dir, exist_ok=True)
    
    # Create output filename
    if args.output_name:
        name_for_saving = args.output_name
    else:
        name_for_saving = "model_comparison_radar"
    
    plt.savefig(os.path.join(output_dir, f"{name_for_saving}_radar.png"), dpi=300, bbox_inches='tight')
    print(f"Radar chart saved to ./results/multi_model_radar/{name_for_saving}_radar.png")

if __name__ == "__main__":
    main()