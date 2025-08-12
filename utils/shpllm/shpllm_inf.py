"""Batch inference for point clouds on ShapeLLM.

This updates the old PointLLM inference script to the ShapeLLM stack (llava.* modules).
It loads a ShapeLLM checkpoint, reads a list of identifier@scene pairs, the
corresponding prompts from upd_text, and .ply point clouds, then runs inference
and saves results to a JSON file.
"""

from __future__ import annotations

import os
import re
import json
import time
import argparse
import logging
from typing import List, Tuple, Dict, Any, Optional

import torch

from llava.utils import disable_torch_init
from llava.model.builder import load_pretrained_model
from llava.conversation import conv_templates, SeparatorStyle
from llava.constants import (
    POINT_TOKEN_INDEX,
    DEFAULT_POINT_TOKEN,
    DEFAULT_PT_START_TOKEN,
    DEFAULT_PT_END_TOKEN,
)
from llava.mm_utils import (
    load_pts,
    process_pts,
    tokenizer_point_token,
    get_model_name_from_path,
    KeywordsStoppingCriteria,
)


# Quiet down transformers logs if present
try:
    import transformers  # type: ignore
    logging.getLogger("transformers").setLevel(logging.ERROR)
except Exception:
    pass


def _read_lines(path: str) -> List[str]:
    with open(path, "r", encoding="utf-8") as f:
        return [ln.strip() for ln in f if ln.strip() and not ln.strip().startswith("#")]


def _parse_identifier_scene(line: str) -> Tuple[str, str]:
    # Accept forms like "identifier@scene" (strict) and guard against stray spaces
    if "@" not in line:
        raise ValueError(f"List entry must be 'identifier@scene', got: {line}")
    identifier, scene = [p.strip() for p in line.split("@", 1)]
    if not identifier or not scene:
        raise ValueError(f"Invalid identifier@scene: {line}")
    return identifier, scene


def _ply_path(unzipped_point_cloud_path: str, identifier: str, scene: str) -> str:
    # Expect: <unzipped>/<identifier>/<scene>/<scene>.ply
    return os.path.join(unzipped_point_cloud_path, identifier, scene, f"{scene}.ply")


def _prompt_txt_path(updtext_versionfolder_subfolder_path: str, identifier_at_scene: str) -> str:
    return os.path.join(updtext_versionfolder_subfolder_path, f"{identifier_at_scene}.txt")


def _safe_read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def _ensure_exists_file(path: str, kind: str) -> None:
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Missing {kind}: {path}")


def _ensure_exists_dir(path: str, kind: str) -> None:
    if not os.path.isdir(path):
        raise FileNotFoundError(f"Missing {kind} directory: {path}")


def init_model(args: argparse.Namespace):
    """Load tokenizer and model using ShapeLLM's builder utilities."""
    disable_torch_init()

    model_name = get_model_name_from_path(args.model_path)
    print(f"[INFO] Loading model from: {args.model_path} (name: {model_name})", flush=True)

    tokenizer, model, _ = load_pretrained_model(
        args.model_path,
        args.model_base,
        model_name,
        args.load_8bit,
        args.load_4bit,
        device=args.device,
    )

    conv = conv_templates["llava_v1"].copy()

    # Determine stop string from conversation template
    stop_str = conv.sep if conv.sep_style != SeparatorStyle.TWO else conv.sep2
    keywords = [stop_str]

    mm_use_pt_start_end = getattr(model.config, "mm_use_pt_start_end", False)

    return tokenizer, model, keywords, mm_use_pt_start_end, conv


