import os
import json
import argparse
from torch.utils.data import DataLoader
from pointllm.data import ModelNet
from tqdm import tqdm
import torch
from llava.constants import IMAGE_TOKEN_INDEX, DEFAULT_IMAGE_TOKEN
from llava.conversation import conv_templates
from llava.model.builder import load_pretrained_model
from llava.mm_utils import tokenizer_image_token, get_model_name_from_path

def existing_dir(path):
    if not os.path.isdir(path):
        raise argparse.ArgumentTypeError(f"readable_dir: '{path}' is not a valid directory")
    return path

def existing_file(path):
    if not os.path.isfile(path):
        raise argparse.ArgumentTypeError(f"readable_file: '{path}' is not a valid file")
    return path

class MyClass:
    def __init__(self, args):
        self.vision_tower = None
        self.pretrain_mm_mlp_adapter = args.pretrain_mm_mlp_adapter
        self.encoder_type = 'pc_encoder'
        self.std=args.std
        self.pc_encoder_type = args.pc_encoder_type
        self.pc_feat_dim = 192
        self.embed_dim = 1024
        self.group_size = 64
        self.num_group = 512
        self.pc_encoder_dim = 512
        self.patch_dropout = 0.0
        self.pc_ckpt_path = args.pc_ckpt_path
        self.lora_path = args.lora_path
        self.model_path = args.model_path
        self.get_pc_tokens_way = args.get_pc_tokens_way

def init_model(model_arg_):
    model_path = "llava-vicuna_phi_3_finetune_weight"
    model_name = get_model_name_from_path(model_path)
    model_path = model_arg_.model_path
    tokenizer, model, context_len = load_pretrained_model(model_path, None, model_name)

    if model_arg_.lora_path:
        from peft import PeftModel

        model = PeftModel.from_pretrained(model, model_arg_.lora_path)
        print("load lora weight ok")

    model.get_model().initialize_other_modules(model_arg_)
    print("load encoder, mlp ok")
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

    model.to(dtype=torch.bfloat16)
    model.get_model().vision_tower.to(dtype=torch.float)
    model.to(device)

    return tokenizer, model

