"""
This file takes lists of scored json files and creates a radar chart where each file becomes a point on the radar.
This is useful for comparing diffe    parser.add_argument("--tick_fontsize", type=int, default=28, help="Font size for axis ticks and labels.")
    parser.add_argument("--legend_fontsize", type=int, default=26, help="Font size for legend text.")
    parser.add_argument("--title_fontsize", type=int, default=38, help="Font size for title text.")t models on the same question types.
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
            custom_color = None
            
            # Check if the next argument after series name could be a color
            # (before any file paths that should exist)
            j = i + 2
            if j < len(args.remaining_args):
                potential_color = args.remaining_args[j]
                # Check if it's a valid color name (not a file path)
                valid_colors = ['red', 'blue', 'green', 'orange', 'purple', 'brown', 'pink', 
                               'gray', 'grey', 'olive', 'cyan', 'magenta', 'yellow', 'black',
                               'lightblue', 'lightgreen', 'lightcoral', 'lightyellow', 'lightgray',
                               'darkblue', 'darkgreen', 'darkred', 'darkgray', 'navy', 'maroon']
                
                if potential_color.lower() in valid_colors and not potential_color.endswith('.json'):
                    custom_color = potential_color.lower()
                    j += 1  # Skip the color argument
            
            # Collect file paths until we hit another --series or end of args
            while j < len(args.remaining_args) and args.remaining_args[j] != '--series':
                file_paths.append(args.remaining_args[j])
                j += 1
            
            if not file_paths:
                raise ValueError(f"No file paths provided for series '{series_name}'")
            
            series_data.append({
                'name': series_name,
                'files': file_paths,
                'color': custom_color
            })
            
            i = j
        else:
            i += 1
    
    return series_data

def find_matching_standard_file(upd_file, series_files):
    """Find the standard file that corresponds to the same model as the UPD file."""
    # Extract model identifier from UPD file
    upd_model_name = extract_model_name_from_path(upd_file)
    
    # Look for standard file with the same model
    for file_path in series_files:
        if "standard" in file_path.lower():
            standard_model_name = extract_model_name_from_path(file_path)
            if standard_model_name == upd_model_name:
                return file_path
    
    return None

def compute_dual_accuracy(upd_file, standard_file):
    """Compute dual accuracy between UPD file and corresponding standard file."""
    if not standard_file or not os.path.exists(standard_file):
        print(f"WARNING: Standard file {standard_file} not found for dual accuracy computation.")
        return 0, 0  # dual_correct, total
    
    # Load both files
    with open(upd_file, 'r') as f:
        upd_data = json.load(f)
    
    with open(standard_file, 'r') as f:
        standard_data = json.load(f)
    
    # Extract scores
    upd_scores = [item["score"] for item in upd_data.values()]
    standard_scores = [item["score"] for item in standard_data.values()]
    
    # Check if both have same number of samples
    if len(upd_scores) != len(standard_scores):
        print(f"WARNING: Mismatch in sample count between {upd_file} ({len(upd_scores)}) and {standard_file} ({len(standard_scores)})")
        return 0, len(upd_scores)
    
    # Count dual correct answers (both standard and UPD correct for same index)
    dual_correct = 0
    for i in range(len(upd_scores)):
        if upd_scores[i] == 'T' and standard_scores[i] == 'T':
            dual_correct += 1
    
    return dual_correct, len(upd_scores)

def process_series_files(series_data, use_dual_accuracy=False):
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
            
            # Skip standard files when in dual mode - they're only used for dual accuracy calculation
            if use_dual_accuracy and "standard" in json_file.lower():
                continue
                
            with open(json_file, 'r') as f:
                data = json.load(f)
            
            # Get model name from file path
            model_name = extract_model_name_from_path(json_file)
            all_model_names.add(model_name)
            
            if use_dual_accuracy:
                # Check if this is an open_ended file (dual accuracy N/A)
                if "open_ended" in json_file.lower():
                    # For open_ended files, dual accuracy is 0 (or N/A)
                    dual_correct = 0
                    total_count = len([item["score"] for item in data.values()])
                else:
                    # Find the standard file that matches this specific model
                    matching_standard_file = find_matching_standard_file(json_file, series['files'])
                    dual_correct, total_count = compute_dual_accuracy(json_file, matching_standard_file)
                
                model_scores[model_name] = {
                    'correct': dual_correct,
                    'total': total_count,
                    'accuracy': dual_correct / total_count if total_count > 0 else 0
                }
            else:
                # Regular accuracy computation
                scores = [item["score"] for item in data.values()]
                correct_count = len([score for score in scores if score == 'T'])
                total_count = len(scores)
                
                model_scores[model_name] = {
                    'correct': correct_count,
                    'total': total_count,
                    'accuracy': correct_count / total_count if total_count > 0 else 0
                }
            
            max_samples = max(max_samples, model_scores[model_name]['total'])
        
        # Store series data
        processed_series.append({
            'name': series['name'],
            'model_scores': model_scores,
            'max_samples': max_samples,
            'color': series.get('color')  # Preserve the custom color
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
    parser.add_argument("--tick_fontsize", type=int, default=28, help="Font size for axis ticks and labels.")
    parser.add_argument("--legend_fontsize", type=int, default=26, help="Font size for legend text.")
    parser.add_argument("--title_fontsize", type=int, default=38, help="Font size for title text.")
    parser.add_argument("--radial_fontsize", type=int, default=21, help="Font size for radial axis labels (concentric circle numbers).")
    parser.add_argument("--fontscale", type=float, default=1.0, help="Scale factor to multiply all font sizes.")
    parser.add_argument("--figsize_width", type=int, default=14, help="Width of the figure in inches.")
    parser.add_argument("--figsize_height", type=int, default=10, help="Height of the figure in inches.")
    parser.add_argument("--legend_bbox_to_anchor", type=str, default="1.02,1.0", help="Legend position as 'x,y'.")
    parser.add_argument("--fig_pad", type=float, default=1.5, help="Padding for the figure to prevent cutoff.")
    parser.add_argument("--use_accuracy", action="store_true", help="Use accuracy (0-1) instead of raw counts.")
    parser.add_argument("--output_folder_name", type=str, help="Custom output folder name within ./results/multi_model_radar/")
    parser.add_argument("--no_legend", action="store_true", help="Disable legend generation (no legend will be shown).")
    parser.add_argument("--dual", action="store_true", help="Compute dual accuracy (both standard and UPD variant correct for same sample) instead of regular accuracy.")
    
    # Spacing consistency parameters
    parser.add_argument("--title_y_position", type=float, default=1.08, help="Base Y position for title.")
    parser.add_argument("--title_line_spacing", type=float, default=0.05, help="Additional Y spacing per title line.")
    parser.add_argument("--chars_per_line", type=int, default=50, help="Characters per line for title wrapping estimation.")
    parser.add_argument("--top_margin_base", type=float, default=0.95, help="Base top margin for layout rect.")
    parser.add_argument("--top_margin_per_line", type=float, default=0.03, help="Top margin reduction per additional title line.")
    parser.add_argument("--layout_rect_right", type=float, default=0.85, help="Right boundary for layout rect (reserves space for legend).")
    
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
    radial_fontsize = int(args.radial_fontsize * args.fontscale)
    
    # Process all series
    processed_series, all_model_names = process_series_files(series_data, use_dual_accuracy=args.dual)
    
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
    
    # Default colors for different series
    default_colors = ['blue', 'red', 'green', 'purple', 'orange', 'brown', 'pink', 'gray', 'olive', 'cyan']
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
        
        # Determine color based on custom color or series name
        if data.get('color'):
            # Use custom color if provided
            color = data['color']
        else:
            # Fall back to keyword-based color selection
            series_name_lower = data['name'].lower()
            if 'standard' in series_name_lower:
                color = 'blue'
            elif 'dual' in series_name_lower:
                color = 'red'
            elif 'upd' in series_name_lower:
                color = 'lightblue'
            else:
                # Use default color cycling for other series
                color = default_colors[series_idx % len(default_colors)]
        
        # Plot the series
        ax.plot(angles, values, 'o-', linewidth=2, 
                label=data['name'], color=color)
        ax.fill(angles, values, alpha=0.1, color=color)
        
        if args.use_accuracy:
            max_y_value = max(max_y_value, 1.0)  # Accuracy is 0-1
        else:
            max_y_value = max(max_y_value, data['max_samples'])
    
    # Set category labels (model names)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(all_model_names[:-1], size=tick_fontsize)
    
    # Set radial axis label font size (concentric circle numbers)
    ax.tick_params(axis='y', labelsize=radial_fontsize)
    
    # Parse the legend position
    legend_x, legend_y = map(float, args.legend_bbox_to_anchor.split(','))
    
    # Calculate title height dynamically based on title length and font size
    # Use configurable parameters for consistency
    title_chars_per_line = max(args.chars_per_line, args.figsize_width * 6)  # Use flag with fallback
    title_lines = max(1, len(args.title) // title_chars_per_line + (1 if len(args.title) % title_chars_per_line > 0 else 0))
    
    # Adjust title y-position based on estimated lines using configurable parameters
    title_y_pos = args.title_y_position + (title_lines - 1) * args.title_line_spacing
    
    # Set title and legend with consistent positioning
    plt.title(args.title, size=title_fontsize, y=title_y_pos, wrap=True)
    
    # Add legend only if not disabled
    if not args.no_legend:
        plt.legend(loc='center left', bbox_to_anchor=(legend_x, legend_y), fontsize=legend_fontsize)
    
    # Set y-axis limit
    ax.set_ylim(0, max_y_value)
    
    # Calculate rect parameters to reserve space for title and legend consistently
    # Use configurable parameters for consistent spacing
    # Adjust layout based on whether legend is present
    if args.no_legend:
        # No legend: use full width for chart
        layout_right = 1.0
    else:
        # Legend present: reserve space on the right
        layout_right = args.layout_rect_right
    
    top_margin = args.top_margin_base - (title_lines - 1) * args.top_margin_per_line
    
    # Add padding to prevent text cutoff with dynamic layout adjustment
    plt.tight_layout(pad=args.fig_pad, rect=[0, 0, layout_right, top_margin])
    
    # Save the figure
    base_output_dir = "./results/multi_model_radar"
    if args.output_folder_name:
        output_dir = os.path.join(base_output_dir, args.output_folder_name)
    else:
        output_dir = base_output_dir
    os.makedirs(output_dir, exist_ok=True)
    
    # Create output filename from series titles
    def sanitize_name(name):
        """Convert a series name to a filename-safe string."""
        # Replace spaces and special characters with underscores
        sanitized = re.sub(r'[^a-zA-Z0-9_-]', '_', name)
        # Remove multiple consecutive underscores
        sanitized = re.sub(r'_+', '_', sanitized)
        # Remove leading/trailing underscores
        return sanitized.strip('_')
    
    # Create shorter filename from series names only
    series_names = [sanitize_name(series['name']) for series in processed_series]
    series_part = "_vs_".join(series_names)
    
    # Add dual indicator to filename if using dual accuracy
    prefix = "rdr_mm_dual_" if args.dual else "rdr_mm_"
    name_for_saving = f"{prefix}{series_part}"
    
    plt.savefig(os.path.join(output_dir, f"{name_for_saving}.png"), dpi=300, bbox_inches='tight')
    accuracy_type = "dual accuracy" if args.dual else "regular accuracy"
    print(f"Radar chart ({accuracy_type}) saved to ./results/multi_model_radar/{name_for_saving}.png")

if __name__ == "__main__":
    main()