def run_one_inference(
    tokenizer,
    model,
    conv_template,
    keywords: List[str],
    mm_use_pt_start_end: bool,
    pts_file: str,
    user_prompt: str,
    temperature: float = 0.2,
    max_new_tokens: int = 512,
) -> Dict[str, Any]:
    """Run inference for one sample and return outputs and some metadata."""
    # Load and process points
    pts = load_pts(pts_file)
    pts_tensor = process_pts(pts, model.config).unsqueeze(0)
    pts_tensor = pts_tensor.to(model.device, dtype=torch.float16)

    conv = conv_template.copy()
    roles = conv.roles

    # First user message, include point token(s)
    if mm_use_pt_start_end:
        first_input = (
            DEFAULT_PT_START_TOKEN + DEFAULT_POINT_TOKEN + DEFAULT_PT_END_TOKEN + "\n" + user_prompt
        )
    else:
        first_input = DEFAULT_POINT_TOKEN + "\n" + user_prompt

    conv.append_message(roles[0], first_input)
    conv.append_message(roles[1], None)
    prompt = conv.get_prompt()

    # Tokenize special point token index
    input_ids = (
        tokenizer_point_token(prompt, tokenizer, POINT_TOKEN_INDEX, return_tensors="pt")
        .unsqueeze(0)
        .to(model.device)
    )

    stopping_criteria = KeywordsStoppingCriteria(keywords, tokenizer, input_ids)

    with torch.inference_mode():
        output_ids = model.generate(
            input_ids,
            points=pts_tensor,
            do_sample=True,
            temperature=temperature,
            max_new_tokens=max_new_tokens,
            use_cache=True,
            stopping_criteria=[stopping_criteria],
        )

    outputs = tokenizer.decode(output_ids[0, input_ids.shape[1]:], skip_special_tokens=True).strip()
    conv.messages[-1][-1] = outputs

    return {
        "prompt": user_prompt,
        "response": outputs,
    }


def inference(
    pcl_list_txt_file_path: str,
    updtext_versionfolder_subfolder_path: str,
    unzipped_point_cloud_path: str,
    upd_subset_name: str,
    tokenizer,
    model,
    keywords: List[str],
    mm_use_pt_start_end: bool,
    conv_template,
    json_tag: Optional[str] = None,
    temperature: float = 0.2,
    max_new_tokens: int = 512,
) -> str:
    """Batch inference on a list of identifier@scene with ShapeLLM.

    Returns the path to the JSON results file.
    """

    # Load list and derive output filename
    identifier_at_scene_list = _read_lines(pcl_list_txt_file_path)
    pcl_list_txt_filename_noext = os.path.basename(os.path.normpath(pcl_list_txt_file_path)).replace(".txt", "")

    # Prepare results as a dict keyed by "identifier@scene" with only prompt/response
    results: Dict[str, Dict[str, Any]] = {}

    total = len(identifier_at_scene_list)
    print(f"[INFO] Running inference on {total} samples...", flush=True)

    for idx, identifier_at_scene in enumerate(identifier_at_scene_list, 1):
        try:
            identifier, scene = _parse_identifier_scene(identifier_at_scene)
            ply_file = _ply_path(unzipped_point_cloud_path, identifier, scene)
            prompt_file = _prompt_txt_path(
                updtext_versionfolder_subfolder_path, identifier_at_scene
            )

            _ensure_exists_file(ply_file, "point cloud .ply")
            _ensure_exists_file(prompt_file, "prompt text")

            user_prompt = _safe_read_text(prompt_file)

            out = run_one_inference(
                tokenizer=tokenizer,
                model=model,
                conv_template=conv_template,
                keywords=keywords,
                mm_use_pt_start_end=mm_use_pt_start_end,
                pts_file=ply_file,
                user_prompt=user_prompt,
                temperature=temperature,
                max_new_tokens=max_new_tokens,
            )

            # Store only prompt and response under key "identifier@scene"
            results[identifier_at_scene] = out

            if idx % 10 == 0 or idx == total:
                print(f"[INFO] {idx}/{total} done", flush=True)

        except Exception as e:
            logging.exception(f"[ERROR] Failed on {identifier_at_scene}: {e}")

    # Compose output filename
    model_base_name = os.path.basename(getattr(model, "name_or_path", "model"))
    tag = f"_{json_tag}" if json_tag else ""
    out_name = f"inf_rslts_{model_base_name}{tag}_{pcl_list_txt_filename_noext}_{upd_subset_name}.json"
    out_path = os.path.abspath(out_name)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"[INFO] Wrote results to: {out_path}")
    return out_path


def existing_dir(path: str) -> str:
    _ensure_exists_dir(path, "input")
    return path


def existing_file(path: str) -> str:
    _ensure_exists_file(path, "input file")
    return path