def load_point_cloud(ply_file_path):
    """
    Load a point cloud from a binary_little_endian PLY and return a tensor of shape (8192, 6):
    (x, y, z, r, g, b).

    Defaults match the 3D-FRONT specification:
      - x, y, z, nx, ny, nz as double; red, green, blue as uchar.
    Also supports variants like Crops3D:
      - x, y, z as float; red, green, blue as short; optional extra fields (e.g., scalar_sf).
    """
    import numpy as np
    import torch

    # Map PLY scalar types to numpy dtypes
    ply_to_np = {
        'char': 'i1', 'uchar': 'u1', 'int8': 'i1', 'uint8': 'u1',
        'short': 'i2', 'ushort': 'u2', 'int16': 'i2', 'uint16': 'u2',
        'int': 'i4', 'uint': 'u4', 'int32': 'i4', 'uint32': 'u4',
        'float': 'f4', 'float32': 'f4', 'double': 'f8', 'float64': 'f8'
    }

    with open(ply_file_path, 'rb') as f:
        format_str = None
        vertex_count = None
        vertex_props = []
        in_vertex_props = False

        # Parse header
        while True:
            line = f.readline()
            if not line:
                raise ValueError(f"Unexpected EOF while reading PLY header: {ply_file_path}")
            line = line.decode('utf-8', errors='ignore').strip()
            if line.startswith('format'):
                # Expect "format binary_little_endian 1.0"
                parts = line.split()
                if len(parts) >= 2:
                    format_str = parts[1].lower()
            elif line.startswith('element'):
                parts = line.split()
                if len(parts) >= 3 and parts[1].lower() == 'vertex':
                    vertex_count = int(parts[2])
                    in_vertex_props = True
                else:
                    # Properties that follow belong to another element (e.g., faces)
                    in_vertex_props = False
            elif line.startswith('property') and in_vertex_props:
                parts = line.split()
                # Format: property <type> <name>
                if len(parts) >= 3:
                    ptype = parts[1].lower()
                    pname = parts[2].lower()
                    vertex_props.append((pname, ptype))
            elif line == 'end_header':
                break
            # ignore other header lines (comment, obj_info, etc.)

        if format_str != 'binary_little_endian':
            raise NotImplementedError(f"Only binary_little_endian PLY is supported, got '{format_str}' for {ply_file_path}")
        if vertex_count is None or vertex_count <= 0 or not vertex_props:
            raise ValueError(f"Invalid PLY header: missing vertex element/properties in {ply_file_path}")

        # Build numpy structured dtype from header (default aligns with 3D-FRONT)
        dtype_fields = []
        for pname, ptype in vertex_props:
            np_type = ply_to_np.get(ptype)
            if np_type is None:
                raise ValueError(f"Unsupported PLY property type '{ptype}' for field '{pname}' in {ply_file_path}")
            dtype_fields.append((pname, np_type))
        dtype = np.dtype(dtype_fields)

        # Read binary payload
        bytes_needed = dtype.itemsize * vertex_count
        raw = f.read(bytes_needed)
        if len(raw) < bytes_needed:
            raise ValueError(f"PLY binary payload too small: expected {bytes_needed} bytes, got {len(raw)} in {ply_file_path}")
        data = np.frombuffer(raw, dtype=dtype, count=vertex_count)

    names = set(data.dtype.names or [])
    # Required coordinates
    for coord in ('x', 'y', 'z'):
        if coord not in names:
            raise ValueError(f"Missing '{coord}' in PLY vertex properties for {ply_file_path}")

    x = data['x'].astype(np.float32)
    y = data['y'].astype(np.float32)
    z = data['z'].astype(np.float32)

    # Colors: try red/green/blue then r/g/b; if absent, fill zeros
    def pick_color(name_primary, name_alt):
        if name_primary in names:
            arr = data[name_primary]
        elif name_alt in names:
            arr = data[name_alt]
        else:
            arr = None
        return arr

    r_arr = pick_color('red', 'r')
    g_arr = pick_color('green', 'g')
    b_arr = pick_color('blue', 'b')

    if r_arr is None or g_arr is None or b_arr is None:
        # Fill zeros if any color missing
        r = np.zeros_like(x, dtype=np.float32)
        g = np.zeros_like(y, dtype=np.float32)
        b = np.zeros_like(z, dtype=np.float32)
    else:
        # Normalize to [0,255] then cast to float32
        def normalize_color(arr):
            if np.issubdtype(arr.dtype, np.floating):
                arrf = arr.astype(np.float32)
                # Heuristic: if values are in [0,1], scale to [0,255]
                maxv = float(np.nanmax(arrf)) if arrf.size > 0 else 0.0
                if maxv <= 1.0:
                    arrf = arrf * 255.0
                return np.clip(arrf, 0.0, 255.0)
            elif np.issubdtype(arr.dtype, np.signedinteger) or np.issubdtype(arr.dtype, np.unsignedinteger):
                arrf = arr.astype(np.float32)
                return np.clip(arrf, 0.0, 255.0)
            else:
                # Fallback
                return np.clip(arr.astype(np.float32), 0.0, 255.0)

        r = normalize_color(r_arr)
        g = normalize_color(g_arr)
        b = normalize_color(b_arr)

    # Stack into (N, 6): x, y, z, r, g, b
    pts = np.stack([x, y, z, r, g, b], axis=1)

    # Randomly sample/pad to 8192 points
    N = pts.shape[0]
    target = 8192
    if N > target:
        idx = np.random.choice(N, size=target, replace=False)
        pts = pts[idx]
    elif N < target and N > 0:
        pad_size = target - N
        pad_idx = np.random.choice(N, size=pad_size, replace=True)
        pts = np.concatenate([pts, pts[pad_idx]], axis=0)
    elif N == 0:
        raise ValueError(f"No vertices found in {ply_file_path}")

    return torch.tensor(pts, dtype=torch.float)

def process_samples(model, tokenizer, args, output_file_path):
    results = {}
    #Read the list file and iterate over samples
    with open(args.pcl_list_txt_file_path, 'r') as f:
        lines = f.readlines()
    for line in lines:
        parts = line.strip().split('@')
        if len(parts) < 2:
            raise ValueError(f"Invalid line format: {line}")
        identifier, scene_name = parts[0], parts[1]
        #Build text prompt file path and load text prompt
        txt_path = os.path.join(args.upd_text_folder_path, args.upd_version_name,
                                 args.upd_version_name_subfolder, f"{identifier}@{scene_name}.txt")
        try:
            with open(txt_path, 'r') as tf:
                prompt_text = tf.read().strip()
        except Exception as e:
            print(f"Error reading {txt_path}: {e}")
            continue

        #Build point cloud file path and load point cloud
        if args.upd_version_name == "3D-FRONT":
            pc_path = os.path.join(args.unzipped_point_cloud_path, identifier, scene_name, f"{scene_name}.ply")
        else:
            pc_path = os.path.join(args.unzipped_point_cloud_path, identifier, f"{scene_name}.ply")
        point_cloud = load_point_cloud(pc_path).unsqueeze(0).cuda() #moved to GPU

        #Prepare the prompt: add default image token as prefix as before
        qs = DEFAULT_IMAGE_TOKEN + "\n" + prompt_text

        #Tokenize prompt
        input_ids = tokenizer_image_token(qs, tokenizer, IMAGE_TOKEN_INDEX, return_tensors="pt").unsqueeze(0).cuda()
        
        #Prepare image tensor
        images_tensor = point_cloud.to(dtype=torch.bfloat16)

        temperature = args.temperature
        top_p = args.top_p
        max_new_tokens = args.max_new_tokens
        min_new_tokens = args.min_new_tokens
        num_beams = args.num_beams

        #Generate output
        with torch.inference_mode():
            output_ids = model.generate(
                input_ids,
                images=images_tensor,
                do_sample=True if temperature > 0 and num_beams == 1 else False,
                temperature=temperature,
                top_p=top_p,
                num_beams=num_beams,
                max_new_tokens=max_new_tokens,
                min_new_tokens=min_new_tokens,
                use_cache=True,
            )
        answer = tokenizer.decode(output_ids[0], skip_special_tokens=True)
        answer = answer.strip().replace("<|end|>", "").strip()

        scene_key = scene_name.split('.')[0]  # mimic splitting as in minigpt-3d_prog.py
        key = identifier + "@" + scene_key
        results[key] = {"prompt": prompt_text, "response": answer}
        print(f"Processed sample {identifier}.")

    #Save results to a JSON file
    with open(output_file_path, 'w') as fp:
        json.dump(results, fp, indent=2)
    print(f"Saved results to {output_file_path}")
    return results

    # --pcl_list_txt_file_path /project/3dllms/melgin/UPD-3D/pcl_lists/3D-FRONT_test.txt \