def main():
    parser = argparse.ArgumentParser(description="Batch inference for ShapeLLM on point clouds")
    parser.add_argument(
        "--model_path",
        type=str,
        default=os.path.join("checkpoints", "shapellm-13b-general-v1.0-finetune"),
        help="Path or HF hub id to the ShapeLLM model.",
    )
    parser.add_argument("--model_base", type=str, default=None, help="Optional base model for LoRA merges.")
    parser.add_argument("--device", type=str, default="cuda", help="Device for inference (e.g., cuda or cpu).")
    parser.add_argument("--load_8bit", action="store_true", help="Load model in 8-bit mode.")
    parser.add_argument("--load_4bit", action="store_true", help="Load model in 4-bit mode.")

    parser.add_argument("--upd_text_folder_path", type=existing_dir, required=True, help="Path to the upd_text folder.")
    parser.add_argument(
        "--upd_version_name",
        type=str,
        required=False,
        default="3D-FRONT",
        help="Name of the upd version (e.g., '3D-FRONT').",
    )
    parser.add_argument(
        "--upd_version_name_subfolder",
        type=str,
        required=True,
        help="Subfolder for the upd version (e.g., 'standard').",
    )
    parser.add_argument(
        "--unzipped_point_cloud_path",
        type=existing_dir,
        required=True,
        help="Folder containing <identifier>/<scene>/<scene>.ply",
    )
    parser.add_argument(
        "--pcl_list_txt_file_path",
        type=existing_file,
        required=True,
        help="Text file with one 'identifier@scene' per line.",
    )
    parser.add_argument(
        "--json_tag",
        type=str,
        required=False,
        default=None,
        help="Optional tag to append in the output JSON filename.",
    )
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--max_new_tokens", type=int, default=512)

    args = parser.parse_args()

    updtext_versionfolder_subfolder_path = os.path.join(
        args.upd_text_folder_path, args.upd_version_name, args.upd_version_name_subfolder
    )
    _ensure_exists_dir(updtext_versionfolder_subfolder_path, "upd_text subset")

    tokenizer, model, keywords, mm_use_pt_start_end, conv = init_model(args)

    inference(
        pcl_list_txt_file_path=args.pcl_list_txt_file_path,
        updtext_versionfolder_subfolder_path=updtext_versionfolder_subfolder_path,
        unzipped_point_cloud_path=args.unzipped_point_cloud_path,
        upd_subset_name=args.upd_version_name_subfolder,
        tokenizer=tokenizer,
        model=model,
        keywords=keywords,
        mm_use_pt_start_end=mm_use_pt_start_end,
        conv_template=conv,
        json_tag=args.json_tag,
        temperature=args.temperature,
        max_new_tokens=args.max_new_tokens,
    )


if __name__ == "__main__":
    main()

"""File to run PointLLM inference programmatically for batch evaluation."""

# import argparse
# from transformers import AutoTokenizer
# import torch
# import os
# from pointllm.conversation import conv_templates, SeparatorStyle
# from pointllm.utils import disable_torch_init
# from pointllm.model import *
# from pointllm.model.utils import KeywordsStoppingCriteria
# import numpy as np
# import json
# from pointllm.data import pc_norm, farthest_point_sample
# import open3d as o3d

# # Suppress transformers logging errors
# import logging
# logging.getLogger('transformers').setLevel(logging.ERROR)

# class FakeUpload:
#     """
#     A simple container class to mimic file upload objects for point cloud inference.
#     The original PointLLM gradio code this file is based on only ever used file
#     upload objects, so this class substitutes for that to allow programmatic evaluation that does not require those file upload objects that come from the gradio UI.
#     """
#     def __init__(self, path, hex, scene_name):
#         self.name = path
#         self.hex = hex
#         self.scene_name = scene_name

# def make_named_upd_txt_files(identifier_at_scene_list, updtext_versionfolder_subfolder_path):
#     """
#     Returns a list of file paths for upd text samples based on the provided subfolder and scenes.
#     """
#     return [os.path.join(updtext_versionfolder_subfolder_path, name + ".txt") for name in identifier_at_scene_list]

# def make_named_ply_files(identifier_at_scene_list, unzipped_point_cloud_path):
#     """
#     Returns a list of FakeUpload objects, each representing a point cloud file.
#     """
#     results = []
#     for identifier_at_scene in identifier_at_scene_list:
#         identifier, scene = identifier_at_scene.split('@')
#         results.append(FakeUpload(os.path.join(unzipped_point_cloud_path, identifier, scene, scene + ".ply"), identifier, scene))
#     return results

# def load_point_cloud(file_path):
#     """Load a point cloud from a PLY file and process it for model input."""
#     try:
#         pcd = o3d.io.read_point_cloud(file_path)
#         points = np.asarray(pcd.points)  # xyz
#         colors = np.asarray(pcd.colors)  # rgb, if available
        
#         # If no colors, create default black colors
#         if colors.size == 0:
#             colors = np.zeros_like(points)
        
#         # Ensure colors are in range [0, 1]
#         if np.max(colors) > 1:
#             colors = colors.astype(np.float32) / 255
        
#         # Concatenate points and colors
#         point_cloud = np.concatenate((points, colors), axis=1)
        
#         # Downsample if needed
#         if point_cloud.shape[0] > 8192:
#             point_cloud = farthest_point_sample(point_cloud, 8192)
        
#         # Normalize point cloud
#         point_cloud = pc_norm(point_cloud)
#         point_cloud = torch.from_numpy(point_cloud).unsqueeze_(0).to(torch.float32).cuda()
        
#         return point_cloud
#     except Exception as e:
#         print(f"[ERROR] Failed to load point cloud {file_path}: {e}", flush=True)
#         return None

# def inference(
#         pcl_list_txt_file_path,
#         updtext_versionfolder_subfolder_path,
#         unzipped_point_cloud_path,
#         upd_subset_name,
#         model,
#         tokenizer,
#         point_backbone_config,
#         keywords,
#         mm_use_point_start_end,
#         conv_template,
#         json_tag=None
#     ):
#     """Perform batch inference on point clouds and prompts."""
#     with open(pcl_list_txt_file_path, 'r') as f:
#         identifier_at_scene_list = f.read().splitlines()
#     pcl_list_txt_filename_noext = os.path.basename(os.path.normpath(pcl_list_txt_file_path)).replace('.txt', '')

#     pc_ply_list = make_named_ply_files(identifier_at_scene_list, unzipped_point_cloud_path)
#     upd_txt_file_list = make_named_upd_txt_files(identifier_at_scene_list, updtext_versionfolder_subfolder_path)

#     results = {}  # Dictionary to store all results
    
#     # Extract model configuration
#     point_token_len = point_backbone_config['point_token_len']
#     default_point_patch_token = point_backbone_config['default_point_patch_token']
#     default_point_start_token = point_backbone_config['default_point_start_token']
#     default_point_end_token = point_backbone_config['default_point_end_token']
    
#     total_samples = len(pc_ply_list)
#     for idx, (ply_file, txt_file) in enumerate(zip(pc_ply_list, upd_txt_file_list), 1):
#         try:
#             print(f"[PROGRESS] Processing sample {idx}/{total_samples}: {ply_file.hex}@{ply_file.scene_name}", flush=True)
#             # Read prompt
#             with open(txt_file, 'r') as f:
#                 prompt = f.read().strip()

#             # Load and process point cloud
#             point_clouds = load_point_cloud(ply_file.name)
#             if point_clouds is None:
#                 print(f"[ERROR] Failed to load point cloud: {ply_file.name}", flush=True)
#                 continue

#             # Reset conversation
#             conv = conv_template.copy()
            
#             # Add point tokens to the prompt
#             if mm_use_point_start_end:
#                 prompt = default_point_start_token + default_point_patch_token * point_token_len + default_point_end_token + '\n' + prompt
#             else:
#                 prompt = default_point_patch_token * point_token_len + '\n' + prompt

#             # Add to conversation
#             conv.append_message(conv.roles[0], prompt)
#             conv.append_message(conv.roles[1], None)
#             prompt_formatted = conv.get_prompt()

#             # Tokenize
#             inputs = tokenizer([prompt_formatted])
#             input_ids = torch.as_tensor(inputs.input_ids).cuda()

#             # Set up stopping criteria
#             stopping_criteria = KeywordsStoppingCriteria(keywords, tokenizer, input_ids)
#             stop_str = keywords[0]

#             # Generate response
#             with torch.inference_mode():
#                 output_ids = model.generate(
#                     input_ids,
#                     point_clouds=point_clouds,
#                     do_sample=False,
#                     temperature=0.2,
#                     max_new_tokens=60,
#                     min_length=1,
#                     max_length=400,
#                     stopping_criteria=[stopping_criteria]
#                 )

#             # Decode response
#             input_token_len = input_ids.shape[1]
#             outputs = tokenizer.batch_decode(output_ids[:, input_token_len:], skip_special_tokens=True)[0]
#             outputs = outputs.strip()
#             if outputs.endswith(stop_str):
#                 outputs = outputs[:-len(stop_str)]
#             outputs = outputs.strip()

#             # Store result
#             results[ply_file.hex + '@' + ply_file.scene_name.split(".")[0]] = {
#                 "prompt": prompt, 
#                 "response": outputs
#             }

#             print(f"[INFO] Processed {ply_file.hex}@{ply_file.scene_name}: {outputs}", flush=True)

#         except Exception as e:
#             print(f"[ERROR] Failed to process pair ({txt_file}, {ply_file.name}): {e}", flush=True)