def main(args):
    #Set output directory
    args.out_path = os.path.join(args.out_path, "evaluation")
    args.output_file_path = os.path.join(args.out_path, "upd_inference_results.json")

    #Create the filename
    os.makedirs(args.out_path, exist_ok=True)
    tag_part = f"{args.json_tag}_" if args.json_tag else ""
    args.pcl_list_txt_filename_noext = os.path.basename(os.path.normpath(args.pcl_list_txt_file_path)).replace('.txt', '')
    output_file_path = os.path.join(args.out_path, f"inf_rslts_gplm_{tag_part}{args.pcl_list_txt_filename_noext}_{args.upd_version_name_subfolder}.json")

    if not os.path.exists(output_file_path):
        # Initialize model and tokenizer using mgpt3d arguments
        model_arg = MyClass(args)
        tokenizer, model = init_model(model_arg)
        model.eval()

        print(f'[INFO] Start processing samples from {args.pcl_list_txt_file_path}.')
        process_samples(model, tokenizer, args, output_file_path)

        #Release model and clear cuda cache
        del model
        torch.cuda.empty_cache()
    else:
        print(f'[INFO] {output_file_path} already exists')

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out_path", type=str,  default="./output_json")
    parser.add_argument("--pretrain_mm_mlp_adapter", type=str,  required=True)
    parser.add_argument("--lora_path", type=str, default=None)
    parser.add_argument("--model_path", type=str, default='./lava-vicuna_2024_4_Phi-3-mini-4k-instruct')
    parser.add_argument("--std", type=float, default=0.0)
    parser.add_argument("--pc_ckpt_path",  type=str,  required=True, default="./pretrained_weight/Uni3D_PC_encoder/modelzoo/uni3d-small/model.pt")
    parser.add_argument("--pc_encoder_type", type=str, required=True, default='small')
    parser.add_argument("--get_pc_tokens_way", type=str, required=True)
    parser.add_argument("--use_color",  action="store_true", default=True)
    parser.add_argument("--batch_size", type=int, default=10)
    parser.add_argument("--shuffle", type=bool, default=False)
    parser.add_argument("--num_workers", type=int, default=20)

    #evaluation setting
    parser.add_argument("--max_new_tokens", type=int, default=110, help="max number of generated tokens")
    parser.add_argument("--min_new_tokens", type=int, default=0, help="min number of generated tokens")
    parser.add_argument("--num_beams", type=int, default=1)
    parser.add_argument("--temperature", type=float, default=0.1)
    parser.add_argument("--top_k", type=int, default=1)
    parser.add_argument("--top_p", type=float, default=0.7)

    #UPD specific arguments
    parser.add_argument("--upd_text_folder_path", type=existing_dir, required=True, help="Path to the upd_text/ folder.")
    parser.add_argument("--upd_version_name", type=str, required=True, help="Name of the upd version (e.g., 'v1').")
    parser.add_argument("--upd_version_name_subfolder", type=str, required=True, help="Subfolder name for the upd version (e.g., 'standard').")
    parser.add_argument("--unzipped_point_cloud_path", type=existing_dir, required=True, help="Path to the unzipped point cloud folder containing dirs identifier/scene/scene.ply")
    parser.add_argument("--pcl_list_txt_file_path", type=existing_file, required=True, help="Path to the text file containing point cloud identifiers and scene names.")
    parser.add_argument("--json_tag", type=str, required=False, help="Optional tag to include in the output JSON filename, eg 'ft-comb' for finetune-combined", default=None)

    args = parser.parse_args()
    main(args)