#     # Write all results to a JSON file
#     try:
#         tag_part = f"{json_tag}_" if json_tag else ""
#         json_filename = f'inf_rslts_pllm_{tag_part}{pcl_list_txt_filename_noext}_{upd_subset_name}.json'
#         with open(json_filename, 'w') as f:
#             json.dump(results, f, indent=4)
#         print(f"[INFO] Results saved to {json_filename}", flush=True)
#     except Exception as e:
#         print(f"[ERROR] Failed to write results to JSON file: {e}", flush=True)

# def init_model(args):
#     """Initialize the model for batch inference."""
#     # Model
#     disable_torch_init()
#     model_name = os.path.expanduser(args.model_name)

#     print(f'[INFO] Model name: {os.path.basename(model_name)}', flush=True)

#     tokenizer = AutoTokenizer.from_pretrained(model_name)
#     model = PointLLMLlamaForCausalLM.from_pretrained(model_name, low_cpu_mem_usage=False, use_cache=True).cuda()
#     model.initialize_tokenizer_point_backbone_config_wo_embedding(tokenizer)

#     model.eval()

#     mm_use_point_start_end = getattr(model.config, "mm_use_point_start_end", False)
#     # Add special tokens ind to model.point_config
#     point_backbone_config = model.get_model().point_backbone_config
    
#     conv = conv_templates["vicuna_v1_1"].copy()

#     stop_str = conv.sep if conv.sep_style != SeparatorStyle.TWO else conv.sep2
#     keywords = [stop_str]
    
#     return model, tokenizer, point_backbone_config, keywords, mm_use_point_start_end, conv

# def existing_dir(path):
#     if not os.path.isdir(path):
#         raise argparse.ArgumentTypeError(f"readable_dir: '{path}' is not a valid directory")
#     return path

# def existing_file(path):
#     if not os.path.isfile(path):
#         raise argparse.ArgumentTypeError(f"readable_file: '{path}' is not a valid file")
#     return path

# if __name__ == "__main__":
#     parser = argparse.ArgumentParser(description="Programmatic evaluation code for PointLLM")
#     parser.add_argument("--model_name", type=str, default="RunsenXu/PointLLM_7B_v1.2",
#                         help="Path to the PointLLM model")
#     parser.add_argument("--upd_text_folder_path", type=existing_dir, required=True, 
#                         help="Path to the upd_text/ folder.")
#     parser.add_argument("--upd_version_name", type=str, required=False, 
#                         help="Name of the upd version (e.g., 'v1').", default="3D-FRONT")
#     parser.add_argument("--upd_version_name_subfolder", type=str, required=True, 
#                         help="Subfolder name for the upd version (e.g., 'standard').")
#     parser.add_argument("--unzipped_point_cloud_path", type=existing_dir, required=True, 
#                         help="Path to the unzipped point cloud folder containing dirs identifier/scene/scene.ply")
#     parser.add_argument("--pcl_list_txt_file_path", type=existing_file, required=True, 
#                         help="Path to the text file containing point cloud identifiers and scene names.")
#     parser.add_argument("--json_tag", type=str, required=False, 
#                         help="Optional tag to include in the output JSON filename, eg 'ft-comb' for finetune-combined", 
#                         default=None)
#     args = parser.parse_args()

#     # Check that the passed paths are valid
#     updtext_versionfolder_subfolder_path = os.path.join(
#         args.upd_text_folder_path,
#         args.upd_version_name,
#         args.upd_version_name_subfolder
#     )
#     if not os.path.isdir(updtext_versionfolder_subfolder_path):
#         raise ValueError(f"Error: '{updtext_versionfolder_subfolder_path}' is not a valid folder path.")

#     # Initialize model
#     model, tokenizer, point_backbone_config, keywords, mm_use_point_start_end, conv = init_model(args)

#     # Run batch inference
#     inference(
#         pcl_list_txt_file_path=args.pcl_list_txt_file_path,
#         updtext_versionfolder_subfolder_path=updtext_versionfolder_subfolder_path,
#         unzipped_point_cloud_path=args.unzipped_point_cloud_path,
#         upd_subset_name=args.upd_version_name_subfolder,
#         model=model,
#         tokenizer=tokenizer,
#         point_backbone_config=point_backbone_config,
#         keywords=keywords,
#         mm_use_point_start_end=mm_use_point_start_end,
#         conv_template=conv,
#         json_tag=args.json_tag
#     )